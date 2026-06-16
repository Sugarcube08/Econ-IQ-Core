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
            "credit_score": pl.Float64,
            "collection_score": pl.Float64,
            "relationship_score": pl.Float64,
        }
        if dimensions_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


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
                "dim_stability"
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
                pl.col("dim_stability").fill_null(0.5)
            ]
        )

        # 1. Health Score: Overall account condition
        # Health = 0.40 * Activity + 0.35 * (1 - Friction) + 0.25 * Stability
        df = df.with_columns(
            (
                pl.col("dim_activity") * 0.40 +
                pl.col("dim_friction") * 0.35 +
                pl.col("dim_stability") * 0.25
            ).clip(0, 1).alias("health_score")
        )

        # 2. Risk Score: Credit default and operational trade risk (High = Risky/Bad)
        # Risk = 0.40 * (1 - Credit) + 0.40 * (1 - Discipline) + 0.20 * (1 - Stability)
        df = df.with_columns(
            (
                (1.0 - pl.col("dim_credit")) * 0.40 +
                (1.0 - pl.col("dim_discipline")) * 0.40 +
                (1.0 - pl.col("dim_stability")) * 0.20
            ).clip(0, 1).alias("risk_score")
        )

        # 3. Growth Score: Scaling potential
        # Growth = 0.50 * Growth + 0.30 * Product + 0.20 * Activity
        df = df.with_columns(
            (
                pl.col("dim_growth") * 0.50 +
                pl.col("dim_product") * 0.30 +
                pl.col("dim_activity") * 0.20
            ).clip(0, 1).alias("growth_score")
        )

        # 4. Trust Score: Terms compliance reliability
        # Trust = 0.50 * Discipline + 0.30 * Relationship + 0.20 * Stability
        df = df.with_columns(
            (
                pl.col("dim_discipline") * 0.50 +
                pl.col("dim_relationship") * 0.30 +
                pl.col("dim_stability") * 0.20
            ).clip(0, 1).alias("trust_score")
        )

        # 5. Opportunity Score: Upsell value
        # Opportunity = 0.50 * (1 - Product) + 0.30 * Growth + 0.20 * Relationship
        df = df.with_columns(
            (
                (1.0 - pl.col("dim_product")) * 0.50 +
                pl.col("dim_growth") * 0.30 +
                pl.col("dim_relationship") * 0.20
            ).clip(0, 1).alias("opportunity_score")
        )

        # 6. Credit Score: Approved risk limit allocation potential (High = Good/Safe for limits)
        # Credit = 0.40 * Trust + 0.40 * (1 - Risk) + 0.20 * Activity
        df = df.with_columns(
            (
                pl.col("trust_score") * 0.40 +
                (1.0 - pl.col("risk_score")) * 0.40 +
                pl.col("dim_activity") * 0.20
            ).clip(0, 1).alias("credit_score")
        )

        # 7. Collection Score: Recovery priority and speed index
        # Collection = 0.50 * (1 - Discipline) + 0.30 * Risk + 0.20 * Activity
        df = df.with_columns(
            (
                (1.0 - pl.col("dim_discipline")) * 0.50 +
                pl.col("risk_score") * 0.30 +
                pl.col("dim_activity") * 0.20
            ).clip(0, 1).alias("collection_score")
        )

        # 8. Relationship Score: Partnership longevity and tenure
        # Relationship = 0.40 * Relationship + 0.40 * Stability + 0.20 * Activity
        df = df.with_columns(
            (
                pl.col("dim_relationship") * 0.40 +
                pl.col("dim_stability") * 0.40 +
                pl.col("dim_activity") * 0.20
            ).clip(0, 1).alias("relationship_score")
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
                "credit_score",
                "collection_score",
                "relationship_score"
            ]
        )

