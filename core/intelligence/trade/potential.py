import polars as pl
from loguru import logger


class TradePotentialEngine:
    """
    Estimates sustainable commercial capacity based on the fusion of
    proven trade regularity and financial settlement discipline.
    """

    def compute_potential(
        self,
        consistency_df: pl.DataFrame,
        settlement_df: pl.DataFrame,
        pressure_df: pl.DataFrame,
        stress_df: pl.DataFrame,
    ) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "sustainable_potential_score": pl.Float64}
        if consistency_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing sustainable commercial trade potential")

        # 1. Join all components
        df = consistency_df.join(settlement_df, on="customer_id", how="left")
        df = df.join(pressure_df, on="customer_id", how="left")

        # Use only the LATEST stress score for sustainable potential (summary metric)
        latest_stress = stress_df.sort("date").group_by("customer_id").tail(1).select(["customer_id", "stress_score"])
        df = df.join(latest_stress, on="customer_id", how="left")

        # 2. Discipline Multiplier (The "Sustainability" Anchor)
        # <30d: 1.0 | 30-60d: 0.8 | 60-90d: 0.4 | 90d+: 0.1
        df = df.with_columns(
            pl.when(pl.col("avg_repayment_days") < 30)
            .then(pl.lit(1.0))
            .when(pl.col("avg_repayment_days") < 60)
            .then(pl.lit(0.8))
            .when(pl.col("avg_repayment_days") < 90)
            .then(pl.lit(0.4))
            .otherwise(pl.lit(0.1))
            .alias("discipline_multiplier")
        )

        # 3. Final Sustainable Potential Formula
        # Fuses regularity (proven rhythm) with discipline (financial capacity)
        # capped by pressure and risk.
        df = df.with_columns(
            (
                pl.col("trade_regularity_score")
                * pl.col("discipline_multiplier")
                * (1.0 - pl.col("exposure_pressure_score") / 2.0).clip(0.1, 1.0)
                * (1.0 - pl.col("stress_score")).clip(0, 1)
            ).alias("sustainable_potential_score")
        )

        return df.select(["customer_id", "sustainable_potential_score"])
