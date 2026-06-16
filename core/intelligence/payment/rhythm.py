import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class PaymentRhythmEngine:
    """
    Analyzes HOW customers repay, focusing on fragmentation,
    regularity, and liquidity oscillations.
    """

    def compute_rhythm(self, ledger_df: pl.DataFrame, context: AnalysisContext) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "repayment_fragmentation": pl.Float64,
            "repayment_regularity_score": pl.Float64,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)


        # 1. Count Events per Customer
        counts = ledger_df.group_by("customer_id").agg(
            [
                pl.col("event_uid").filter(pl.col("event_type") == "SALE").count().alias("sale_count"),
                pl.col("event_uid").filter(pl.col("event_type") == "PAYMENT").count().alias("payment_count"),
            ]
        )

        # 2. Fragmentation Score (payment_count / sale_count)
        # High ratio (> 2.0) indicates fragmented, struggling payments.
        counts = counts.with_columns(
            (pl.col("payment_count") / pl.max_horizontal(pl.col("sale_count"), 1.0)).alias("repayment_fragmentation")
        )

        # 3. Regularity (Variance in payment gaps)
        payments_df = (
            ledger_df.filter(pl.col("event_type") == "PAYMENT")
            .sort(["customer_id", "event_date"])
            .with_columns(
                (pl.col("event_date").dt.date() - pl.col("event_date").dt.date().shift(1))
                .dt.total_days()
                .over("customer_id")
                .alias("pay_gap")
            )
        )

        regularity_df = payments_df.group_by("customer_id").agg(
            [pl.col("pay_gap").median().alias("median_pay_gap"), pl.col("pay_gap").std().alias("stddev_pay_gap")]
        )

        # Join and return
        final_df = counts.join(regularity_df, on="customer_id", how="left")

        # Calculate regularity_score: Lower stddev relative to median is better
        final_df = final_df.with_columns(
            (pl.col("stddev_pay_gap") / pl.max_horizontal(pl.col("median_pay_gap"), 1.0))
            .fill_null(1.0)  # High variance if only 1 payment
            .alias("repayment_regularity_score")
        )

        return final_df.select(
            ["customer_id", "repayment_fragmentation", "repayment_regularity_score", "payment_count"]
        )
