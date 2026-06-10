import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class PurchaseBehaviorEngine:
    """
    Measures quality of commercial participation behavior.
    Prioritizes frequency + volume synergy and cadence stability.
    Suppresses whale favoritism.
    """

    def compute_score(
        self, features_df: pl.DataFrame, consistency_df: pl.DataFrame, context: AnalysisContext, org_metrics: dict | None = None
    ) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "purchase_behavior_score": pl.Float64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing deterministic purchase behavior intelligence")

        # Fallback for org metrics if not provided
        p95_billing = (org_metrics or {}).get("p95_billing", 500000.0)
        p95_density = (org_metrics or {}).get("p95_density", 0.4)

        # 1. Join features and consistency
        df = features_df.select(
            ["customer_id", "date", "sales_window", "sales_recent", "log_sales_scale", "participation_density"]
        )
        df = df.join(consistency_df, on="customer_id", how="left")

        # Fill nulls for safe math
        df = df.with_columns(
            [
                pl.col("log_sales_scale").fill_null(0.0),
                pl.col("participation_density").fill_null(0.0),
                pl.col("trade_regularity_score").fill_null(0.0),
            ]
        )

        # 2. Subfactor Extraction

        # Subfactor 2.1: Hybrid Billing Volume (35%)
        # Blend: 70% Relative to Org P95 | 30% Absolute Scale (₹1M benchmark)
        import math
        
        log_p95 = math.log10(max(p95_billing, 1000.0))
        # Relative component (70%)
        relative_volume = (pl.col("log_sales_scale") / log_p95).clip(0, 1)
        # Absolute component (30%) - Target ₹1,000,000 (log10 = 6.0)
        absolute_volume = (pl.col("log_sales_scale") / 6.0).clip(0, 1)
        
        billing_volume_score = (relative_volume * 0.70) + (absolute_volume * 0.30)

        # Subfactor 2.2: Relative Purchase Frequency (35%)
        # Benchmarked against Org P95 density
        purchase_frequency_score = (pl.col("participation_density") / max(p95_density, 0.05)).clip(0, 1)

        # Subfactor 2.3: Growth Trend (15%)
        # Smoothed longitudinal growth slope (Recent vs Window Velocity)
        # Using a safer growth ratio: (recent_daily_avg / window_daily_avg)
        window_days = context.window_days or 180
        recent_days = max(14, int(window_days * 0.2))
        
        df = df.with_columns(
            (pl.col("sales_window") / window_days).alias("window_velocity"),
            (pl.col("sales_recent") / recent_days).alias("recent_velocity"),
        )
        
        # Growth score: ratio of 1.0 is stable (0.5 score), 2.0 is high growth (1.0 score)
        growth_score = (
            (pl.col("recent_velocity") / pl.max_horizontal(pl.col("window_velocity"), 1.0))
            .map_elements(lambda x: 0.5 + (x - 1.0) * 0.5 if x >= 1.0 else x * 0.5)
            .clip(0, 1)
        )

        # Subfactor 2.4: Seasonal Stability (15%)
        # Proxy: Trade Regularity (Consistency of purchase intervals)
        seasonal_stability_score = pl.col("trade_regularity_score")

        # 3. Final Deterministic Fusion
        # Weights: Volume 35%, Frequency 35%, Growth 15%, Stability 15%
        df = df.with_columns(
            (
                (billing_volume_score * 0.35)
                + (purchase_frequency_score * 0.35)
                + (growth_score * 0.15)
                + (seasonal_stability_score * 0.15)
            ).alias("purchase_behavior_score")
        )

        return df.select(
            [
                "customer_id",
                "date",
                "purchase_behavior_score",
                billing_volume_score.alias("subfactor_billing_volume"),
                purchase_frequency_score.alias("subfactor_purchase_frequency"),
                growth_score.alias("subfactor_growth_trend"),
                seasonal_stability_score.alias("subfactor_seasonal_stability"),
            ]
        )
