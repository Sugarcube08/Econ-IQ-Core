import polars as pl
from loguru import logger


class TrustEngine:
    """
    Trust Engine v2: Computes B2B relationship trust scores.
    Formula: TS = 0.50 * (1 - AvgDPD) + 0.30 * PaymentConsistency + 0.20 * DiscountHarvesting
    """

    def compute(
        self,
        settlement_df: pl.DataFrame,
        rhythm_df: pl.DataFrame,
        features_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "trust_score": pl.Float64,
        }
        if settlement_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Trust Score v2 (Multi-Dimensional Fusion)")

        # 1. Start with settlement metrics
        df = settlement_df.select(["customer_id", "avg_repayment_days"])

        # 2. Join rhythm (Payment Consistency)
        if not rhythm_df.is_empty():
            df = df.join(
                rhythm_df.select(["customer_id", "repayment_regularity_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(1.0).alias("repayment_regularity_score"))

        # 3. Join features (Discount Harvesting)
        if not features_df.is_empty():
            # Join the latest date row from features
            latest_feat = features_df.sort("date").group_by("customer_id").tail(1)
            df = df.join(
                latest_feat.select(["customer_id", "date", "sales_window", "discounts_window"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(
                pl.lit(None).cast(pl.Date).alias("date"),
                pl.lit(0.0).alias("sales_window"),
                pl.lit(0.0).alias("discounts_window"),
            )

        # 4. Fill nulls and anchor date
        df = df.with_columns(
            [
                pl.col("date").cast(pl.Date),
                pl.col("avg_repayment_days").fill_null(180.0),
                pl.col("repayment_regularity_score").fill_null(0.0),
                pl.col("sales_window").fill_null(0.0),
                pl.col("discounts_window").fill_null(0.0),
            ]
        )

        # 5. Compute Subfactors
        # Subfactor 1: 1 - AvgDPD (normalized to 180 days max delay)
        df = df.with_columns(
            (1.0 - (pl.col("avg_repayment_days") / 180.0).clip(0, 1)).alias("dpd_score")
        )

        # Subfactor 2: Payment Consistency
        df = df.with_columns(
            pl.col("repayment_regularity_score").alias("consistency_score")
        )

        # Subfactor 3: Discount Harvesting Rate
        df = df.with_columns(
            pl.when(pl.col("sales_window") > 0)
            .then((pl.col("discounts_window") / pl.col("sales_window")).clip(0, 1))
            .otherwise(0.0)
            .alias("discount_harvesting")
        )

        # 6. Apply Weights
        w1, w2, w3 = 0.50, 0.30, 0.20
        df = df.with_columns(
            (
                (pl.col("dpd_score") * w1)
                + (pl.col("consistency_score") * w2)
                + (pl.col("discount_harvesting") * w3)
            )
            .clip(0, 1)
            .alias("trust_score")
        )

        # Ensure date column is present
        if "date" not in df.columns or df["date"].null_count() == df.height:
            from datetime import UTC, datetime
            df = df.with_columns(pl.lit(datetime.now(UTC).date()).alias("date"))

        return df.select(["customer_id", "date", "trust_score"])
