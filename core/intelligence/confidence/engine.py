import math

import polars as pl

from core.schemas.intelligence import AnalysisContext


class ConfidenceEngine:
    """
    Computes multi-dimensional confidence scores longitudinally using AnalysisContext.
    """

    def compute(self, features_df: pl.DataFrame, context: AnalysisContext, org_metrics: dict | None = None) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "confidence_score": pl.Float64,
            "confidence_modifier": pl.Float64,
            "behavioral_confidence": pl.Float64,
            "observation_strength": pl.Float64,
            "evidence_density": pl.Float64,
            "observation_span": pl.Int64,
        }
        if features_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # Fallback for org metrics if not provided
        p95_billing = (org_metrics or {}).get("p95_billing", 500000.0)
        
        # Phase 8: Evidence Confidence Weighting
        # Goal: Prevent low-data or short-lived customers from appearing unrealistically strong.
        
        conf_df = features_df.with_columns(
            [
                # 1. Transactional Depth (Logarithmic scaling of event volume)
                # Target: 60+ events for full confidence
                ((pl.col("events_window") + 1.0).log10() / 1.78).clip(0, 1).alias("transactional_confidence"),
                
                # 2. Longitudinal Depth (Active participation days vs window duration)
                (pl.col("active_duration_days") / (context.window_days * 0.5)).clip(0, 1).alias("longitudinal_confidence"),
                
                # 3. Behavioral Density (Events per month)
                (pl.col("events_window") / (context.window_days / 30.0 * 4.0)).clip(0, 1).alias("evidence_density"),

                # 4. Volume Confidence (Absolute Commercial Weight)
                # Normalizes settled/purchase amount relative to org P95
                (pl.col("log_sales_scale") / math.log10(max(p95_billing, 1000.0))).clip(0, 1).alias("volume_confidence"),

                # 5. Activity Breadth (Months with activity)
                # Target: Activity in at least 6 unique months for full confidence
                # Approximation: active_duration_days / 30
                (pl.col("active_duration_days") / 180.0).clip(0, 1).alias("breadth_confidence"),
            ]
        )

        # 6. Final Confidence Fusion (Deterministic)
        # Weights: Transactional 30%, Longitudinal 20%, Density 10%, Volume 20%, Breadth 20%
        conf_df = conf_df.with_columns(
            (
                (pl.col("transactional_confidence") * 0.3)
                + (pl.col("longitudinal_confidence") * 0.2)
                + (pl.col("evidence_density") * 0.1)
                + (pl.col("volume_confidence") * 0.2)
                + (pl.col("breadth_confidence") * 0.2)
            ).alias("confidence_modifier")
        )

        conf_df = conf_df.with_columns(
            pl.col("confidence_modifier").alias("confidence_score"),
            pl.col("confidence_modifier").alias("behavioral_confidence"),
            pl.col("confidence_modifier").alias("observation_strength"),
            pl.lit(context.window_days).alias("observation_span"),
        )

        return conf_df.select(
            [
                "customer_id",
                "date",
                "confidence_score",
                "confidence_modifier",
                "behavioral_confidence",
                "observation_strength",
                "evidence_density",
                "observation_span",
                "transactional_confidence",
                "longitudinal_confidence",
                "volume_confidence",
                "breadth_confidence",
            ]
        )
