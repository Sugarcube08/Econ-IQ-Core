from datetime import date

import polars as pl
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.feature_store.engineer import FeatureEngineer
from core.ledger.context import LedgerContextService
from core.schemas.intelligence import AnalysisContext


class MLDatasetBuilder:
    """
    Extracts features from event history and structures training datasets
    for XGBoost/LightGBM model training cycles.
    """

    def __init__(self):
        self.ledger_context = LedgerContextService()
        self.feature_engineer = FeatureEngineer()

    async def build_training_set(
        self, session: AsyncSession, customer_ids: list[str], end_date: date, window_days: int = 365
    ) -> pl.DataFrame:
        """
        Builds a single stateful feature dataset for a set of customers as of a target historical date.
        """
        logger.info(f"Building ML training dataset for {len(customer_ids)} customers as of {end_date}")
        history_df = await self.ledger_context.load_customer_history(session, customer_ids)
        if history_df.is_empty():
            return pl.DataFrame()

        context = AnalysisContext(window_days=window_days, end_date=end_date)
        features_df = self.feature_engineer.compute_features(history_df, context)
        return features_df

    def split_train_val_test(
        self, df: pl.DataFrame, train_ratio: float = 0.7, val_ratio: float = 0.15
    ) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
        """
        Splits dataset deterministically for model training validation cycles.
        """
        if df.is_empty():
            return pl.DataFrame(), pl.DataFrame(), pl.DataFrame()

        # Deterministic shuffle by hashing customer_id
        shuffled = df.with_columns(
            pl.col("customer_id").hash().alias("shuffle_hash")
        ).sort("shuffle_hash")

        n = len(shuffled)
        n_train = int(n * train_ratio)
        n_val = int(n * val_ratio)

        train = shuffled.slice(0, n_train).drop("shuffle_hash")
        val = shuffled.slice(n_train, n_val).drop("shuffle_hash")
        test = shuffled.slice(n_train + n_val).drop("shuffle_hash")

        logger.info(f"Dataset split: Train={len(train)} | Val={len(val)} | Test={len(test)}")
        return train, val, test
