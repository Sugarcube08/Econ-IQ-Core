from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from core.prediction.service import PredictionService
from core.schemas.recommendation import (
    ActionRecommendation,
    CustomerRecommendations,
    RecommendationType,
)


class RecommendationService:
    """
    Generates actionable business and financial recommendations
    based on customer behavioral scoring, ML predictions, and active policies.
    """

    def __init__(self, prediction_service: PredictionService | None = None):
        self.prediction_service = prediction_service or PredictionService()

    async def generate_recommendations(self, session: AsyncSession, customer_id: str) -> CustomerRecommendations:
        """
        Consumes ML predictions and outputs a set of action recommendations.
        """
        logger.info(f"Generating commercial recommendations for customer {customer_id}")
        
        # 1. Fetch relevant predictions
        risk_pred = await self.prediction_service.get_risk_prediction(session, customer_id)
        growth_pred = await self.prediction_service.get_growth_prediction(session, customer_id)
        churn_pred = await self.prediction_service.get_churn_prediction(session, customer_id)
        
        recommendations = []

        # 2. Credit Limit Recommendation
        if risk_pred.risk_level in ["LOW", "MEDIUM"] and growth_pred.growth_potential in ["EXPANSION", "ACCELERATING"]:
            # Low risk + High growth = Recommend Credit expansion
            action = "INCREASE_CREDIT_LIMIT"
            val = "20% Increase"
            rationale = "Customer exhibits low payment default risk coupled with expanding trading volume."
            conf = 0.90
        elif risk_pred.risk_level in ["HIGH", "CRITICAL"]:
            # High risk = Recommend Credit contraction
            action = "DECREASE_CREDIT_LIMIT"
            val = "30% Decrease"
            rationale = "Customer risk profile has degraded. High exposure default risk detected."
            conf = 0.95
        else:
            action = "MAINTAIN_CREDIT_LIMIT"
            val = "No Change"
            rationale = "Customer trading and repayment rhythms are stable."
            conf = 0.80

        recommendations.append(
            ActionRecommendation(
                recommendation_type=RecommendationType.CREDIT_LIMIT,
                action=action,
                value=val,
                rationale=rationale,
                confidence=conf,
            )
        )

        # 3. Payment Terms Recommendation
        if risk_pred.risk_level == "CRITICAL":
            recommendations.append(
                ActionRecommendation(
                    recommendation_type=RecommendationType.PAYMENT_TERMS,
                    action="TIGHTEN_PAYMENT_TERMS",
                    value="Net-15 or COD",
                    rationale="Critical settlement delays observed. Restrict credit terms immediately.",
                    confidence=0.98,
                )
            )
        elif risk_pred.risk_level == "HIGH":
            recommendations.append(
                ActionRecommendation(
                    recommendation_type=RecommendationType.PAYMENT_TERMS,
                    action="TIGHTEN_PAYMENT_TERMS",
                    value="Net-30",
                    rationale="High default risk detected. Shorten payment duration boundaries.",
                    confidence=0.90,
                )
            )
        elif risk_pred.risk_level == "LOW" and growth_pred.growth_potential in ["EXPANSION", "ACCELERATING"]:
            recommendations.append(
                ActionRecommendation(
                    recommendation_type=RecommendationType.PAYMENT_TERMS,
                    action="EXTEND_PAYMENT_TERMS",
                    value="Net-60",
                    rationale="Highly reliable payment discipline supports extended terms to capture trading growth.",
                    confidence=0.85,
                )
            )

        # 4. Retention Recommendation (Churn Risk)
        if churn_pred.is_churn_risk:
            recommendations.append(
                ActionRecommendation(
                    recommendation_type=RecommendationType.RETENTION_STRATEGY,
                    action="PROACTIVE_RETENTION_REACH_OUT",
                    rationale="Extended inactivity gap detected. Assign account executive for retention contact.",
                    confidence=0.92,
                )
            )

        # 5. Collection strategy
        if risk_pred.risk_level in ["HIGH", "CRITICAL"]:
            recommendations.append(
                ActionRecommendation(
                    recommendation_type=RecommendationType.COLLECTION_STRATEGY,
                    action="ACCELERATED_COLLECTION",
                    rationale="High stress and overdue patterns indicate immediate collection queue priority.",
                    confidence=0.94,
                )
            )

        return CustomerRecommendations(
            customer_id=customer_id,
            generated_date=datetime.now(UTC).date(),
            recommendations=recommendations,
        )
