import polars as pl
from loguru import logger


class ValueDimensionEngine:
    """
    Dimension 9: Commercial Value
    Focus: Absolute importance, revenue share, and margin contribution.
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        if features_df.is_empty():
            return pl.DataFrame({"customer_id": [], "date": [], "dim_value": []})

        logger.debug("Computing Dimension 9: Commercial Value")
        
        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "sales_window", 
                "net_revenue_window",
                "log_sales_scale"
            ]
        )

        # Sub-scores
        # 1. Gross Volume Score (scaled log)
        df = df.with_columns(
            (pl.col("log_sales_scale") / 7.0).clip(0, 1).alias("gross_volume_score"),
            # 2. Net Revenue Score (Efficiency)
            pl.when(pl.col("sales_window") > 0)
            .then((pl.col("net_revenue_window") / pl.col("sales_window")).clip(0, 1))
            .otherwise(0.0)
            .alias("revenue_efficiency_score")
        )

        w_vol, w_eff = 0.7, 0.3
        
        df = df.with_columns(
            (
                pl.col("gross_volume_score") * w_vol +
                pl.col("revenue_efficiency_score") * w_eff
            ).clip(0, 1).alias("dim_value")
        )

        return df.select(["customer_id", "date", "dim_value"])
