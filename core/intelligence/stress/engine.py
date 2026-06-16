import polars as pl
from loguru import logger


class StressEngine:
    """
    Computes customer stress scores longitudinally.
    """

    def compute(self, features_df: pl.DataFrame) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "stress_score": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        from core.policy.manager import policy_manager
        policy = policy_manager.policy.stress

        # stress = (returns / sales) * stress_rg_weight + (deficiency / sales) * stress_deficiency_weight
        stress_df = features_df.with_columns(
            [
                (pl.col("penalty_window") / pl.max_horizontal(pl.col("sales_window"), 100.0)).alias("rg_ratio"),
                (
                    (pl.col("sales_window") - pl.col("payments_window"))
                    / pl.max_horizontal(pl.col("sales_window"), 100.0)
                ).alias("deficiency"),
            ]
        )

        stress_df = stress_df.with_columns(
            pl.max_horizontal(
                pl.lit(0.0), pl.min_horizontal(pl.lit(1.0), (pl.col("rg_ratio") * policy.stress_rg_weight) + (pl.col("deficiency") * policy.stress_deficiency_weight))
            ).alias("stress_score")
        )

        return stress_df.select(["customer_id", "date", "stress_score"])
