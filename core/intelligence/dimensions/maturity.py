import polars as pl
from loguru import logger


class MaturityDimensionEngine:
    """
    Dimension 12: Business Maturity
    Focus: Operational age and stage.
    """
    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        if features_df.is_empty():
            return pl.DataFrame({"customer_id": [], "date": [], "dim_maturity": []})

        logger.debug("Computing Dimension 12: Business Maturity")
        
        df = features_df.select(["customer_id", "date", "business_age_days", "active_duration_days"])

        # Age Score
        # Assume 5 years (1825 days) is full maturity
        df = df.with_columns(
            (pl.col("business_age_days") / 1825.0).clip(0, 1).alias("age_score"),
            (pl.col("active_duration_days") / 1095.0).clip(0, 1).alias("relationship_age_score")
        )

        w_age, w_rel = 0.5, 0.5
        
        df = df.with_columns(
            (
                pl.col("age_score") * w_age +
                pl.col("relationship_age_score") * w_rel
            ).clip(0, 1).alias("dim_maturity")
        )

        return df.select(["customer_id", "date", "dim_maturity"])
