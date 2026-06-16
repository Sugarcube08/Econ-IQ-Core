import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class LedgerReconstructionEngine:
    """
    Reconstructs the chronological financial state of a customer.
    Computes daily exposure, outstanding balances, and debit persistence.
    """

    def reconstruct_exposure(self, ledger_df: pl.DataFrame, context: AnalysisContext) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "date": pl.Date,
            "outstanding_balance": pl.Float64,
            "debit_persistence_days": pl.Int64,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Prepare Daily Delta
        # Sales (+) | Payments (-) | Returns (-)
        daily_delta = (
            ledger_df.sort(["customer_id", "event_date"])
            .with_columns(pl.col("event_date").dt.date().alias("date"))
            .group_by(["customer_id", "date"])
            .agg(
                [
                    pl.col("amount")
                    .filter(pl.col("event_type").is_in(["SALE", "OPENING_BALANCE"]))
                    .sum()
                    .fill_null(0.0)
                    .alias("daily_sales"),
                    pl.col("amount")
                    .filter(pl.col("event_type").is_in(["PAYMENT", "RETURN", "DISCOUNT"]))
                    .sum()
                    .fill_null(0.0)
                    .alias("daily_credits"),
                ]
            )
            .with_columns((pl.col("daily_sales") - pl.col("daily_credits")).alias("daily_balance_delta"))
            .sort(["customer_id", "date"])
        )

        # 2. Compute Cumulative Outstanding Balance
        exposure_df = daily_delta.with_columns(
            pl.col("daily_balance_delta").cum_sum().over("customer_id").alias("outstanding_balance")
        )

        # 3. Calculate Exposure Metrics
        # - exposure_pressure: normalized ratio of outstanding to recent sales
        # - debit_persistence: how many consecutive days balance has been > 0
        exposure_df = exposure_df.with_columns(
            pl.when(pl.col("outstanding_balance") > 0).then(pl.lit(1)).otherwise(pl.lit(0)).alias("is_debit")
        )

        # Calculate consecutive days in debit using cumulative count over "is_debit" groups
        exposure_df = exposure_df.with_columns(
            pl.col("is_debit")
            .cum_count()
            .over(["customer_id", (pl.col("is_debit") != pl.col("is_debit").shift(1)).fill_null(True).cum_sum()])
            .alias("debit_streak")
        )

        # Reset streak if not in debit
        exposure_df = exposure_df.with_columns(
            pl.when(pl.col("is_debit") == 1)
            .then(pl.col("debit_streak"))
            .otherwise(pl.lit(0))
            .alias("debit_persistence_days")
        )

        return exposure_df.select(["customer_id", "date", "outstanding_balance", "debit_persistence_days"])
