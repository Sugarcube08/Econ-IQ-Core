import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class StateEngine:
    """
    Infers longitudinal behavioral states.
    """

    def compute(
        self,
        features_df: pl.DataFrame,
        cadence_df: pl.DataFrame,
        stress_df: pl.DataFrame,
        trust_df: pl.DataFrame,
        settlement_df: pl.DataFrame,
        pressure_df: pl.DataFrame,
        rhythm_df: pl.DataFrame,
        consistency_df: pl.DataFrame,
        conf_df: pl.DataFrame,
        context: AnalysisContext,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "behavioral_state": pl.Utf8,
            "trajectory": pl.Utf8,
            "cadence_class": pl.Utf8,
            "overall_class": pl.Utf8,
            "stress_score": pl.Float64,
            "trust_score": pl.Float64,
            "events_window": pl.Int64,
            "sales_window": pl.Float64,
            "penalty_window": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug(f"Inferring longitudinal behavioral states and holistic grades for {context.window_days}d window")

        # Join all components on customer_id (and date where applicable)
        if "customer_id" in stress_df.columns:
            df = features_df.join(stress_df, on=["customer_id", "date"], how="left")
        else:
            df = features_df.with_columns(pl.lit(None).alias("stress_score"))

        if "customer_id" in trust_df.columns:
            df = df.join(trust_df, on=["customer_id", "date"], how="left")
        else:
            df = df.with_columns(pl.lit(None).alias("trust_score"))

        if "customer_id" in conf_df.columns:
            df = df.join(conf_df, on=["customer_id", "date"], how="left")
        else:
            df = df.with_columns(pl.lit(None).alias("confidence_modifier"), pl.lit(None).alias("confidence_score"))

        # Static/Longitudinal joins (customer_id only)
        if "customer_id" in settlement_df.columns:
            df = df.join(settlement_df, on="customer_id", how="left")
        else:
            df = df.with_columns(pl.lit(None).alias("avg_repayment_days"))

        if "customer_id" in pressure_df.columns:
            df = df.join(pressure_df, on="customer_id", how="left")
        else:
            df = df.with_columns(pl.lit(None).alias("exposure_pressure_score"))

        if "customer_id" in rhythm_df.columns:
            df = df.join(rhythm_df, on="customer_id", how="left")
        else:
            df = df.with_columns(
                pl.lit(None).alias("repayment_regularity_score"), pl.lit(None).alias("repayment_fragmentation")
            )

        if "customer_id" in consistency_df.columns:
            df = df.join(consistency_df, on="customer_id", how="left")
        else:
            df = df.with_columns(pl.lit(None).alias("trade_regularity_score"))

        # Cadence is often a baseline per customer, but we can broadcast it
        if not cadence_df.is_empty():
            df = df.join(cadence_df.select(["customer_id", "cadence_class"]), on="customer_id", how="left")
        else:
            df = df.with_columns(pl.lit("UNKNOWN").alias("cadence_class"))

        # Ensure cadence_class is never null (database constraint)
        df = df.with_columns(pl.col("cadence_class").fill_null("UNKNOWN"))

        # Fill nulls for safe math in grading
        df = df.with_columns(
            [
                pl.col("avg_repayment_days").fill_null(180.0),
                pl.col("exposure_pressure_score").fill_null(1.0),
                pl.col("repayment_regularity_score").fill_null(0.0),
                pl.col("repayment_fragmentation").fill_null(1.0),
                pl.col("trade_regularity_score").fill_null(0.0),
                pl.col("stress_score").fill_null(0.0),
                pl.col("confidence_modifier").fill_null(0.0),
                pl.col("trust_score").fill_null(0.0),
            ]
        )

        from core.policy.manager import policy_manager
        policy = policy_manager.policy.state

        # 1. State Inference - Deterministic & Operationally Meaningful
        df = df.with_columns(
            pl.when(pl.col("events_window") == 0)
            .then(pl.lit("inactive"))
            .when(pl.col("stress_score") > policy.declining_stress_threshold)
            .then(pl.lit("declining"))
            .when((pl.col("trust_score") > policy.elite_trust_threshold) & (pl.col("stress_score") < policy.elite_stress_threshold))
            .then(pl.lit("elite"))
            .when((pl.col("trust_score") > policy.active_trust_threshold) & (pl.col("stress_score") < policy.active_stress_threshold))
            .then(pl.lit("active"))
            .otherwise(pl.lit("irregular"))
            .alias("behavioral_state")
        )

        # 2. Adaptive Trajectory Engine (Relative to history)
        recent_window_days = max(14, int(context.window_days * 0.2))

        # Calculate historical velocity using the effective active duration
        df = df.with_columns(
            (pl.col("sales_window") / pl.max_horizontal(pl.col("active_duration_days"), 1.0)).alias(
                "historical_velocity"
            ),
            (pl.col("sales_recent") / recent_window_days).alias("current_velocity"),
        )

        # Calculate velocity delta
        df = df.with_columns(
            (pl.col("current_velocity") / pl.max_horizontal(pl.col("historical_velocity"), 1.0)).alias("velocity_ratio")
        )

        df = df.with_columns(
            pl.when(pl.col("events_recent") == 0)
            .then(pl.lit("inactive"))
            .when((pl.col("velocity_ratio") > policy.accelerating_ratio) & (pl.col("historical_velocity") > 0))
            .then(pl.lit("ACCELERATING"))
            .when((pl.col("velocity_ratio") > policy.growing_ratio) & (pl.col("velocity_ratio") <= policy.accelerating_ratio))
            .then(pl.lit("GROWING"))
            .when((pl.col("velocity_ratio") < policy.collapsing_ratio) & (pl.col("historical_velocity") > 0))
            .then(pl.lit("COLLAPSING"))
            .when((pl.col("velocity_ratio") < policy.declining_ratio) & (pl.col("velocity_ratio") >= policy.collapsing_ratio))
            .then(pl.lit("DECLINING"))
            .otherwise(pl.lit("STABLE"))
            .alias("trajectory")
        )

        # 3. Longitudinal State Refinement
        df = df.with_columns(
            pl.when(
                (pl.col("behavioral_state") != "inactive") & 
                ((pl.col("trajectory").is_in(["COLLAPSING", "DECLINING"])) | (pl.col("stress_score") > policy.declining_stress_threshold))
            )
            .then(pl.lit("declining"))
            .otherwise(pl.col("behavioral_state"))
            .alias("behavioral_state")
        )

        # 4. OVERALL CLASS DERIVATION
        df = df.with_columns(
            pl.when(pl.col("trust_score") >= policy.class_a_threshold)
            .then(pl.lit("A"))
            .when(pl.col("trust_score") >= policy.class_b_threshold)
            .then(pl.lit("B"))
            .when(pl.col("trust_score") >= policy.class_c_threshold)
            .then(pl.lit("C"))
            .otherwise(pl.lit("D"))
            .alias("overall_class")
        )

        return df.select(
            [
                "customer_id",
                "date",
                "behavioral_state",
                "trajectory",
                "cadence_class",
                "overall_class",
                "stress_score",
                "trust_score",
                "events_window",
                "sales_window",
                "penalty_window",
                "last_purchased_at",
            ]
        )
