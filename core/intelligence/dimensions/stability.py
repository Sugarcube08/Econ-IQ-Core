import polars as pl
from loguru import logger


class StabilityDimensionEngine:
    """
    Dimension 8: Stability & Predictability (Consolidated: Stability + Maturity)
    Focus: Variance, operational cadence, and tenure.
    """
    def compute(self, features_df: pl.DataFrame, consistency_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_stability": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Dimension 8: Stability & Predictability")

        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "participation_density",
                "business_age_days",
                "active_duration_days"
            ]
        )

        if not consistency_df.is_empty():
            df = df.join(
                consistency_df.select(["customer_id", "trade_regularity_score"]),
                on="customer_id",
                how="left"
            )
        else:
            df = df.with_columns(pl.lit(0.5).alias("trade_regularity_score"))

        df = df.with_columns(
            [
                pl.col("participation_density").fill_null(0.0),
                pl.col("trade_regularity_score").fill_null(0.5),
                pl.col("business_age_days").fill_null(0),
                pl.col("active_duration_days").fill_null(0.0),
            ]
        )

        # Tenure / Maturity sub-scores
        df = df.with_columns(
            (pl.col("business_age_days") / 1825.0).clip(0, 1).alias("age_score"),
            (pl.col("active_duration_days") / 1095.0).clip(0, 1).alias("relationship_age_score")
        )

        # Stability sub-scores
        df = df.with_columns(
            pl.col("participation_density").alias("cadence_stability"),
            pl.col("trade_regularity_score").alias("variance_stability")
        )

        w_cadence, w_var, w_age, w_rel = 0.3, 0.3, 0.2, 0.2
        
        df = df.with_columns(
            (
                pl.col("cadence_stability") * w_cadence +
                pl.col("variance_stability") * w_var +
                pl.col("age_score") * w_age +
                pl.col("relationship_age_score") * w_rel
            ).clip(0, 1).alias("dim_stability")
        )

        return df.select(["customer_id", "date", "dim_stability"])
