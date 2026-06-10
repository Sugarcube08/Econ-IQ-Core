from dataclasses import dataclass
from datetime import date, datetime

import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


@dataclass
class Bill:
    id: str
    date: date
    amount: float
    remaining: float
    settled_date: date | None = None


class SettlementMatchingEngine:
    """
    Implements FIFO-style matching of receipts to sales bills.
    Calculates actual repayment durations and settlement classes.
    """

    def compute_settlements(self, ledger_df: pl.DataFrame, context: AnalysisContext) -> pl.DataFrame:
        empty_schema = {
            "customer_id": pl.Utf8,
            "avg_repayment_days": pl.Float64,
            "max_repayment_days": pl.Float64,
            "outstanding_bill_count": pl.Int64,
            "overdue_60_90_count": pl.Int64,
            "overdue_90_120_count": pl.Int64,
            "overdue_120p_count": pl.Int64,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing FIFO settlement matching")

        # 1. Separate Bills (SALES) and Credits (PAYMENTS + RETURNS)
        events = (
            ledger_df.filter(pl.col("event_type").is_in(["SALE", "PAYMENT", "RETURN", "OPENING_BALANCE", "DISCOUNT"]))
            .sort(["customer_id", "event_date", "sequence_number"])
            .select(["customer_id", "event_date", "amount", "event_type", "event_uid"])
            .with_columns(pl.col("event_date").dt.date().alias("date"))
        )

        customer_settlements = []
        reference_date = context.end_date if context.end_date else datetime.now().date()

        # 2. Procedural FIFO Matching per Customer
        # (Optimized for correctness in behavioral modeling)
        for (cid,), group in events.group_by("customer_id"):
            bills = []
            matched_data = []

            for row in group.to_dicts():
                etype = row["event_type"]
                amt = row["amount"]
                edate = row["date"]

                if etype in ["SALE", "OPENING_BALANCE"]:
                    bills.append(Bill(id=row["event_uid"], date=edate, amount=amt, remaining=amt))
                else:
                    # PAYMENT, RETURN, or DISCOUNT
                    # Apply credit to bills in FIFO order
                    credit_remaining = amt
                    while credit_remaining > 0 and bills:
                        current_bill = bills[0]

                        if credit_remaining >= current_bill.remaining:
                            # Bill fully settled
                            credit_remaining -= current_bill.remaining
                            current_bill.remaining = 0
                            current_bill.settled_date = edate

                            # Record settlement
                            repayment_days = (current_bill.settled_date - current_bill.date).days
                            matched_data.append(
                                {
                                    "customer_id": cid,
                                    "bill_id": current_bill.id,
                                    "bill_date": current_bill.date,
                                    "settled_date": current_bill.settled_date,
                                    "amount": current_bill.amount,
                                    "repayment_days": max(0, repayment_days),
                                    "status": "SETTLED",
                                }
                            )
                            bills.pop(0)
                        else:
                            # Bill partially settled
                            current_bill.remaining -= credit_remaining
                            credit_remaining = 0

            # Record outstanding bills
            for b in bills:
                matched_data.append(
                    {
                        "customer_id": cid,
                        "bill_id": b.id,
                        "bill_date": b.date,
                        "settled_date": None,
                        "amount": b.remaining,
                        "repayment_days": max(0, (reference_date - b.date).days),
                        "status": "OUTSTANDING",
                    }
                )

            customer_settlements.extend(matched_data)

        if not customer_settlements:
            return pl.DataFrame(schema=empty_schema)

        settlement_df = pl.DataFrame(customer_settlements)

        # MANDATORY: Filter metrics by window to ensure dynamic responsiveness
        # We only aggregate settlements or outstanding bills relevant to the requested window
        if context.start_date:
            # We filter by settled_date in window OR (outstanding and bill_date >= start_date)
            # This ensures averages only reflect the active analysis window
            settlement_df = settlement_df.filter(
                (pl.col("settled_date") >= context.start_date) |
                ((pl.col("status") == "OUTSTANDING") & (pl.col("bill_date") >= context.start_date))
            )

        if settlement_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        return self._aggregate_settlement_metrics(settlement_df)

    def _aggregate_settlement_metrics(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Aggregates settlements per customer and computes core repayment metrics.
        New Buckets: 0-60, 60-90, 90-120, 120+
        """
        agg_df = df.group_by("customer_id").agg(
            [
                pl.col("repayment_days").mean().alias("avg_repayment_days"),
                pl.col("repayment_days").max().alias("max_repayment_days"),
                pl.col("bill_id").count().alias("total_bill_count"),
                pl.col("amount").sum().alias("total_exposure"),
                pl.col("status").filter(pl.col("status") == "OUTSTANDING").count().alias("outstanding_bill_count"),
                pl.col("amount").filter(pl.col("status") == "OUTSTANDING").sum().alias("outstanding_amount"),
                # Counts for legacy/telemetry
                pl.col("repayment_days")
                .filter((pl.col("repayment_days") > 60) & (pl.col("repayment_days") <= 90))
                .count()
                .alias("overdue_60_90_count"),
                pl.col("repayment_days")
                .filter((pl.col("repayment_days") > 90) & (pl.col("repayment_days") <= 120))
                .count()
                .alias("overdue_90_120_count"),
                pl.col("repayment_days").filter(pl.col("repayment_days") > 120).count().alias("overdue_120p_count"),
                # Amounts for Exposure-Weighted Aging
                pl.col("amount")
                .filter((pl.col("repayment_days") > 60) & (pl.col("repayment_days") <= 90))
                .sum()
                .alias("overdue_60_90_amount"),
                pl.col("amount")
                .filter((pl.col("repayment_days") > 90) & (pl.col("repayment_days") <= 120))
                .sum()
                .alias("overdue_90_120_amount"),
                pl.col("amount")
                .filter(pl.col("repayment_days") > 120)
                .sum()
                .alias("overdue_120p_amount"),
            ]
        )

        return agg_df
