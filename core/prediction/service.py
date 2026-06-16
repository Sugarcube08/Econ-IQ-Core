from datetime import UTC, datetime

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from core.feature_store.engineer import FeatureEngineer
from core.ledger.context import LedgerContextService
from core.prediction.contracts.prediction_contracts import ModelMetadataContract
from core.prediction.interfaces.estimator import IModelEstimator
from core.prediction.monitoring.monitor import prediction_monitor
from core.prediction.registry.model_registry import model_registry
from core.schemas.intelligence import AnalysisContext
from core.schemas.prediction import (
    ChurnPrediction,
    CollectionPrediction,
    GrowthPrediction,
    HealthPrediction,
    OpportunityPrediction,
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
            model_version="1.0.0",
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["unpaid_ratio", "penalty_returns"] if score > 0.5 else ["payment_regularity"],
            risk_level=risk_level,
        )

    def get_metadata(self) -> ModelMetadataContract:
        return ModelMetadataContract(
            model_name="DefaultRiskEstimator",
            model_version="1.0.0",
            framework="HeuristicRules",
            features_required=["sales_window", "payments_window", "penalty_window"],
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
            model_version="1.0.0",
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["sales_recent_velocity"],
            growth_potential=potential,
        )

    def get_metadata(self) -> ModelMetadataContract:
        return ModelMetadataContract(
            model_name="DefaultGrowthEstimator",
            model_version="1.0.0",
            framework="HeuristicRules",
            features_required=["sales_window", "sales_recent"],
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
            model_version="1.0.0",
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["payment_ratio", "operational_friction_penalty"],
            health_grade=grade,
        )

    def get_metadata(self) -> ModelMetadataContract:
        return ModelMetadataContract(
            model_name="DefaultHealthEstimator",
            model_version="1.0.0",
            framework="HeuristicRules",
            features_required=["sales_window", "payments_window", "penalty_window"],
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
            model_version="1.0.0",
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["days_since_last_purchase"],
            is_churn_risk=is_churn,
        )

    def get_metadata(self) -> ModelMetadataContract:
        return ModelMetadataContract(
            model_name="DefaultChurnEstimator",
            model_version="1.0.0",
            framework="HeuristicRules",
            features_required=["last_purchased_at"],
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
            model_version="1.0.0",
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["historical_repayment_ratio"],
            repayment_probability=round(prob, 4),
            expected_delay_days=delay,
        )

    def get_metadata(self) -> ModelMetadataContract:
        return ModelMetadataContract(
            model_name="DefaultCollectionEstimator",
            model_version="1.0.0",
            framework="HeuristicRules",
            features_required=["sales_window", "payments_window"],
        )


class DefaultOpportunityEstimator(IModelEstimator):
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> OpportunityPrediction:
        if features_df.is_empty():
            score = 0.5
            tier = "MEDIUM"
            val = 0.0
        else:
            row = features_df.tail(1).to_dicts()[0]
            sales = row.get("sales_window") or 0.0
            diversity = row.get("category_diversity_count") or 1.0

            # High sales + low diversity = STIMULUS upsell opportunity
            if sales > 50000.0 and diversity <= 2:
                score = 0.85
                tier = "STIMULUS"
                val = sales * 0.25
            elif sales > 10000.0 and diversity <= 4:
                score = 0.65
                tier = "HIGH"
                val = sales * 0.15
            elif sales > 0:
                score = 0.45
                tier = "MEDIUM"
                val = sales * 0.05
            else:
                score = 0.15
                tier = "LOW"
                val = 0.0

        return OpportunityPrediction(
            customer_id=customer_id,
            prediction_date=datetime.now(UTC).date(),
            score=round(score, 4),
            confidence=0.82,
            model_version="1.0.0",
            features_snapshot=features_df.to_dicts()[0] if not features_df.is_empty() else {},
            key_drivers=["sales_vs_category_diversity"],
            opportunity_tier=tier,
            expected_upsell_value=round(val, 2),
        )

    def get_metadata(self) -> ModelMetadataContract:
        return ModelMetadataContract(
            model_name="DefaultOpportunityEstimator",
            model_version="1.0.0",
            framework="HeuristicRules",
            features_required=["sales_window", "category_diversity_count"],
        )


# Register baseline default models under registry version 1.0.0
model_registry.register_model("RISK", "1.0.0", DefaultRiskEstimator())
model_registry.register_model("GROWTH", "1.0.0", DefaultGrowthEstimator())
model_registry.register_model("HEALTH", "1.0.0", DefaultHealthEstimator())
model_registry.register_model("CHURN", "1.0.0", DefaultChurnEstimator())
model_registry.register_model("COLLECTION", "1.0.0", DefaultCollectionEstimator())
model_registry.register_model("OPPORTUNITY", "1.0.0", DefaultOpportunityEstimator())


class PredictionService:
    """
    Orchestrates ML features generation and execution of prediction models.
    Supports dynamic model swapping and telemetry hooks.
    """

    def __init__(self):
        self.ledger_context = LedgerContextService()
        self.feature_engineer = FeatureEngineer()

    async def get_all_predictions(self, session: AsyncSession, customer_id: str, version: str | None = None) -> dict:
        """Consolidated method to fetch all predictions using 1 database load and 1 feature generation."""
        features = await self._load_features(session, customer_id)
        
        # RISK
        risk_model = model_registry.get_model("RISK", version)
        risk_pred = risk_model.predict(customer_id, features)
        prediction_monitor.log_prediction(customer_id, "RISK", risk_model.get_metadata().model_version, risk_pred)
        
        # GROWTH
        growth_model = model_registry.get_model("GROWTH", version)
        growth_pred = growth_model.predict(customer_id, features)
        prediction_monitor.log_prediction(customer_id, "GROWTH", growth_model.get_metadata().model_version, growth_pred)
        
        # HEALTH
        health_model = model_registry.get_model("HEALTH", version)
        health_pred = health_model.predict(customer_id, features)
        prediction_monitor.log_prediction(customer_id, "HEALTH", health_model.get_metadata().model_version, health_pred)
        
        # CHURN
        churn_model = model_registry.get_model("CHURN", version)
        churn_pred = churn_model.predict(customer_id, features)
        prediction_monitor.log_prediction(customer_id, "CHURN", churn_model.get_metadata().model_version, churn_pred)
        
        # COLLECTION
        collection_model = model_registry.get_model("COLLECTION", version)
        collection_pred = collection_model.predict(customer_id, features)
        prediction_monitor.log_prediction(customer_id, "COLLECTION", collection_model.get_metadata().model_version, collection_pred)
        
        # OPPORTUNITY
        opportunity_model = model_registry.get_model("OPPORTUNITY", version)
        opportunity_pred = opportunity_model.predict(customer_id, features)
        prediction_monitor.log_prediction(customer_id, "OPPORTUNITY", opportunity_model.get_metadata().model_version, opportunity_pred)
        
        return {
            "risk": risk_pred,
            "growth": growth_pred,
            "health": health_pred,
            "churn": churn_pred,
            "collection": collection_pred,
            "opportunity": opportunity_pred
        }

    async def get_risk_prediction(self, session: AsyncSession, customer_id: str, version: str | None = None) -> RiskPrediction:
        res = await self.get_all_predictions(session, customer_id, version)
        return res["risk"]

    async def get_growth_prediction(self, session: AsyncSession, customer_id: str, version: str | None = None) -> GrowthPrediction:
        res = await self.get_all_predictions(session, customer_id, version)
        return res["growth"]

    async def get_health_prediction(self, session: AsyncSession, customer_id: str, version: str | None = None) -> HealthPrediction:
        res = await self.get_all_predictions(session, customer_id, version)
        return res["health"]

    async def get_churn_prediction(self, session: AsyncSession, customer_id: str, version: str | None = None) -> ChurnPrediction:
        res = await self.get_all_predictions(session, customer_id, version)
        return res["churn"]

    async def get_collection_prediction(self, session: AsyncSession, customer_id: str, version: str | None = None) -> CollectionPrediction:
        res = await self.get_all_predictions(session, customer_id, version)
        return res["collection"]

    async def get_opportunity_prediction(self, session: AsyncSession, customer_id: str, version: str | None = None) -> OpportunityPrediction:
        res = await self.get_all_predictions(session, customer_id, version)
        return res["opportunity"]

    async def _load_features(self, session: AsyncSession, customer_id: str) -> pl.DataFrame:
        """Loads customer timeline and aggregates features."""
        history_df = await self.ledger_context.load_customer_history(session, [customer_id])
        if history_df.is_empty():
            return pl.DataFrame()
            
        try:
            from sqlalchemy import text
            max_pay_res = await session.execute(text("SELECT MAX(event_date) FROM event_ledger WHERE event_type = 'PAYMENT'"))
            max_pay_date = max_pay_res.scalar()
            if max_pay_date:
                anchor_date = max_pay_date
            else:
                anchor_date = datetime.now(UTC).date()
        except Exception:
            anchor_date = datetime.now(UTC).date()

        context = AnalysisContext(window_days=365, end_date=anchor_date)
        features_df = self.feature_engineer.compute_features(history_df, context)
        return features_df
