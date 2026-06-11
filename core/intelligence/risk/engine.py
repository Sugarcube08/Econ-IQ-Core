import polars as pl
from loguru import logger


class RiskEngine:
    """
    Risk Engine v2: Computes B2B default risk scores.
    Formula: RS = 0.40 * EWAAgingScore + 0.30 * CreditUtilization + 0.15 * CollectionResistance + 0.15 * Instability
    """

    def compute(
        self,
        settlement_df: pl.DataFrame,
        pressure_df: pl.DataFrame,
        rhythm_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "risk_score": pl.Float64,
        }
        if settlement_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Risk Score v2 (Multi-Dimensional Fusion)")

        # 1. Start with settlement metrics
        df = settlement_df.select(
            [
                "customer_id",
                "total_exposure",
                "outstanding_amount",
                "overdue_60_90_amount",
                "overdue_90_120_amount",
                "overdue_120p_amount",
            ]
        )

        # 2. Join pressure
        if not pressure_df.is_empty():
            df = df.join(
                pressure_df.select(["customer_id", "exposure_pressure_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias("exposure_pressure_score"))

        # 3. Join rhythm
        if not rhythm_df.is_empty():
            df = df.join(
                rhythm_df.select(["customer_id", "repayment_fragmentation", "repayment_regularity_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(
                pl.lit(1.0).alias("repayment_fragmentation"),
                pl.lit(1.0).alias("repayment_regularity_score"),
            )

        # Fill nulls
        df = df.with_columns(
            [
                pl.col("total_exposure").fill_null(0.0),
                pl.col("outstanding_amount").fill_null(0.0),
                pl.col("overdue_60_90_amount").fill_null(0.0),
                pl.col("overdue_90_120_amount").fill_null(0.0),
                pl.col("overdue_120p_amount").fill_null(0.0),
                pl.col("exposure_pressure_score").fill_null(0.0),
                pl.col("repayment_fragmentation").fill_null(1.0),
                pl.col("repayment_regularity_score").fill_null(1.0),
            ]
        )

        # 4. Compute Subfactors
        # Subfactor 1: EWAAgingScore (higher penalty for older overdue buckets)
        total_exp = pl.max_horizontal(pl.col("total_exposure"), 1.0)
        overdue_weighted_penalty = (
            (pl.col("overdue_60_90_amount") / total_exp * 0.2)
            + (pl.col("overdue_90_120_amount") / total_exp * 0.5)
            + (pl.col("overdue_120p_amount") / total_exp * 1.0)
        ).clip(0, 1)
        df = df.with_columns(overdue_weighted_penalty.alias("ewa_aging_score"))

        # Subfactor 2: Credit Utilization / Exposure Pressure
        df = df.with_columns(
            (pl.col("exposure_pressure_score").clip(0, 2) / 2.0).alias("credit_utilization")
        )

        # Subfactor 3: Collection Resistance (approximated by payment fragmentation)
        df = df.with_columns(
            ((pl.col("repayment_fragmentation") - 1.0).clip(0, 2) / 2.0).alias("collection_resistance")
        )

        # Subfactor 4: Instability (based on payment regularity variance)
        df = df.with_columns(
            (1.0 - pl.col("repayment_regularity_score")).clip(0, 1).alias("instability")
        )

        # 5. Apply Weights
        w1, w2, w3, w4 = 0.40, 0.30, 0.15, 0.15
        df = df.with_columns(
            (
                (pl.col("ewa_aging_score") * w1)
                + (pl.col("credit_utilization") * w2)
                + (pl.col("collection_resistance") * w3)
                + (pl.col("instability") * w4)
            )
            .clip(0, 1)
            .alias("risk_score")
        )

        # Add default date anchor
        from datetime import UTC, datetime
        df = df.with_columns(pl.lit(datetime.now(UTC).date()).alias("date"))

        return df.select(["customer_id", "date", "risk_score"])
