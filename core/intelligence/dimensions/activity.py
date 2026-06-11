import polars as pl
from loguru import logger


class ActivityDimensionEngine:
    """
    Dimension 1: Commercial Activity
    Focus: Buying velocity, frequency, and consistency.
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        if features_df.is_empty():
            return pl.DataFrame({"customer_id": [], "date": [], "dim_activity": []})

        logger.debug("Computing Dimension 1: Commercial Activity")
        
        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "sales_window", 
                "sales_events_window", 
                "participation_density",
                "log_sales_scale",
                "active_duration_days"
            ]
        )

        df = df.with_columns(
            [
                pl.col("sales_window").fill_null(0.0),
                pl.col("sales_events_window").fill_null(0),
                pl.col("participation_density").fill_null(0.0),
                pl.col("log_sales_scale").fill_null(0.0),
                pl.col("active_duration_days").fill_null(1.0)
            ]
        )

        # Sub-scores
        df = df.with_columns(
            ((pl.col("sales_events_window") / pl.max_horizontal(pl.col("active_duration_days") / 30.0, 1.0)).clip(0, 5) / 5.0).alias("freq_score"),
            (pl.col("log_sales_scale") / 7.0).clip(0, 1).alias("vol_score"), # Assume 10M is max log scale (~7)
            pl.col("participation_density").alias("consistency_score")
        )

        # Dimension Score: Weighted combination
        w_freq, w_vol, w_cons = 0.4, 0.3, 0.3
        
        df = df.with_columns(
            (
                pl.col("freq_score") * w_freq +
                pl.col("vol_score") * w_vol +
                pl.col("consistency_score") * w_cons
            ).clip(0, 1).alias("dim_activity")
        )

        return df.select(["customer_id", "date", "dim_activity"])
