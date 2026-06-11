import polars as pl
from loguru import logger


class ProductDimensionEngine:
    """
    Dimension 5: Product Behavior
    Focus: Catalog penetration and concentration risk.
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_product": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Dimension 5: Product Behavior")

        df = features_df.select(["customer_id", "date"])

        # Placeholder: Assume 0.5 until product category features are fully materialized in FeatureEngineer
        df = df.with_columns(pl.lit(0.5).alias("dim_product"))

        return df.select(["customer_id", "date", "dim_product"])
