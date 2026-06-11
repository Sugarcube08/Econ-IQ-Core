import polars as pl
from loguru import logger


class MetaScoreEngine:
    """
    Computes Meta Scores purely from the 8 Dimensions.
    Prevents circular dependencies and duplicate penalties.
    """
    def compute(self, dimensions_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8, 
            "date": pl.Date, 
            "risk_score": pl.Float64,
            "growth_score": pl.Float64,
            "opportunity_score": pl.Float64,
            "trust_score": pl.Float64,
            "health_score": pl.Float64,
            "strategic_value_score": pl.Float64,
            "stability_score": pl.Float64,
        }
        if dimensions_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Meta Scores from 12 Dimensions")

        df = dimensions_df.select(
            [
                "customer_id",
                "date",
                "dim_activity",
                "dim_discipline",
                "dim_credit",
                "dim_relationship",
                "dim_product",
                "dim_friction",
                "dim_growth",
                "dim_stability",
                "dim_value",
                "dim_concentration",
                "dim_payment_mode",
                "dim_maturity"
            ]
        )

        # Fill neutral defaults
        df = df.with_columns(
            [
                pl.col("dim_activity").fill_null(0.0),
                pl.col("dim_discipline").fill_null(0.0),
                pl.col("dim_credit").fill_null(0.5),
                pl.col("dim_relationship").fill_null(0.0),
                pl.col("dim_product").fill_null(0.5),
                pl.col("dim_friction").fill_null(1.0),
                pl.col("dim_growth").fill_null(0.5),
                pl.col("dim_stability").fill_null(0.5),
                pl.col("dim_value").fill_null(0.0),
                pl.col("dim_concentration").fill_null(0.5),
                pl.col("dim_payment_mode").fill_null(0.5),
                pl.col("dim_maturity").fill_null(0.0)
            ]
        )

        # 1. Risk Score: Creditworthiness (High = Safe)
        df = df.with_columns(
            (
                pl.col("dim_discipline") * 0.35 +
                pl.col("dim_credit") * 0.35 +
                pl.col("dim_friction") * 0.15 +
                pl.col("dim_stability") * 0.15
            ).clip(0, 1).alias("risk_score")
        )

        # 2. Growth Score: Scaling potential
        df = df.with_columns(
            (
                pl.col("dim_growth") * 0.40 +
                pl.col("dim_activity") * 0.30 +
                pl.col("dim_concentration") * 0.15 + # Portfolio diversity
                pl.col("dim_value") * 0.15
            ).clip(0, 1).alias("growth_score")
        )

        # 3. Opportunity Score: Upsell value
        df = df.with_columns(
            (
                pl.col("dim_growth") * 0.40 +
                pl.col("dim_activity") * 0.40 +
                pl.col("dim_value") * 0.20
            ).clip(0, 1).alias("opportunity_score")
        )

        # 4. Trust Score: Terms & Conditions reliability
        df = df.with_columns(
            (
                pl.col("dim_discipline") * 0.40 +
                pl.col("dim_stability") * 0.30 +
                pl.col("dim_relationship") * 0.20 +
                pl.col("dim_payment_mode") * 0.10
            ).clip(0, 1).alias("trust_score")
        )

        # 5. Health Score: Overall account condition
        df = df.with_columns(
            (
                pl.col("dim_discipline") * 0.30 +
                pl.col("dim_activity") * 0.30 +
                pl.col("dim_friction") * 0.20 +
                pl.col("dim_stability") * 0.20
            ).clip(0, 1).alias("health_score")
        )

        # 6. Strategic Value Score: Priority servicing
        df = df.with_columns(
            (
                pl.col("dim_value") * 0.50 +
                pl.col("dim_relationship") * 0.30 +
                pl.col("dim_maturity") * 0.20
            ).clip(0, 1).alias("strategic_value_score")
        )

        # 7. Stability Score: Forecast reliability
        df = df.with_columns(
            (
                pl.col("dim_stability") * 0.50 +
                pl.col("dim_maturity") * 0.30 +
                pl.col("dim_discipline") * 0.20
            ).clip(0, 1).alias("stability_score")
        )

        return df.select(
            [
                "customer_id", 
                "date", 
                "risk_score", 
                "growth_score", 
                "opportunity_score", 
                "trust_score",
                "health_score",
                "strategic_value_score",
                "stability_score"
            ]
        )
