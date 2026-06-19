import polars as pl


class GrowthDimensionEngine:
    """
    Dimension 7: Growth Dynamics
    Focus: Trajectory and improvement vectors.
    """
    def compute(self, features_df: pl.DataFrame, org_metrics: dict | None = None) -> pl.DataFrame:
        empty_schema = {"customer_id": pl.Utf8, "date": pl.Date, "dim_growth": pl.Float64}
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "sales_window", 
                "sales_recent", 
                "sales_events_window", 
                "sales_events_recent"
            ]
        )

        df = df.with_columns(
            [
                pl.col("sales_window").fill_null(0.0),
                pl.col("sales_recent").fill_null(0.0),
                pl.col("sales_events_window").fill_null(1),
                pl.col("sales_events_recent").fill_null(0),
            ]
        )

        # Recent is 20% of window (e.g. 73 days of 365). Neutral growth means recent = 20% of total.
        df = df.with_columns(
            pl.when(pl.col("sales_window") > 0)
            .then(((pl.col("sales_recent") / pl.col("sales_window")) / 0.20).clip(0, 2.0) / 2.0)
            .otherwise(0.0)
            .alias("revenue_growth_score"),
            
            pl.when(pl.col("sales_events_window") > 0)
            .then(((pl.col("sales_events_recent") / pl.col("sales_events_window")) / 0.20).clip(0, 2.0) / 2.0)
            .otherwise(0.0)
            .alias("frequency_growth_score")
        )

        w_rev, w_freq = 0.6, 0.4
        
        df = df.with_columns(
            (
                pl.col("revenue_growth_score") * w_rev +
                pl.col("frequency_growth_score") * w_freq
            ).clip(0, 1).alias("dim_growth")
        )

        return df.select(["customer_id", "date", "dim_growth"])
