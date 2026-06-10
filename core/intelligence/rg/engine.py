import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class RGBehaviorEngine:
    """
    Measures customer-caused operational friction (Return Goods burden).
    LOWER IS BETTER (0.0 -> 1.0+).
    0.0 represents a clean customer with no returns.
    Higher scores represent increasing operational friction and return burden.
    """

    def compute_score(self, features_df: pl.DataFrame, context: AnalysisContext) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "rg_rate_score": pl.Float64,
            "subfactor_return_intensity": pl.Float64,
            "subfactor_return_frequency": pl.Float64,
            "raw_rg_ratio": pl.Float64,
            "raw_rg_amount": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Simplified RG Ratio Information")

        # 1. Base Metrics
        df = features_df.select(["customer_id", "date", "penalty_window", "sales_window"])

        # rg_score = total_rg_amount / total_purchase_amount
        df = df.with_columns(
            pl.when(pl.col("sales_window") > 0.0)
            .then((pl.col("penalty_window") / pl.col("sales_window")).clip(0.0, 1.0))
            .otherwise(0.0)
            .alias("rg_rate_score")
        )

        return df.select(
            [
                "customer_id",
                "date",
                "rg_rate_score",
                pl.lit(0.0).alias("subfactor_return_intensity"),
                pl.lit(0.0).alias("subfactor_return_frequency"),
                pl.col("rg_rate_score").alias("raw_rg_ratio"),
                pl.col("penalty_window").alias("raw_rg_amount"),
            ]
        )
