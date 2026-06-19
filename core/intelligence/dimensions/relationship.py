import polars as pl


class RelationshipDimensionEngine:
    """
    Dimension 4: Relationship Quality
    Focus: Longevity, mutual dependence, and engagement.
    """
    def compute(self, features_df: pl.DataFrame, consistency_df: pl.DataFrame, org_metrics: dict | None = None) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_relationship": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        if org_metrics is None:
            org_metrics = {"p95_duration_days": 1095.0}
            
        p95_duration_days = max(180.0, org_metrics.get("p95_duration_days", 1095.0))

        df = features_df.select([
            "customer_id", 
            "date", 
            "active_duration_days",
            "sales_window",
            "penalty_window"
        ])

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
                pl.col("active_duration_days").fill_null(0.0),
                pl.col("trade_regularity_score").fill_null(0.5),
                pl.col("sales_window").fill_null(0.0),
                pl.col("penalty_window").fill_null(0.0),
            ]
        )

        # 1. Longevity Score
        df = df.with_columns(
            (pl.col("active_duration_days") / p95_duration_days).clip(0, 1).alias("longevity_score")
        )

        # 2. Cooperation Score (1 - return friction)
        df = df.with_columns(
            pl.when(pl.col("sales_window") > 0.0)
            .then(1.0 - (pl.col("penalty_window") / pl.col("sales_window")).clip(0.0, 1.0))
            .otherwise(1.0)
            .alias("cooperation_score")
        )

        # 3. Engagement Score (trade regularity)
        df = df.with_columns(
            pl.col("trade_regularity_score").alias("engagement_score")
        )

        # Dimension Score: Weighted combination of the three
        w_long, w_coop, w_eng = 0.4, 0.3, 0.3
        df = df.with_columns(
            (
                pl.col("longevity_score") * w_long +
                pl.col("cooperation_score") * w_coop +
                pl.col("engagement_score") * w_eng
            ).clip(0, 1).alias("dim_relationship")
        )

        return df.select(["customer_id", "date", "dim_relationship"])
