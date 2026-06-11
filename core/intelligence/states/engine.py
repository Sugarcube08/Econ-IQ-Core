import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class StateEngine:
    """
    Infers longitudinal behavioral states based on V2 Meta Scores.
    Maps dimensional intelligence to business-logic states via policy.
    """
    def compute(
        self,
        features_df: pl.DataFrame,
        meta_scores_df: pl.DataFrame,
        context: AnalysisContext,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "behavioral_state": pl.Utf8,
            "trajectory": pl.Utf8,
            "overall_class": pl.Utf8,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug(f"Inferring longitudinal behavioral states for {context.window_days}d window")

        df = features_df.select([
            "customer_id", "date", "events_window", "sales_window", 
            "sales_recent", "active_duration_days"
        ])

        if not meta_scores_df.is_empty():
            df = df.join(meta_scores_df, on=["customer_id", "date"], how="left")
        else:
            df = df.with_columns(
                pl.lit(0.0).alias("trust_score"),
                pl.lit(0.0).alias("risk_score"),
                pl.lit(0.0).alias("growth_score"),
                pl.lit(0.0).alias("opportunity_score")
            )
            
        df = df.with_columns([
            pl.col("trust_score").fill_null(0.0),
            pl.col("risk_score").fill_null(0.0),
            pl.col("growth_score").fill_null(0.0),
            pl.col("opportunity_score").fill_null(0.0),
        ])

        # Synthesize V1 Stress Score (inverse of V2 Risk Score for backward compatible policy mapping)
        df = df.with_columns(
            (1.0 - pl.col("risk_score")).alias("stress_score")
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

        df = df.with_columns(
            (pl.col("sales_window") / pl.max_horizontal(pl.col("active_duration_days"), 1.0)).alias("historical_velocity"),
            (pl.col("sales_recent") / recent_window_days).alias("current_velocity"),
        )

        df = df.with_columns(
            (pl.col("current_velocity") / pl.max_horizontal(pl.col("historical_velocity"), 1.0)).alias("velocity_ratio")
        )

        df = df.with_columns(
            pl.when(pl.col("events_window") == 0)
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
                "overall_class",
            ]
        )
