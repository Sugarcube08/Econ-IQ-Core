import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class PaymentBehaviorEngine:
    """
    Measures repayment quality, liquidity discipline, and debt clearance capability.
    Realigned to penalize persistent debt pressure even if payments are active.
    """

    def compute_score(
        self, settlement_df: pl.DataFrame, rhythm_df: pl.DataFrame, pressure_df: pl.DataFrame, context: AnalysisContext, customer_avg_billing: dict | None = None
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "payment_behavior_score": pl.Float64,
        }
        if settlement_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing deterministic unified payment discipline intelligence")

        # 1. Join pillars
        df = settlement_df.select(
            [
                "customer_id", 
                "avg_repayment_days", 
                "total_bill_count", 
                "total_exposure",
                "outstanding_amount",
                "overdue_60_90_amount", 
                "overdue_90_120_amount", 
                "overdue_120p_amount"
            ]
        )

        if not rhythm_df.is_empty():
            df = df.join(rhythm_df.select(["customer_id", "payment_count", "repayment_regularity_score", "repayment_fragmentation"]), on="customer_id", how="left")
        else:
            df = df.with_columns(
                pl.lit(1.0).alias("repayment_regularity_score"), 
                pl.lit(1.0).alias("repayment_fragmentation"),
                pl.lit(0).alias("payment_count")
            )

        if not pressure_df.is_empty():
            df = df.join(
                pressure_df.select(
                    [
                        "customer_id", 
                        "exposure_pressure_score", 
                        "current_outstanding", 
                        "max_outstanding",
                        "avg_outstanding",
                        "sales_window",
                    ]
                ),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(
                pl.lit(1.0).alias("exposure_pressure_score"),
                pl.lit(0.0).alias("current_outstanding"),
                pl.lit(0.0).alias("max_outstanding"),
                pl.lit(0.0).alias("avg_outstanding"),
                pl.lit(1.0).alias("sales_window"),
            )

        # Fill nulls for safe math
        df = df.with_columns(
            [
                pl.col("avg_repayment_days").fill_null(180.0),
                pl.col("total_bill_count").fill_null(0),
                pl.col("total_exposure").fill_null(0.0),
                pl.col("outstanding_amount").fill_null(0.0),
                pl.col("overdue_60_90_amount").fill_null(0.0),
                pl.col("overdue_90_120_amount").fill_null(0.0),
                pl.col("overdue_120p_amount").fill_null(0.0),
                pl.col("repayment_regularity_score").fill_null(1.0),
                pl.col("repayment_fragmentation").fill_null(2.5),
                pl.col("exposure_pressure_score").fill_null(1.0),
                pl.col("payment_count").fill_null(0),
                pl.col("current_outstanding").fill_null(0.0),
                pl.col("max_outstanding").fill_null(0.0),
                pl.col("avg_outstanding").fill_null(0.0),
                pl.col("sales_window").fill_null(1.0),
            ]
        )

        # 2. Subfactor Extraction

        from core.policy.manager import policy_manager
        policy = policy_manager.policy.payment

        # Subfactor 1: Payment Delay
        # Progressive deterioration based on policy limits
        delay_score = (
            pl.when(pl.col("avg_repayment_days") <= policy.delay_healthy_days)
            .then(pl.lit(1.0))
            .when(pl.col("avg_repayment_days") <= policy.delay_warning_days)
            .then(1.0 - (pl.col("avg_repayment_days") - policy.delay_healthy_days) * ((1.0 - policy.delay_warning_score) / (policy.delay_warning_days - policy.delay_healthy_days)))
            .when(pl.col("avg_repayment_days") <= policy.delay_critical_days)
            .then(policy.delay_warning_score - (pl.col("avg_repayment_days") - policy.delay_warning_days) * (policy.delay_warning_score / (policy.delay_critical_days - policy.delay_warning_days)))
            .otherwise(0.0)
            .clip(0, 1)
            .alias("delay_score")
        )

        # Subfactor 2: Payment Consistency (Based on CV)
        consistency_score = (
            pl.when(pl.col("payment_count") > 0)
            .then((1.0 - pl.col("repayment_regularity_score")).clip(0, 1))
            .otherwise(0.0)
            .alias("consistency_score")
        )

        # Subfactor 3: Partial Payment Habit
        partial_habit_score = (
            pl.when(pl.col("payment_count") > 0)
            .then((1.0 - (pl.col("repayment_fragmentation") - 1.0) / (policy.partial_habit_max_fragmentation - 1.0)).clip(0, 1))
            .otherwise(0.0)
            .alias("partial_habit_score")
        )

        # Subfactor 4: Individualized Clearance Discipline
        cust_billing_map = customer_avg_billing or {}
        df = df.with_columns(
            pl.col("customer_id")
            .map_elements(lambda x: cust_billing_map.get(x, 0.0), return_dtype=pl.Float64)
            .alias("customer_avg_monthly_billing")
        )
        
        clearance_ratio = (pl.col("outstanding_amount") / pl.max_horizontal(pl.col("customer_avg_monthly_billing"), 1.0))
        clearance_score = (
            pl.when(pl.col("outstanding_amount") == 0)
            .then(pl.lit(1.0))
            .otherwise((1.0 - clearance_ratio / policy.clearance_critical_ratio).clip(0, 1))
            .alias("clearance_score")
        )

        # Subfactor 5: Exposure-Weighted Aging
        total_exp = pl.max_horizontal(pl.col("total_exposure"), 1.0)
        overdue_weighted_penalty = (
            (pl.col("overdue_60_90_amount") / total_exp * policy.aging_60_90_weight) +
            (pl.col("overdue_90_120_amount") / total_exp * policy.aging_90_120_weight) +
            (pl.col("overdue_120p_amount") / total_exp * policy.aging_120p_weight)
        ).clip(0, 1)
        aging_score = (1.0 - overdue_weighted_penalty).alias("aging_score")

        # Subfactor 6: Outstanding Pressure
        discipline_score = (1.0 - pl.col("exposure_pressure_score") / policy.discipline_scale_factor).clip(0, 1)

        # Subfactor 7: Credit Day Breach
        breach_days = (pl.col("avg_repayment_days") - policy.breach_expected_threshold).clip(0, policy.breach_max_days)
        breach_score = (1.0 - (breach_days / policy.breach_scaling_factor)).clip(0, 1)

        # 3. Final Deterministic Fusion (Weighted Sum from policy settings)
        df = df.with_columns(
            (
                (delay_score * policy.delay_weight)
                + (consistency_score * policy.consistency_weight)
                + (partial_habit_score * policy.partial_habit_weight)
                + (clearance_score * policy.clearance_weight)
                + (aging_score * policy.weight_aging)
                + (discipline_score * policy.discipline_weight)
                + (breach_score * policy.breach_weight)
            ).alias("raw_payment_score")
        )

        # 4. Evidence Strength & Confidence Ceiling
        evidence_strength = (
            (pl.col("total_bill_count").log(10) / 1.7).clip(0, 1) * 
            (pl.col("payment_count").log(10) / 1.6).clip(0, 1)
        ).alias("evidence_strength")

        df = df.with_columns(evidence_strength)

        # Apply Graduated Confidence Caps dynamically compiled from policy
        cap_expr = pl.col("raw_payment_score")
        for cap_info in sorted(policy.evidence_caps, key=lambda x: x["limit"], reverse=True):
            cap_expr = pl.when(pl.col("evidence_strength") < cap_info["limit"]).then(pl.min_horizontal(pl.col("raw_payment_score"), cap_info["cap"])).otherwise(cap_expr)
            
        df = df.with_columns(cap_expr.alias("payment_behavior_score"))

        return df.select(
            [
                "customer_id",
                "payment_behavior_score",
                "evidence_strength",
                delay_score.alias("subfactor_payment_delay"),
                consistency_score.alias("subfactor_payment_consistency"),
                discipline_score.alias("subfactor_credit_discipline"),
                partial_habit_score.alias("subfactor_partial_payment_habit"),
                clearance_score.alias("subfactor_clearance_discipline"),
                aging_score.alias("subfactor_outstanding_aging"),
            ]
        )
