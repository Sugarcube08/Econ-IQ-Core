from datetime import UTC, datetime

import polars as pl
from loguru import logger


class OpportunityEngine:
    """
    Opportunity Engine v2: Computes B2B customer opportunity scores.
    Formula: OS = SRI * (0.30 * PortalEngagement + 0.50 * CategoryGapScore + 0.20 * (1 - CartAbandonment))
    """

    def compute(
        self,
        features_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "opportunity_score": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing Opportunity Score v2")

        # 1. Base details from features
        df = features_df.sort("date").group_by("customer_id").tail(1)

        # Fill nulls
        df = df.with_columns(
            [
                pl.col("events_window").fill_null(1),
                pl.col("participation_density").fill_null(0.0),
            ]
        )

        # 2. Check for optional columns, otherwise use safe, transaction-derived defaults
        # Portal Engagement proxy: based on participation density, default to 0.7 if missing
        if "portal_engagement" in df.columns:
            df = df.with_columns(pl.col("portal_engagement").fill_null(0.7).alias("portal_engagement"))
        else:
            df = df.with_columns(
                ((pl.col("participation_density") * 0.5) + 0.5).clip(0, 1).alias("portal_engagement")
            )

        # Category Gap Score: default to 0.5 if missing
        if "category_gap_score" in df.columns:
            df = df.with_columns(pl.col("category_gap_score").fill_null(0.5).alias("category_gap_score"))
        else:
            df = df.with_columns(pl.lit(0.5).alias("category_gap_score"))

        # Cart Abandonment: default to 0.1 (low abandonment) if missing
        if "cart_abandonment" in df.columns:
            df = df.with_columns(pl.col("cart_abandonment").fill_null(0.1).alias("cart_abandonment"))
        else:
            df = df.with_columns(pl.lit(0.1).alias("cart_abandonment"))

        # 3. Compute Signal Reliability Index (SRI)
        # SRI scales down scores for customers with very low event density to avoid noise
        sri = (
            pl.when(pl.col("events_window") >= 5)
            .then(1.0)
            .otherwise(0.5 + 0.1 * pl.col("events_window"))
        ).alias("sri")

        df = df.with_columns(sri)

        # 4. Apply Weights
        w1, w2, w3 = 0.30, 0.50, 0.20
        df = df.with_columns(
            (
                pl.col("sri")
                * (
                    (pl.col("portal_engagement") * w1)
                    + (pl.col("category_gap_score") * w2)
                    + ((1.0 - pl.col("cart_abandonment")) * w3)
                )
            )
            .clip(0, 1)
            .alias("opportunity_score")
        )

        # Anchor date
        if "date" not in df.columns or df["date"].null_count() == df.height:
            df = df.with_columns(pl.lit(datetime.now(UTC).date()).alias("date"))

        return df.select(["customer_id", "date", "opportunity_score"])
