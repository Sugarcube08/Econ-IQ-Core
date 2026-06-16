import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class ExposurePressureEngine:
    """
    Models customer ledger pressure behavior, focusing on outstanding persistence,
    exposure stability, and debt clearance capability.
    """

    def compute_score(
        self, pressure_df: pl.DataFrame, settlement_df: pl.DataFrame, features_df: pl.DataFrame, context: AnalysisContext
    ) -> pl.DataFrame:
        """
        Computes the deterministic Outstanding/Clearance Intelligence score.
        Mapped to: repayment_health_score
        """
        empty_schema = {
            "customer_id": pl.Utf8,
            "repayment_health_score": pl.Float64,
        }
        if pressure_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Join required components
        df = pressure_df.select(
            ["customer_id", "avg_outstanding", "peak_debit_persistence", "exposure_pressure_score"]
        )

        if not settlement_df.is_empty():
            df = df.join(
                settlement_df.select(
                    [
                        "customer_id",
                        "avg_repayment_days",
                        "overdue_60_90_count",
                        "overdue_90_120_count",
                        "overdue_120p_count",
                        "outstanding_bill_count",
                    ]
                ),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(
                [
                    pl.lit(180.0).alias("avg_repayment_days"),
                    pl.lit(0).alias("overdue_60_90_count"),
                    pl.lit(0).alias("overdue_90_120_count"),
                    pl.lit(0).alias("overdue_120p_count"),
                    pl.lit(0).alias("outstanding_bill_count"),
                ]
            )

        latest_features = (
            features_df.sort("date")
            .group_by("customer_id")
            .tail(1)
            .select(["customer_id", "sales_window"])
        )
        df = df.join(latest_features, on="customer_id", how="left")

        # Fill nulls for safe math
        df = df.with_columns(
            [
                pl.col("avg_repayment_days").fill_null(180.0),
                pl.col("overdue_60_90_count").fill_null(0),
                pl.col("overdue_90_120_count").fill_null(0),
                pl.col("overdue_120p_count").fill_null(0),
                pl.col("outstanding_bill_count").fill_null(0),
                pl.col("sales_window").fill_null(1.0),
            ]
        )

        # 2. Subfactor Extraction

        # Subfactor 4.1: Total Outstanding (30%)
        # Relative outstanding: outstanding / rolling_monthly_billing
        # Target: > 3.0x monthly billing is critical stress (0.0 score)
        monthly_billing = pl.max_horizontal(pl.col("sales_window") / (context.window_days / 30.0), 1.0)
        total_outstanding_score = (1.0 - (pl.col("avg_outstanding") / (monthly_billing * 3.0))).clip(0, 1)

        # Subfactor 4.2: Overdue Amount (25%)
        # Normalization: No overdue = 1.0 | 1 bill overdue >120p = 0.0 | 3+ bills >60p = 0.2
        overdue_penalty = (
            (pl.col("overdue_60_90_count") * 0.2)
            + (pl.col("overdue_90_120_count") * 0.5)
            + (pl.col("overdue_120p_count") * 1.0)
        ).clip(0, 1)
        overdue_score = (1.0 - overdue_penalty)

        # Subfactor 4.3: Outstanding Aging (25%)
        # Debit persistence days vs window duration
        # Target: > 40% of window in debit is severe stress (0.0 score)
        aging_score = (1.0 - (pl.col("peak_debit_persistence") / (context.window_days * 0.4))).clip(0, 1)

        # Subfactor 4.4: Exposure vs Monthly Billing Ratio (10%)
        # Direct stress indicator
        exposure_ratio_score = (1.0 - pl.col("exposure_pressure_score") / 2.0).clip(0, 1)

        # Subfactor 4.5: Credit Day Breach (10%)
        # Expected 60d. Actual - Expected.
        # Target: > 30d breach (90d total) starts penalizing heavily.
        expected_threshold = 60
        breach_days = (pl.col("avg_repayment_days") - expected_threshold).clip(0, 120)
        breach_score = (1.0 - (breach_days / 60.0)).clip(0, 1)

        # 3. Final Deterministic Fusion
        # Weights: Outstanding 30%, Overdue 25%, Aging 25%, Ratio 10%, Breach 10%
        df = df.with_columns(
            (
                (total_outstanding_score * 0.30)
                + (overdue_score * 0.25)
                + (aging_score * 0.25)
                + (exposure_ratio_score * 0.10)
                + (breach_score * 0.10)
            ).alias("repayment_health_score")
        )

        return df.select(
            [
                "customer_id",
                "repayment_health_score",
                total_outstanding_score.alias("subfactor_total_outstanding"),
                overdue_score.alias("subfactor_overdue_amount"),
                aging_score.alias("subfactor_outstanding_aging"),
                exposure_ratio_score.alias("subfactor_exposure_ratio"),
                breach_score.alias("subfactor_credit_day_breach"),
            ]
        )

    def compute_pressure(
        self, exposure_df: pl.DataFrame, features_df: pl.DataFrame, context: AnalysisContext
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "avg_outstanding": pl.Float64,
            "max_outstanding": pl.Float64,
            "exposure_pressure_score": pl.Float64,
            "debit_persistence_score": pl.Float64,
            "debt_clearance_ratio": pl.Float64,
            "unresolved_exposure_ratio": pl.Float64,
            "repayment_sufficiency": pl.Float64,
            "clearance_strength": pl.Float64,
        }
        if exposure_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Aggregate Exposure & Persistence Metrics
        agg_df = exposure_df.group_by("customer_id").agg(
            [
                pl.col("outstanding_balance").mean().alias("avg_outstanding"),
                pl.col("outstanding_balance").max().alias("max_outstanding"),
                pl.col("debit_persistence_days").max().alias("peak_debit_persistence"),
                pl.col("outstanding_balance").filter(pl.col("outstanding_balance") > 0).count().alias("days_in_debit"),
            ]
        )

        # 2. Join with Sales & Receipts Features
        # We need total receipts and total sales in the window to compute clearance
        latest_features = (
            features_df.sort("date")
            .group_by("customer_id")
            .tail(1)
            .select(["customer_id", "sales_window", "payments_window"])
        )
        df = agg_df.join(latest_features, on="customer_id", how="left")

        # 3. Calculate Debt Pressure Intelligence

        # Debt Clearance Ratio: payments_received / total_exposure_generated
        # We use max(sales, 1) to avoid division by zero
        df = df.with_columns(
            (pl.col("payments_window") / pl.max_horizontal(pl.col("sales_window"), 1.0))
            .clip(0, 1)
            .alias("debt_clearance_ratio")
        )

        # Unresolved Exposure Ratio: current_outstanding / peak_exposure
        # We use current outstanding (last row in exposure_df)
        current_outstanding = (
            exposure_df.sort("date")
            .group_by("customer_id")
            .tail(1)
            .select(["customer_id", "outstanding_balance"])
            .rename({"outstanding_balance": "current_outstanding"})
        )

        df = df.join(current_outstanding, on="customer_id", how="left")

        df = df.with_columns(
            (pl.col("current_outstanding") / pl.max_horizontal(pl.col("max_outstanding"), 1.0))
            .clip(0, 1)
            .alias("unresolved_exposure_ratio")
        )

        # Repayment Sufficiency: How effectively payments reduce debt
        # High when clearance is high AND unresolved ratio is low
        df = df.with_columns(
            (pl.col("debt_clearance_ratio") * (1.0 - pl.col("unresolved_exposure_ratio")))
            .clip(0, 1)
            .alias("repayment_sufficiency")
        )

        # Clearance Strength: Balance between persistence and resolution
        # Penalized by debit persistence
        persistence_penalty = (pl.col("peak_debit_persistence") / (context.window_days * 0.5)).clip(0, 1)
        df = df.with_columns(
            (pl.col("repayment_sufficiency") * (1.0 - persistence_penalty)).clip(0, 1).alias("clearance_strength")
        )

        # 4. Standard Scores (Legacy Compatibility)
        monthly_multiplier = context.window_days / 30.0
        df = df.with_columns(
            (pl.col("avg_outstanding") / pl.max_horizontal(pl.col("sales_window") / monthly_multiplier, 100.0))
            .clip(0, 2)
            .alias("exposure_pressure_score")
        )

        persistence_threshold = context.window_days * 0.4
        df = df.with_columns(
            (pl.col("peak_debit_persistence") / persistence_threshold).clip(0, 1).alias("debit_persistence_score")
        )

        return df.select(
            [
                "customer_id",
                "avg_outstanding",
                "max_outstanding",
                "current_outstanding",
                "sales_window",
                "payments_window",
                "peak_debit_persistence",
                "exposure_pressure_score",
                "debit_persistence_score",
                "debt_clearance_ratio",
                "unresolved_exposure_ratio",
                "repayment_sufficiency",
                "clearance_strength",
            ]
        )
