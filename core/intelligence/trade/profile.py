import polars as pl
from loguru import logger

from core.schemas.intelligence import AnalysisContext


class TradeProfileEngine:
    """
    Analyzes the structural nature of customer trading and exposure patterns.
    Distinguishes between episodic high-value traders and frequent low-value traders.
    """

    def compute_profile(
        self, ledger_df: pl.DataFrame, exposure_df: pl.DataFrame, context: AnalysisContext
    ) -> pl.DataFrame:
        """
        Computes structural trade profile and exposure distribution metrics.
        Includes behavioral_purchase_capacity for future allowance reasoning.
        """
        empty_schema = {
            "customer_id": pl.Utf8,
            "avg_txn_size": pl.Float64,
            "median_txn_size": pl.Float64,
            "p90_txn_size": pl.Float64,
            "txn_size_variance_ratio": pl.Float64,
            "exposure_burstiness": pl.Float64,
            "exposure_p90": pl.Float64,
            "exposure_p95": pl.Float64,
            "sustained_exposure_zone": pl.Float64,
            "behavioral_purchase_capacity": pl.Float64,
            "structural_trade_profile": pl.Utf8,
        }
        if ledger_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        logger.debug("Computing structural trade profile and behavioral purchase capacity")

        # 1. Transaction Size Analysis (Based on SALES)
        sales_df = ledger_df.filter(pl.col("event_type") == "SALE")

        if sales_df.is_empty():
            return pl.DataFrame(schema=empty_schema)

        txn_stats = (
            sales_df.group_by("customer_id")
            .agg(
                [
                    pl.col("amount").mean().alias("avg_txn_size"),
                    pl.col("amount").median().alias("median_txn_size"),
                    pl.col("amount").quantile(0.90).alias("p90_txn_size"),
                    pl.col("amount").std().alias("std_txn_size"),
                    pl.col("amount").max().alias("max_txn_size"),
                    pl.len().alias("txn_count"),
                ]
            )
            .with_columns(
                (pl.col("std_txn_size") / pl.max_horizontal(pl.col("avg_txn_size"), 1.0)).alias(
                    "txn_size_variance_ratio"
                ),
                (pl.col("max_txn_size") / pl.max_horizontal(pl.col("avg_txn_size"), 1.0)).alias("exposure_burstiness"),
            )
        )

        # 2. Exposure Distribution Analysis (Based on outstanding_balance history)
        if not exposure_df.is_empty():
            exp_stats = exposure_df.group_by("customer_id").agg(
                [
                    pl.col("outstanding_balance").quantile(0.90).alias("exposure_p90"),
                    pl.col("outstanding_balance").quantile(0.95).alias("exposure_p95"),
                    # Sustained zone: mean of top 20% exposure days
                    pl.col("outstanding_balance")
                    .filter(pl.col("outstanding_balance") >= pl.col("outstanding_balance").quantile(0.80))
                    .mean()
                    .alias("sustained_exposure_zone"),
                ]
            )
        else:
            exp_stats = pl.DataFrame(
                {
                    "customer_id": txn_stats["customer_id"],
                    "exposure_p90": [0.0] * len(txn_stats),
                    "exposure_p95": [0.0] * len(txn_stats),
                    "sustained_exposure_zone": [0.0] * len(txn_stats),
                }
            )

        # 3. Join and Classify Profile
        profile_df = txn_stats.join(exp_stats, on="customer_id", how="left")

        # Fill nulls
        profile_df = profile_df.with_columns(
            [
                pl.col("txn_size_variance_ratio").fill_null(0.0),
                pl.col("exposure_burstiness").fill_null(1.0),
                pl.col("exposure_p90").fill_null(0.0),
                pl.col("exposure_p95").fill_null(0.0),
                pl.col("sustained_exposure_zone").fill_null(0.0),
                pl.col("p90_txn_size").fill_null(0.0),
            ]
        )

        # 4. Profile Classification and Behavioral Capacity Synthesis
        profile_df = profile_df.with_columns(
            pl.struct(["avg_txn_size", "exposure_burstiness", "txn_size_variance_ratio"])
            .map_elements(lambda x: self._classify_structural_profile(x), return_dtype=pl.Utf8)
            .alias("structural_trade_profile")
        )

        # 5. Behavioral Purchase Capacity Synthesis
        # Logic:
        # EPISODIC: Capacity should allow for 1.2x their P90 transaction size (high single-shot).
        # FREQUENT: Capacity should allow for 2.5x their P90 size (revolving room for multiple open small bills).
        # BALANCED: 1.8x P90 size.
        profile_df = profile_df.with_columns(
            pl.struct(["p90_txn_size", "structural_trade_profile", "max_txn_size"])
            .map_elements(lambda x: self._synthesize_behavioral_capacity(x), return_dtype=pl.Float64)
            .alias("behavioral_purchase_capacity")
        )

        return profile_df

    def _classify_structural_profile(self, row: dict) -> str:
        avg_size = row["avg_txn_size"]
        burstiness = row["exposure_burstiness"]
        variance = row["txn_size_variance_ratio"]

        # High Value episodic (Large individual transaction scale)
        if avg_size > 100000 or (avg_size > 50000 and burstiness > 1.5):
            return "EPISODIC_HIGH_VALUE"

        # Frequent Small (Consistent low-value throughput)
        elif avg_size < 20000 and variance < 0.8:
            return "FREQUENT_LOW_VALUE"

        # Balanced (Moderate scale and regularity)
        elif avg_size > 30000 and variance < 1.0:
            return "BALANCED_STABLE"

        else:
            return "IRREGULAR_STRUCTURE"

    def _synthesize_behavioral_capacity(self, row: dict) -> float:
        p90 = row["p90_txn_size"]
        profile = row["structural_trade_profile"]
        max_txn = row["max_txn_size"]

        if profile == "EPISODIC_HIGH_VALUE":
            # Support the peak transaction size plus a small buffer
            return max(max_txn * 1.1, p90 * 1.2)
        elif profile == "FREQUENT_LOW_VALUE":
            # Support multiple open transactions (e.g., 2.5 cycles)
            return p90 * 2.5
        elif profile == "BALANCED_STABLE":
            # Balanced revolving room
            return p90 * 2.0
        else:
            # Conservative for irregular
            return p90 * 1.5
