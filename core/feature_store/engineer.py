import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class FeatureEngineer:
    def __init__(self):
        pass

    def compute_features(self, ledger_df: pl.DataFrame, context: AnalysisContext) -> pl.DataFrame:
        """
        Computes LONGITUDINAL rolling features using Polars dynamic group-by and AnalysisContext.
        """
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "sales_window": pl.Float64,
            "payments_window": pl.Float64,
            "discounts_window": pl.Float64,
            "penalty_window": pl.Float64,
            "events_window": pl.Int64,
            "active_duration_days": pl.Int64,
            "sales_recent": pl.Float64,
            "events_recent": pl.Int64,
            "last_purchased_at": pl.Date,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug(f"Computing longitudinal rolling features for window: {context.window_str}")

        # MANDATORY SCHEMA ALIGNMENT: Ensure all required columns exist before group-by
        required_cols = {
            "amount": pl.Float64,
            "event_type": pl.Utf8,
            "discount_amount": pl.Float64,
            "rg_responsibility": pl.Utf8,
            "behavioral_penalty_weight": pl.Float64,
        }
        for col, dtype in required_cols.items():
            if col not in ledger_df.columns:
                ledger_df = ledger_df.with_columns(pl.lit(None).cast(dtype).alias(col))

        # Fill nulls for critical columns
        ledger_df = ledger_df.with_columns(
            [
                pl.col("amount").fill_null(0.0),
                pl.col("discount_amount").fill_null(0.0),
                pl.col("rg_responsibility").fill_null(""),
                pl.col("behavioral_penalty_weight").fill_null(1.0),
            ]
        )

        # 1. Standardize and Aggregate Daily
        daily_df = (
            ledger_df.sort(["customer_id", "event_date"])
            .group_by(["customer_id", pl.col("event_date").cast(pl.Date).alias("date")])
            .agg(
                [
                    pl.col("amount").filter(pl.col("event_type") == "SALE").sum().alias("daily_sales"),
                    pl.col("amount").filter(pl.col("event_type") == "PAYMENT").sum().alias("daily_payments"),
                    pl.col("discount_amount").sum().alias("daily_discounts"),
                    # RG Score Simplification: capture raw worth/value of RGs returned
                    pl.col("amount")
                    .filter(pl.col("event_type") == "RETURN")
                    .sum()
                    .alias("daily_penalty_amount"),
                    pl.len().alias("daily_events"),
                    # Track latest purchase date in this day (already cleaned in ledger)
                    pl.col("event_date")
                    .filter(pl.col("event_type") == "SALE")
                    .max()
                    .alias("last_purchase_date_daily")
                ]
            )
            .sort(["customer_id", "date"])
        )

        # 2. Real-time Anchor (Deterministic State Freshness)
        # We ensure a row exists for context.end_date (usually 'today') to force 
        # rolling windows to reflect the current state (e.g., transition to inactive).
        if context.end_date:
            unique_customers = daily_df.select("customer_id").unique()
            anchor_df = unique_customers.with_columns(
                [
                    pl.lit(context.end_date).alias("date"),
                    pl.lit(0.0).alias("daily_sales"),
                    pl.lit(0.0).alias("daily_payments"),
                    pl.lit(0.0).alias("daily_discounts"),
                    pl.lit(0.0).alias("daily_penalty_amount"),
                    pl.lit(0).alias("daily_events"),
                    pl.lit(None).cast(pl.Date).alias("last_purchase_date_daily"),
                ]
            )
            # Merge and deduplicate (keep existing daily data if it exists for end_date)
            daily_df = pl.concat([daily_df, anchor_df], how="diagonal_relaxed").unique(
                subset=["customer_id", "date"], keep="first"
            ).sort(["customer_id", "date"])

        # 3. Global History Logic
        # Compute absolute last purchase date (cumulative max with forward fill)
        # This ensures last_purchased_at is system-absolute, not window-bound.
        daily_df = daily_df.with_columns(
            pl.col("last_purchase_date_daily")
            .cum_max()
            .forward_fill()
            .over("customer_id")
            .alias("abs_last_purchase")
        )

        # 4. Dynamic Longitudinal Windowing (Dual Window for Trajectory)
        window_str = context.window_str
        recent_window_days = max(14, int(context.window_days * 0.2))
        recent_window_str = f"{recent_window_days}d"

        logger.debug(f"Applying dual windows: {window_str} (Historical) and {recent_window_str} (Recent)")

        final_features = (
            daily_df.sort("date")
            .rolling("date", period=window_str, group_by="customer_id")
            .agg(
                [
                    pl.col("daily_sales").sum().alias("sales_window"),
                    pl.col("daily_payments").sum().alias("payments_window"),
                    pl.col("daily_discounts").sum().alias("discounts_window"),
                    pl.col("daily_penalty_amount").sum().alias("penalty_window"),
                    pl.col("daily_events").sum().alias("events_window"),
                    pl.col("daily_events").filter(pl.col("daily_sales") > 0).count().alias("purchase_days"),
                    (pl.col("date").max() - pl.col("date").min()).dt.total_days().alias("active_duration_days"),
                    # We take the last known absolute purchase timestamp in this window
                    pl.col("abs_last_purchase").last().alias("last_purchased_at"),
                ]
            )
        )

        # 3. Behavioral Intelligence Normalization (Deterministic)
        final_features = final_features.with_columns(
            [
                # Sustainable Scale (Log10 Normalization to prevent whale domination)
                (pl.col("sales_window").fill_null(0.0) + 1.0).log10().alias("log_sales_scale"),
                # Participation Density (Active purchase days vs total window duration)
                (
                    pl.col("purchase_days").fill_null(0.0)
                    / pl.max_horizontal(pl.col("active_duration_days").fill_null(0.0), 1.0)
                )
                .clip(0, 1)
                .alias("participation_density"),
            ]
        )

        # 4. Join with recent window features
        recent_features = (
            daily_df.sort("date")
            .rolling("date", period=recent_window_str, group_by="customer_id")
            .agg(
                [
                    pl.col("daily_sales").sum().alias("sales_recent"),
                    pl.col("daily_events").sum().alias("events_recent"),
                ]
            )
        )

        final_features = final_features.join(recent_features, on=["customer_id", "date"], how="left")

        # 3. Apply Temporal Context Filters AFTER rolling to preserve history
        if context.start_date:
            final_features = final_features.filter(pl.col("date") >= context.start_date)
        if context.end_date:
            final_features = final_features.filter(pl.col("date") <= context.end_date)

        return final_features
