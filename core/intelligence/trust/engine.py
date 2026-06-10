import polars as pl
from loguru import logger


class TrustEngine:
    """
    Computes Deterministic Commercial Behavioral Intelligence.
    Fuses 4 pillars into a single confidence-weighted score.
    """

    def compute(
        self,
        purchase_df: pl.DataFrame,
        payment_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "trust_score": pl.Float64,
            "raw_trust": pl.Float64,
        }
        if purchase_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Fusing 2 deterministic pillars into final behavioral intelligence")

        # 1. Join both behavioral pillars
        df = purchase_df.select(["customer_id", "date", "purchase_behavior_score"])

        if not payment_df.is_empty():
            df = df.join(payment_df.select(["customer_id", "payment_behavior_score"]), on="customer_id", how="left")
        else:
            df = df.with_columns(pl.lit(0.0).alias("payment_behavior_score"))

        # Fill nulls for safe math
        df = df.with_columns(
            [
                pl.col("purchase_behavior_score").fill_null(0.0),
                pl.col("payment_behavior_score").fill_null(0.0),
            ]
        )

        from core.policy.manager import policy_manager
        policy = policy_manager.policy.trust

        # 2. Final Deterministic Fusion (dynamic policy-driven weights)
        df = df.with_columns(
            (
                (pl.col("purchase_behavior_score") * policy.purchase_weight)
                + (pl.col("payment_behavior_score") * policy.payment_weight)
            ).alias("raw_trust")
        )

        df = df.with_columns(pl.col("raw_trust").alias("trust_score"))

        return df.select(["customer_id", "date", "trust_score", "raw_trust"])
