import polars as pl
from datetime import date, timedelta
from loguru import logger


class MLLabelGenerator:
    """
    Generates historical labels/targets (y) for model training.
    """

    def generate_churn_labels(self, ledger_df: pl.DataFrame, observation_date: date, lead_window_days: int = 90) -> pl.DataFrame:
        """
        Generates binary labels for churn: 1 if customer has no purchase events
        within lead_window_days after the observation_date, 0 otherwise.
        """
        logger.info(f"Generating churn labels observation_date={observation_date} | lead_window={lead_window_days}d")
        if ledger_df.is_empty():
            return pl.DataFrame(schema={"customer_id": pl.Utf8, "label_churn": pl.Int64})

        # Filter events in lead window
        end_lead_date = observation_date + timedelta(days=lead_window_days)
        
        active_in_lead = (
            ledger_df.filter(
                (pl.col("event_date").dt.date() > observation_date) & 
                (pl.col("event_date").dt.date() <= end_lead_date) &
                (pl.col("event_type") == "SALE")
            )
            .select("customer_id")
            .unique()
            .with_columns(pl.lit(1).alias("has_purchased"))
        )

        unique_customers = ledger_df.select("customer_id").unique()
        
        labels_df = unique_customers.join(active_in_lead, on="customer_id", how="left").with_columns(
            pl.when(pl.col("has_purchased").is_null())
            .then(1) # Churned (no purchase found)
            .otherwise(0)
            .alias("label_churn")
        ).drop("has_purchased")

        return labels_df

    def generate_default_labels(self, ledger_df: pl.DataFrame, observation_date: date, lead_window_days: int = 90, dpd_threshold: int = 60) -> pl.DataFrame:
        """
        Generates default labels: 1 if customer records days past due (DPD) exceeding threshold
        within lead_window_days after the observation_date, 0 otherwise.
        """
        logger.info(f"Generating default labels observation_date={observation_date} | dpd_threshold={dpd_threshold}")
        if ledger_df.is_empty():
            return pl.DataFrame(schema={"customer_id": pl.Utf8, "label_default": pl.Int64})

        end_lead_date = observation_date + timedelta(days=lead_window_days)
        
        # In B2B transaction systems, DPD is stored in metadata columns of EventLedger PAYMENT events.
        # We parse the metadata to determine delay.
        default_events = (
            ledger_df.filter(
                (pl.col("event_date").dt.date() > observation_date) & 
                (pl.col("event_date").dt.date() <= end_lead_date) &
                (pl.col("event_type") == "PAYMENT")
            )
            # Safe JSON/metadata parsing
            .with_columns(
                pl.col("metadata").struct.field("days_past_due").cast(pl.Int64).fill_null(0).alias("dpd")
            )
            .filter(pl.col("dpd") >= dpd_threshold)
            .select("customer_id")
            .unique()
            .with_columns(pl.lit(1).alias("has_defaulted"))
        )

        unique_customers = ledger_df.select("customer_id").unique()
        
        labels_df = unique_customers.join(default_events, on="customer_id", how="left").with_columns(
            pl.when(pl.col("has_defaulted").is_null())
            .then(0)
            .otherwise(1)
            .alias("label_default")
        ).drop("has_defaulted")

        return labels_df
