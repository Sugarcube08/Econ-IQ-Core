import polars as pl


class DisciplineDimensionEngine:
    """
    Dimension 2: Financial Discipline
    Focus: Payment reliability and promptness.
    """
    def compute(self, settlement_df: pl.DataFrame, rhythm_df: pl.DataFrame, org_metrics: dict | None = None) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_discipline": pl.Float64}
        if settlement_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        df = settlement_df.select(["customer_id", "avg_repayment_days", "date"])

        if not rhythm_df.is_empty():
            df = df.join(
                rhythm_df.select(["customer_id", "repayment_regularity_score", "repayment_fragmentation"]),
                on="customer_id",
                how="left"
            )
        else:
            df = df.with_columns(
                pl.lit(1.0).alias("repayment_regularity_score"),
                pl.lit(1.0).alias("repayment_fragmentation")
            )

        df = df.with_columns(
            [
                pl.col("avg_repayment_days").fill_null(180.0),
                pl.col("repayment_regularity_score").fill_null(0.0),
                pl.col("repayment_fragmentation").fill_null(1.0),
            ]
        )

        # Sub-scores
        df = df.with_columns(
            pl.when(pl.col("avg_repayment_days") <= 45.0)
            .then(1.0)
            .otherwise((1.0 - ((pl.col("avg_repayment_days") - 45.0) / 135.0)).clip(0, 1))
            .alias("promptness_score"),
            (1.0 - (pl.col("repayment_regularity_score") * 0.5).clip(0, 1)).alias("reliability_score"),
            pl.when(pl.col("repayment_fragmentation") <= 1.0)
            .then(1.0)
            .otherwise((1.0 - ((pl.col("repayment_fragmentation") - 1.0) / 4.0)).clip(0, 1))
            .alias("fragmentation_score")
        )

        # Dimension Score
        w_prompt, w_rel, w_frag = 0.5, 0.3, 0.2
        
        df = df.with_columns(
            (
                pl.col("promptness_score") * w_prompt +
                pl.col("reliability_score") * w_rel +
                pl.col("fragmentation_score") * w_frag
            ).clip(0, 1).alias("dim_discipline")
        )

        return df.select(["customer_id", "date", "dim_discipline"])
