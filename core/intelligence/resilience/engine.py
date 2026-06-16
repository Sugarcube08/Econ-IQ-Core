from datetime import UTC, datetime

import polars as pl
from loguru import logger


class ResilienceEngine:
    """
    Resilience Engine v2: Computes customer resilience.
    Formula: Resilience = Stability * (1 - Stress)
    Where:
      - Stability = 0.5 * TradeRegularity + 0.5 * PaymentConsistency
      - Stress = longitudinal stress score from StressEngine
    """

    def compute(
        self,
        features_df: pl.DataFrame,
        stress_df: pl.DataFrame,
        rhythm_df: pl.DataFrame,
        consistency_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "resilience_score": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Base details from features
        df = features_df.sort("date").group_by("customer_id").tail(1)

        # 2. Join stress score
        if not stress_df.is_empty():
            df = df.join(
                stress_df.select(["customer_id", "stress_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(0.0).alias("stress_score"))

        # 3. Join trade consistency
        if not consistency_df.is_empty():
            df = df.join(
                consistency_df.select(["customer_id", "trade_regularity_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(0.5).alias("trade_regularity_score"))

        # 4. Join payment rhythm consistency
        if not rhythm_df.is_empty():
            df = df.join(
                rhythm_df.select(["customer_id", "repayment_regularity_score"]),
                on="customer_id",
                how="left",
            )
        else:
            df = df.with_columns(pl.lit(1.0).alias("repayment_regularity_score"))

        # Fill nulls
        df = df.with_columns(
            [
                pl.col("stress_score").fill_null(0.0),
                pl.col("trade_regularity_score").fill_null(0.5),
                pl.col("repayment_regularity_score").fill_null(0.5),
            ]
        )

        # 5. Compute subfactors
        df = df.with_columns(
            (0.5 * pl.col("trade_regularity_score") + 0.5 * pl.col("repayment_regularity_score")).alias("stability_score")
        )

        df = df.with_columns(
            (pl.col("stability_score") * (1.0 - pl.col("stress_score"))).clip(0, 1).alias("resilience_score")
        )

        # Anchor date
        if "date" not in df.columns or df["date"].null_count() == df.height:
            df = df.with_columns(pl.lit(datetime.now(UTC).date()).alias("date"))

        return df.select(["customer_id", "date", "resilience_score"])
