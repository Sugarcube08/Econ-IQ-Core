from datetime import UTC, datetime

import polars as pl
from loguru import logger


class RelationshipEngine:
    """
    Relationship Engine v2: Computes B2B customer relationship scores.
    Formula: RLS = 0.40 * TenureScore + 0.40 * CooperationScore + 0.20 * InteractionDensity
    """

    def compute(
        self,
        features_df: pl.DataFrame,
        consistency_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "relationship_score": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Base details from features
        df = features_df.sort("date").group_by("customer_id").tail(1)

        # 2. Join consistency
        if not consistency_df.is_empty():
            df = df.join(
                consistency_df.select(["customer_id", "trade_regularity_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(0.5).alias("trade_regularity_score"))

        # Fill nulls
        df = df.with_columns(
            [
                pl.col("active_duration_days").fill_null(0),
                pl.col("penalty_window").fill_null(0.0),
                pl.col("sales_window").fill_null(0.0),
                pl.col("events_window").fill_null(1),
                pl.col("trade_regularity_score").fill_null(0.5),
            ]
        )

        # 3. Compute Subfactors
        # Subfactor 1: Tenure Score (Longevity in years, normalized to 3 years / 1095 days)
        df = df.with_columns(
            (pl.col("active_duration_days") / 1095.0).clip(0, 1).alias("tenure_score")
        )

        # Subfactor 2: Cooperation Score (proxy: 1 - return friction, i.e., penalty_window / sales_window)
        # Resilient default: if sales_window is 0, cooperation is 1.0 (no friction)
        df = df.with_columns(
            pl.when(pl.col("sales_window") > 0.0)
            .then(1.0 - (pl.col("penalty_window") / pl.col("sales_window")).clip(0.0, 1.0))
            .otherwise(1.0)
            .alias("cooperation_score")
        )

        # Subfactor 3: Interaction Density (proxy: average transaction frequency)
        # E.g. events_window / active_duration_days normalized to 1 event every 5 days (0.2 density)
        df = df.with_columns(
            pl.when(pl.col("active_duration_days") > 0)
            .then(((pl.col("events_window") / pl.col("active_duration_days")) / 0.2).clip(0, 1))
            .otherwise(1.0)
            .alias("interaction_density")
        )

        # 4. Apply Weights
        w1, w2, w3 = 0.40, 0.40, 0.20
        df = df.with_columns(
            (
                (pl.col("tenure_score") * w1)
                + (pl.col("cooperation_score") * w2)
                + (pl.col("interaction_density") * w3)
            )
            .clip(0, 1)
            .alias("relationship_score")
        )

        # Anchor date
        if "date" not in df.columns or df["date"].null_count() == df.height:
            df = df.with_columns(pl.lit(datetime.now(UTC).date()).alias("date"))

        return df.select(["customer_id", "date", "relationship_score"])
