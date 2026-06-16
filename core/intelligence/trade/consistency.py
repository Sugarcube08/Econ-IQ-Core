import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class TradeConsistencyEngine:
    """
    Prioritizes consistent commercial participation and regularity
    above raw sporadic volume.
    """

    def compute_consistency(
        self, ledger_df: pl.DataFrame, cadence_df: pl.DataFrame, context: AnalysisContext
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "participation_density": pl.Float64,
            "trade_regularity_score": pl.Float64,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Participation Density (Days with SALE / Total Days in Window)
        window_days = context.window_days
        density_df = (
            ledger_df.filter(pl.col("event_type") == "SALE")
            .with_columns(pl.col("event_date").dt.date().alias("date"))
            .group_by("customer_id")
            .agg([pl.col("date").n_unique().alias("active_days")])
            .with_columns((pl.col("active_days") / window_days).clip(0, 1).alias("participation_density"))
        )

        # 2. Join with Cadence Stats (Median/StdDev of gaps)
        df = density_df.join(cadence_df, on="customer_id", how="left")

        # 3. Trade Regularity Score
        # Regularity is high if participation density is high AND variance in gaps is low
        df = df.with_columns(
            (pl.col("stddev_gap") / pl.max_horizontal(pl.col("median_gap"), 1.0))
            .fill_null(1.0)
            .alias("gap_variance_ratio")
        )

        df = df.with_columns(
            (pl.col("participation_density") * 0.7 + (1.0 - pl.col("gap_variance_ratio").clip(0, 1)) * 0.3).alias(
                "trade_regularity_score"
            )
        )

        return df.select(["customer_id", "participation_density", "trade_regularity_score"])
