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

        logger.debug("PROCESSING | Computing longitudinal rolling features", extra={"window": context.window_str})

        # MANDATORY SCHEMA ALIGNMENT: Ensure all required columns exist before group-by
        required_cols = {
            "amount": pl.Float64,
            "event_type": pl.Utf8,
            "discount_amount": pl.Float64,
            "rg_responsibility": pl.Utf8,
            "behavioral_penalty_weight": pl.Float64,
            "product_category": pl.Utf8,
            "product_name": pl.Utf8,
            "return_reason": pl.Utf8,
            "payment_mode": pl.Utf8,
            "registration_date": pl.Date,
            "business_type": pl.Utf8,
            "credit_limit": pl.Float64,
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

        # 1. Propagate static metadata (from OPENING_BALANCE or any row)
        # This ensures registration_date and business_type are available on every daily row after group-by
        ledger_df = ledger_df.sort(["customer_id", "event_date"]).with_columns(
            [
                pl.col("registration_date").forward_fill().backward_fill().over("customer_id"),
                pl.col("business_type").forward_fill().backward_fill().over("customer_id"),
                pl.col("credit_limit").forward_fill().backward_fill().over("customer_id"),
            ]
        )

        # 2. Standardize and Aggregate Daily
        daily_df = (
            ledger_df.sort(["customer_id", "event_date"])
            .group_by(["customer_id", pl.col("event_date").cast(pl.Date).alias("date")])
            .agg(
                [
                    pl.col("amount").filter(pl.col("event_type") == "SALE").sum().alias("daily_sales"),
                    pl.col("amount").filter(pl.col("event_type") == "PAYMENT").sum().alias("daily_payments"),
                    pl.col("discount_amount").sum().alias("daily_discounts"),
                    pl.col("amount").filter(pl.col("event_type") == "RETURN").sum().alias("daily_returns_value"),
                    pl.len().alias("daily_events"),
                    (pl.col("event_type") == "SALE").sum().alias("daily_sales_events"),
                    (pl.col("event_type") == "PAYMENT").sum().alias("daily_payments_events"),
                    (pl.col("event_type") == "RETURN").sum().alias("daily_returns_events"),
                    # Product diversity
                    pl.col("product_category").filter(pl.col("event_type") == "SALE").n_unique().alias("daily_categories"),
                    pl.col("product_name").filter(pl.col("event_type") == "SALE").n_unique().alias("daily_products"),
                    # Payment modes
                    pl.col("payment_mode").filter(pl.col("event_type") == "PAYMENT").alias("daily_payment_modes"),
                    # Static Metadata (Take first as they are propagated)
                    pl.col("registration_date").first().alias("registration_date"),
                    pl.col("business_type").first().alias("business_type"),
                    pl.col("credit_limit").first().alias("credit_limit"),
                    # Track latest purchase date
                    pl.col("event_date").filter(pl.col("event_type") == "SALE").max().alias("last_purchase_date_daily"),
                ]
            )
            .sort(["customer_id", "date"])
        )

        # 3. Real-time Anchor
        if context.end_date:
            unique_customers = daily_df.select("customer_id").unique()
            anchor_df = unique_customers.with_columns(
                [
                    pl.lit(context.end_date).alias("date"),
                    pl.lit(0.0).alias("daily_sales"),
                    pl.lit(0.0).alias("daily_payments"),
                    pl.lit(0.0).alias("daily_discounts"),
                    pl.lit(0.0).alias("daily_returns_value"),
                    pl.lit(0).alias("daily_events"),
                    pl.lit(0).cast(pl.UInt32).alias("daily_sales_events"),
                    pl.lit(0).cast(pl.UInt32).alias("daily_payments_events"),
                    pl.lit(0).cast(pl.UInt32).alias("daily_returns_events"),
                    pl.lit(0).cast(pl.UInt32).alias("daily_categories"),
                    pl.lit(0).cast(pl.UInt32).alias("daily_products"),
                    pl.lit([]).cast(pl.List(pl.Utf8)).alias("daily_payment_modes"),
                    pl.lit(None).cast(pl.Date).alias("registration_date"),
                    pl.lit(None).cast(pl.Utf8).alias("business_type"),
                    pl.lit(None).cast(pl.Float64).alias("credit_limit"),
                    pl.lit(None).cast(pl.Date).alias("last_purchase_date_daily"),
                ]
            )
            daily_df = pl.concat([daily_df, anchor_df], how="diagonal_relaxed").unique(
                subset=["customer_id", "date"], keep="first"
            ).sort(["customer_id", "date"])
            
            # Re-fill static metadata for anchor row
            daily_df = daily_df.sort(["customer_id", "date"]).with_columns(
                [
                    pl.col("registration_date").forward_fill().backward_fill().over("customer_id"),
                    pl.col("business_type").forward_fill().backward_fill().over("customer_id"),
                    pl.col("credit_limit").forward_fill().backward_fill().over("customer_id"),
                ]
            )

        # 4. Global History Logic
        daily_df = daily_df.with_columns(
            pl.col("last_purchase_date_daily").cum_max().forward_fill().over("customer_id").alias("abs_last_purchase")
        )

        # 5. Dynamic Longitudinal Windowing
        window_str = context.window_str
        
        final_features = (
            daily_df.sort("date")
            .rolling("date", period=window_str, group_by="customer_id")
            .agg(
                [
                    pl.col("daily_sales").sum().alias("sales_window"),
                    pl.col("daily_payments").sum().alias("payments_window"),
                    pl.col("daily_returns_value").sum().alias("returns_value_window"),
                    pl.col("daily_events").sum().alias("events_window"),
                    pl.col("daily_sales_events").sum().alias("sales_events_window"),
                    pl.col("daily_payments_events").sum().alias("payments_events_window"),
                    pl.col("daily_returns_events").sum().alias("returns_events_window"),
                    # Diversification
                    pl.col("daily_categories").sum().alias("category_diversity_count"),
                    pl.col("daily_products").sum().alias("product_diversity_count"),
                    # Payment Behavior
                    pl.col("daily_payment_modes").flatten().alias("payment_modes_window"),
                    # Maturity
                    pl.col("registration_date").first().alias("registration_date"),
                    pl.col("business_type").first().alias("business_type"),
                    pl.col("credit_limit").first().alias("credit_limit_window"),
                    pl.col("daily_events").filter(pl.col("daily_sales") > 0).count().alias("purchase_days"),
                    (pl.col("date").max() - pl.col("date").min()).dt.total_days().alias("active_duration_days"),
                    pl.col("abs_last_purchase").last().alias("last_purchased_at"),
                ]
            )
        )

        # 6. Behavioral Intelligence Normalization
        final_features = final_features.with_columns(
            [
                (pl.col("sales_window").fill_null(0.0) + 1.0).log10().alias("log_sales_scale"),
                (
                    pl.col("purchase_days").fill_null(0.0)
                    / pl.max_horizontal(pl.col("active_duration_days").fill_null(0.0), 1.0)
                )
                .clip(0, 1)
                .alias("participation_density"),
                # Net Revenue
                (pl.col("sales_window") - pl.col("returns_value_window")).alias("net_revenue_window"),
                # Maturity Age
                (pl.col("date") - pl.col("registration_date")).dt.total_days().fill_null(0).alias("business_age_days"),
            ]
        )

        # 7. Join with recent window features
        recent_window_days = max(14, int(context.window_days * 0.2))
        recent_window_str = f"{recent_window_days}d"

        recent_features = (
            daily_df.sort("date")
            .rolling("date", period=recent_window_str, group_by="customer_id")
            .agg(
                [
                    pl.col("daily_sales").sum().alias("sales_recent"),
                    pl.col("daily_events").sum().alias("events_recent"),
                    pl.col("daily_sales_events").sum().alias("sales_events_recent"),
                ]
            )
        )

        final_features = final_features.join(recent_features, on=["customer_id", "date"], how="left")

        # Alias returns_value_window as penalty_window for backward compatibility with downstream engines
        if "returns_value_window" in final_features.columns:
            final_features = final_features.with_columns(
                pl.col("returns_value_window").alias("penalty_window")
            )

        # 3. Apply Temporal Context Filters AFTER rolling to preserve history
        if context.start_date:
            final_features = final_features.filter(pl.col("date") >= context.start_date)
        if context.end_date:
            final_features = final_features.filter(pl.col("date") <= context.end_date)

        return final_features
