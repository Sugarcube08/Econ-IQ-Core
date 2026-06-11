import polars as pl
from loguru import logger


class GrowthEngine:
    """
    Growth Engine v2: Computes B2B customer growth scores.
    Formula: GS = 0.50 * PurchaseVelocity + 0.30 * SKUDiversification + 0.20 * FrequencyTrend
    """

    def compute(
        self,
        features_df: pl.DataFrame,
        consistency_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "growth_score": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Growth Score v2 (Multi-Dimensional Fusion)")

        # 1. Select latest features per customer
        df = features_df.sort("date").group_by("customer_id").tail(1)

        # 2. Join consistency
        if not consistency_df.is_empty():
            df = df.join(
                consistency_df.select(["customer_id", "trade_regularity_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(0.5).alias("trade_regularity_score"))

        # Fill nulls
        df = df.with_columns(
            [
                pl.col("sales_window").fill_null(0.0),
                pl.col("sales_recent").fill_null(0.0),
                pl.col("events_window").fill_null(1.0),
                pl.col("events_recent").fill_null(0.0),
                pl.col("trade_regularity_score").fill_null(0.5),
            ]
        )

        # 3. Compute Subfactors
        # Subfactor 1: Purchase Velocity (recent vs long-term sales scaled)
        # We assume recent window is ~73 days (20% of 365). Perfect growth ratio is 0.20.
        df = df.with_columns(
            pl.when(pl.col("sales_window") > 0)
            .then(((pl.col("sales_recent") / pl.col("sales_window")) / 0.20).clip(0, 1.5) / 1.5)
            .otherwise(0.0)
            .alias("purchase_velocity")
        )

        # Subfactor 2: SKU Diversification (approximated by trade regularity)
        df = df.with_columns(
            pl.col("trade_regularity_score").alias("sku_diversification")
        )

        # Subfactor 3: Frequency Trend (recent events vs window events scaled)
        df = df.with_columns(
            pl.when(pl.col("events_window") > 0)
            .then(((pl.col("events_recent") / pl.col("events_window")) / 0.20).clip(0, 1.5) / 1.5)
            .otherwise(0.0)
            .alias("frequency_trend")
        )

        # 4. Apply Weights
        w1, w2, w3 = 0.50, 0.30, 0.20
        df = df.with_columns(
            (
                (pl.col("purchase_velocity") * w1)
                + (pl.col("sku_diversification") * w2)
                + (pl.col("frequency_trend") * w3)
            )
            .clip(0, 1)
            .alias("growth_score")
        )

        # Add default date anchor
        from datetime import UTC, datetime
        df = df.with_columns(pl.lit(datetime.now(UTC).date()).alias("date"))

        return df.select(["customer_id", "date", "growth_score"])
