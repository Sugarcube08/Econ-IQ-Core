import polars as pl
from loguru import logger


class RelationshipDimensionEngine:
    """
    Dimension 4: Relationship Quality
    Focus: Longevity, mutual dependence, and engagement.
    """
    def compute(self, features_df: pl.DataFrame, consistency_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_relationship": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        df = features_df.select(["customer_id", "date", "active_duration_days"])

        if not consistency_df.is_empty():
            df = df.join(
                consistency_df.select(["customer_id", "trade_regularity_score"]),
                on="customer_id",
                how="left"
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias("trade_regularity_score"))

        df = df.with_columns(
            [
                pl.col("active_duration_days").fill_null(0.0),
                pl.col("trade_regularity_score").fill_null(0.0)
            ]
        )

        df = df.with_columns(
            (pl.col("active_duration_days") / 1095.0).clip(0, 1).alias("longevity_score"), # Max score at 3 years
            pl.col("trade_regularity_score").alias("engagement_score")
        )

        w_long, w_eng = 0.4, 0.6
        
        df = df.with_columns(
            (
                pl.col("longevity_score") * w_long +
                pl.col("engagement_score") * w_eng
            ).clip(0, 1).alias("dim_relationship")
        )

        return df.select(["customer_id", "date", "dim_relationship"])
