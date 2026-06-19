import polars as pl


class ActivityDimensionEngine:
    """
    Dimension 1: Commercial Activity
    Focus: Buying velocity, frequency, and consistency.
    """
    def compute(self, features_df: pl.DataFrame, org_metrics: dict | None = None) -> pl.DataFrame:
        if features_df.is_empty():
            return pl.DataFrame({"customer_id": [], "date": [], "dim_activity": []})

        if org_metrics is None:
            org_metrics = {"p95_billing": 100000.0, "p95_density": 0.5, "avg_org_billing": 10000.0}
            
        p95_billing = max(100.0, org_metrics.get("p95_billing", 100000.0))
        p95_density = max(0.01, org_metrics.get("p95_density", 0.5))

        df = features_df.select(
            [
                "customer_id", 
                "date", 
                "sales_window", 
                "sales_events_window", 
                "participation_density",
                "log_sales_scale",
                "active_duration_days"
            ]
        )

        df = df.with_columns(
            [
                pl.col("sales_window").fill_null(0.0),
                pl.col("sales_events_window").fill_null(0),
                pl.col("participation_density").fill_null(0.0),
                pl.col("log_sales_scale").fill_null(0.0),
                pl.col("active_duration_days").fill_null(1.0)
            ]
        )

        import math
        df = df.with_columns(
            ((pl.col("sales_events_window") / pl.max_horizontal(pl.col("active_duration_days") / 30.0, 1.0)) / (p95_density * 30.0)).clip(0, 1).alias("freq_score"),
            ((pl.col("sales_window") + 1.0).log10() / math.log10(p95_billing + 1.0)).clip(0, 1).alias("vol_score"),
            (pl.col("participation_density") / p95_density).clip(0, 1).alias("consistency_score")
        )

        # Dimension Score: Weighted combination
        w_freq, w_vol, w_cons = 0.4, 0.3, 0.3
        
        df = df.with_columns(
            (
                pl.col("freq_score") * w_freq +
                pl.col("vol_score") * w_vol +
                pl.col("consistency_score") * w_cons
            ).clip(0, 1).alias("dim_activity")
        )

        return df.select(["customer_id", "date", "dim_activity"])
