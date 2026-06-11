import polars as pl
from loguru import logger


class FrictionDimensionEngine:
    """
    Dimension 6: Operational Friction
    Focus: Exception rates, dispute frequency, returns.
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_friction": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Dimension 6: Operational Friction")

        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "returns_events_window",
                "sales_events_window",
                "penalty_window",
                "sales_window"
            ]
        )

        df = df.with_columns(
            [
                pl.col("returns_events_window").fill_null(0),
                pl.col("sales_events_window").fill_null(0),
                pl.col("penalty_window").fill_null(0.0),
                pl.col("sales_window").fill_null(0.0),
            ]
        )

        # Higher friction score = MORE friction (WORSE)
        # We want the dimension to be normalized where 1.0 is highest friction?
        # NO. Let's standardize: Dimensions are usually 1.0 = GOOD, 0.0 = BAD. 
        # Actually, Friction is a negative dimension. Let's make 1.0 = NO FRICTION (Good), 0.0 = HIGH FRICTION.

        df = df.with_columns(
            pl.when(pl.col("sales_events_window") > 0)
            .then(pl.col("returns_events_window") / pl.col("sales_events_window"))
            .otherwise(0.0)
            .alias("return_frequency_rate"),
            
            pl.when(pl.col("sales_window") > 0)
            .then(pl.col("penalty_window") / pl.col("sales_window"))
            .otherwise(0.0)
            .alias("return_value_ratio")
        )

        # Invert so 1.0 is Good (Zero Friction)
        df = df.with_columns(
            (1.0 - (pl.col("return_frequency_rate") * 2.0).clip(0, 1)).alias("freq_score"), # >50% returns is 0
            (1.0 - (pl.col("return_value_ratio") * 2.0).clip(0, 1)).alias("val_score")
        )

        w_freq, w_val = 0.5, 0.5
        
        df = df.with_columns(
            (
                pl.col("freq_score") * w_freq +
                pl.col("val_score") * w_val
            ).clip(0, 1).alias("dim_friction")
        )

        return df.select(["customer_id", "date", "dim_friction"])
