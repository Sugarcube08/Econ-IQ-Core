import polars as pl
from loguru import logger

from core.config.settings import settings
from core.schemas.intelligence import AnalysisContext


class CadenceEngine:
    """
    Infers the behavioral rhythm class based on the MEDIAN and STDDEV of gaps
    between significant events (sales).
    """

    def compute(self, ledger_df: pl.DataFrame, context: AnalysisContext) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "median_gap": pl.Float64,
            "stddev_gap": pl.Float64,
            "sale_count": pl.Int64,
            "cadence_class": pl.Utf8,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing behavioral cadence")

        # Only care about SALES for behavioral rhythm
        sales_df = ledger_df.filter(pl.col("event_type") == "SALE").sort(["customer_id", "event_date"])

        # Calculate gap in days between consecutive sales
        gaps_df = sales_df.with_columns(
            [
                (pl.col("event_date").dt.date() - pl.col("event_date").dt.date().shift(1))
                .dt.total_days()
                .over("customer_id")
                .alias("gap_days")
            ]
        ).filter(pl.col("gap_days").is_not_null())

        # Aggregate cadence metrics
        cadence_stats = gaps_df.group_by("customer_id").agg(
            [
                pl.col("gap_days").median().alias("median_gap"),
                pl.col("gap_days").std().alias("stddev_gap"),
                (pl.len() + 1).alias("sale_count"),  # Number of sales = number of gaps + 1
            ]
        )

        # Assign Cadence Classes
        min_events = settings.CADENCE_MIN_EVENTS
        stddev_mult = settings.CADENCE_STDDEV_MULTIPLIER

        cadence_stats = cadence_stats.with_columns(
            pl.when(pl.col("sale_count") < min_events)
            .then(pl.lit("SPARSE_ACTIVITY"))
            .when(pl.col("stddev_gap") > (pl.col("median_gap") * stddev_mult))
            .then(pl.lit("HIGH_VARIANCE"))
            # Rough proxy for seasonal: high median gap but low relative stddev
            .when((pl.col("median_gap") > 60) & (pl.col("stddev_gap") < pl.col("median_gap")))
            .then(pl.lit("SEASONAL"))
            .when(pl.col("stddev_gap") <= (pl.col("median_gap") * stddev_mult))
            .then(pl.lit("STABLE_CADENCE"))
            .otherwise(pl.lit("IRREGULAR"))
            .alias("cadence_class")
        )

        return cadence_stats
