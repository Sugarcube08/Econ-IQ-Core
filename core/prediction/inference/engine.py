from datetime import UTC, datetime
from typing import Any

import polars as pl
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.feature_store.engineer import FeatureEngineer
from core.ledger.context import LedgerContextService
from core.prediction.interfaces.estimator import IInferenceEngine
from core.prediction.registry.model_registry import model_registry
from core.schemas.intelligence import AnalysisContext


class InferenceEngine(IInferenceEngine):
    """
    Standard implementation of IInferenceEngine.
    """

    def __init__(self):
        self.ledger_context = LedgerContextService()
        self.feature_engineer = FeatureEngineer()

    async def run_inference(
        self, session: AsyncSession, customer_id: str, model_type: str, version: str | None = None
    ) -> Any:
        logger.debug(f"Executing Inference Engine for customer [{customer_id}] | Model: [{model_type}]")

        # 1. Load customer ledger context
        history_df = await self.ledger_context.load_customer_history(session, [customer_id])
        if history_df.is_empty():
            logger.warning(f"No history found for customer [{customer_id}] during inference.")
            features_df = pl.DataFrame()
        else:
            # 2. Generate longitudinal features
            context = AnalysisContext(window_days=365, end_date=datetime.now(UTC).date())
            features_df = self.feature_engineer.compute_features(history_df, context)

        # 3. Fetch swappable model from registry
        model = model_registry.get_model(model_type, version)

        # 4. Run prediction
        prediction = model.predict(customer_id, features_df)
        return prediction
