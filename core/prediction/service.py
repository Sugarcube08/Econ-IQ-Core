from datetime import UTC, datetime

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from core.feature_store.engineer import FeatureEngineer
from core.ledger.context import LedgerContextService
from core.prediction.interfaces import IModelEstimator
from core.schemas.intelligence import AnalysisContext
from core.schemas.prediction import (
    ChurnPrediction,
    CollectionPrediction,
    GrowthPrediction,
    HealthPrediction,
    RiskPrediction,
)


class DefaultRiskEstimator(IModelEstimator):
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> RiskPrediction:
        # Rules-based proxy for default risk using outstanding & payments windows
        if features_df.is_empty():
            score = 0.5
            risk_level = "MEDIUM"
        else:
            row = features_df.tail(1).to_dicts()[0]
            sales = row.get("sales_window") or 0.0
            payments = row.get("payments_window") or 0.0
            penalty = row.get("penalty_window") or 0.0
            
            # Simple ratio + return penalties
            if sales > 0:
                unpaid_ratio = max(0.0, (sales - payments) / sales)
            else:
                unpaid_ratio = 0.5
                
            score = min(1.0, unpaid_ratio * 0.7 + (1.0 if penalty > 0 else 0.0) * 0.3)
            
            if score < 0.25:
                risk_level = "LOW"
            elif score < 0.5:
                risk_level = "MEDIUM"
            elif score < 0.75:
                risk_level = "HIGH"
            else:
                risk_level = "CRITICAL"

        return RiskPrediction(
            customer_id=customer_id,
            prediction_date=datetime.now(UTC).date(),
            score=round(score, 4),
            confidence=0.95,
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["unpaid_ratio", "penalty_returns"] if score > 0.5 else ["payment_regularity"],
            risk_level=risk_level,
        )


class DefaultGrowthEstimator(IModelEstimator):
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> GrowthPrediction:
        if features_df.is_empty():
            score = 0.5
            potential = "STABLE"
        else:
            row = features_df.tail(1).to_dicts()[0]
            sales = row.get("sales_window") or 0.0
            sales_recent = row.get("sales_recent") or 0.0
            
            # Growth based on recent vs overall sales trajectory
            if sales > 0:
                growth_ratio = (sales_recent * 5.0) / sales # scaled
            else:
                growth_ratio = 1.0
                
            score = min(1.0, max(0.0, growth_ratio * 0.5))
            
            if score < 0.3:
                potential = "CONTRACTION"
            elif score < 0.6:
                potential = "STABLE"
            elif score < 0.8:
                potential = "EXPANSION"
            else:
                potential = "ACCELERATING"

        return GrowthPrediction(
            customer_id=customer_id,
            prediction_date=datetime.now(UTC).date(),
            score=round(score, 4),
            confidence=0.88,
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["sales_recent_velocity"],
            growth_potential=potential,
        )


class DefaultHealthEstimator(IModelEstimator):
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> HealthPrediction:
        if features_df.is_empty():
            score = 0.7
            grade = "C"
        else:
            row = features_df.tail(1).to_dicts()[0]
            sales = row.get("sales_window") or 0.0
            payments = row.get("payments_window") or 0.0
            penalty = row.get("penalty_window") or 0.0
            
            if sales > 0:
                payment_ratio = min(1.0, payments / sales)
            else:
                payment_ratio = 0.8
                
            penalty_ratio = min(1.0, penalty / max(sales, 1.0))
            score = min(1.0, max(0.0, payment_ratio * 0.8 - penalty_ratio * 0.5))
            
            if score > 0.85:
                grade = "A"
            elif score > 0.70:
                grade = "B"
            elif score > 0.55:
                grade = "C"
            elif score > 0.40:
                grade = "D"
            else:
                grade = "F"

        return HealthPrediction(
            customer_id=customer_id,
            prediction_date=datetime.now(UTC).date(),
            score=round(score, 4),
            confidence=0.92,
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["payment_ratio", "operational_friction_penalty"],
            health_grade=grade,
        )


class DefaultChurnEstimator(IModelEstimator):
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> ChurnPrediction:
        if features_df.is_empty():
            score = 0.1
            is_churn = False
        else:
            row = features_df.tail(1).to_dicts()[0]
            last_pur = row.get("last_purchased_at")
            if last_pur:
                if isinstance(last_pur, str):
                    last_pur = datetime.strptime(last_pur[:10], "%Y-%m-%d").date()
                days_since = (datetime.now(UTC).date() - last_pur).days
            else:
                days_since = 365

            score = min(1.0, max(0.0, days_since / 180.0))
            is_churn = score > 0.75

        return ChurnPrediction(
            customer_id=customer_id,
            prediction_date=datetime.now(UTC).date(),
            score=round(score, 4),
            confidence=0.90,
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["days_since_last_purchase"],
            is_churn_risk=is_churn,
        )


class DefaultCollectionEstimator(IModelEstimator):
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> CollectionPrediction:
        if features_df.is_empty():
            prob = 0.8
            delay = 30
        else:
            row = features_df.tail(1).to_dicts()[0]
            sales = row.get("sales_window") or 0.0
            payments = row.get("payments_window") or 0.0
            
            if sales > 0:
                prob = min(1.0, max(0.0, payments / sales))
            else:
                prob = 0.85
                
            delay = int((1.0 - prob) * 90)

        return CollectionPrediction(
            customer_id=customer_id,
            prediction_date=datetime.now(UTC).date(),
            score=round(prob, 4),
            confidence=0.85,
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["historical_repayment_ratio"],
            repayment_probability=round(prob, 4),
            expected_delay_days=delay,
        )


class PredictionService:
    """
    Orchestrates ML features generation and execution of prediction models.
    """

    def __init__(
        self,
        risk_model: IModelEstimator | None = None,
        growth_model: IModelEstimator | None = None,
        health_model: IModelEstimator | None = None,
        churn_model: IModelEstimator | None = None,
        collection_model: IModelEstimator | None = None,
    ):
        self.ledger_context = LedgerContextService()
        self.feature_engineer = FeatureEngineer()
        
        # Load custom models or fallback to default rule-based predictors
        self.risk_model = risk_model or DefaultRiskEstimator()
        self.growth_model = growth_model or DefaultGrowthEstimator()
        self.health_model = health_model or DefaultHealthEstimator()
        self.churn_model = churn_model or DefaultChurnEstimator()
        self.collection_model = collection_model or DefaultCollectionEstimator()

    async def get_risk_prediction(self, session: AsyncSession, customer_id: str) -> RiskPrediction:
        features = await self._load_features(session, customer_id)
        return self.risk_model.predict(customer_id, features)

    async def get_growth_prediction(self, session: AsyncSession, customer_id: str) -> GrowthPrediction:
        features = await self._load_features(session, customer_id)
        return self.growth_model.predict(customer_id, features)

    async def get_health_prediction(self, session: AsyncSession, customer_id: str) -> HealthPrediction:
        features = await self._load_features(session, customer_id)
        return self.health_model.predict(customer_id, features)

    async def get_churn_prediction(self, session: AsyncSession, customer_id: str) -> ChurnPrediction:
        features = await self._load_features(session, customer_id)
        return self.churn_model.predict(customer_id, features)

    async def get_collection_prediction(self, session: AsyncSession, customer_id: str) -> CollectionPrediction:
        features = await self._load_features(session, customer_id)
        return self.collection_model.predict(customer_id, features)

    async def _load_features(self, session: AsyncSession, customer_id: str) -> pl.DataFrame:
        """Loads customer timeline and aggregates features."""
        history_df = await self.ledger_context.load_customer_history(session, [customer_id])
        if history_df.is_empty():
            return pl.DataFrame()
            
        context = AnalysisContext(window_days=365, end_date=datetime.now(UTC).date())
        features_df = self.feature_engineer.compute_features(history_df, context)
        return features_df
