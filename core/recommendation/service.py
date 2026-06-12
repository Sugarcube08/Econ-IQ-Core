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
            action_cat = "INCREASE_CREDIT_LIMIT"
            val = "20% Increase"
            rationale = "Customer exhibits low payment default risk coupled with expanding trading volume."
            priority = "MEDIUM"
            impact = "HIGH"
            conf = 0.90
        elif risk_pred.risk_level in ["HIGH", "CRITICAL"]:
            action_cat = "DECREASE_CREDIT_LIMIT"
            val = "30% Decrease"
            rationale = "Customer risk profile has degraded. High exposure default risk detected."
            priority = "HIGH" if risk_pred.risk_level == "HIGH" else "CRITICAL"
            impact = "HIGH"
            conf = 0.95
        else:
            action_cat = "MAINTAIN_CREDIT_LIMIT"
            val = "No Change"
            rationale = "Customer trading and repayment rhythms are stable."
            priority = "LOW"
            impact = "LOW"
            conf = 0.80

        recommendations.append(
            ActionRecommendation(
                type=RecommendationType.CREDIT_LIMIT,
                priority=priority,
                reason=rationale,
                affected_score="credit_score",
                expected_impact=impact,
                confidence=conf,
                action_category=action_cat,
                value=val,
            )
        )

        # 3. Payment Terms Recommendation
        if risk_pred.risk_level == "CRITICAL":
            recommendations.append(
                ActionRecommendation(
                    type=RecommendationType.PAYMENT_TERMS,
                    priority="CRITICAL",
                    reason="Critical settlement delays observed. Restrict credit terms immediately.",
                    affected_score="collection_score",
                    expected_impact="HIGH",
                    confidence=0.98,
                    action_category="TIGHTEN_PAYMENT_TERMS",
                    value="Net-15 or COD",
                )
            )
        elif risk_pred.risk_level == "HIGH":
            recommendations.append(
                ActionRecommendation(
                    type=RecommendationType.PAYMENT_TERMS,
                    priority="HIGH",
                    reason="High default risk detected. Shorten payment duration boundaries.",
                    affected_score="collection_score",
                    expected_impact="MEDIUM",
                    confidence=0.90,
                    action_category="TIGHTEN_PAYMENT_TERMS",
                    value="Net-30",
                )
            )
        elif risk_pred.risk_level == "LOW" and growth_pred.growth_potential in ["EXPANSION", "ACCELERATING"]:
            recommendations.append(
                ActionRecommendation(
                    type=RecommendationType.PAYMENT_TERMS,
                    priority="LOW",
                    reason="Highly reliable payment discipline supports extended terms to capture trading growth.",
                    affected_score="collection_score",
                    expected_impact="MEDIUM",
                    confidence=0.85,
                    action_category="EXTEND_PAYMENT_TERMS",
                    value="Net-60",
                )
            )

        # 4. Retention Recommendation (Churn Risk)
        if churn_pred.is_churn_risk:
            recommendations.append(
                ActionRecommendation(
                    type=RecommendationType.RETENTION_STRATEGY,
                    priority="HIGH",
                    reason="Extended inactivity gap detected. Assign account executive for retention contact.",
                    affected_score="relationship_score",
                    expected_impact="HIGH",
                    confidence=0.92,
                    action_category="PROACTIVE_RETENTION_REACH_OUT",
                    value=None,
                )
            )

        # 5. Collection strategy
        if risk_pred.risk_level in ["HIGH", "CRITICAL"]:
            recommendations.append(
                ActionRecommendation(
                    type=RecommendationType.COLLECTION_STRATEGY,
                    priority="HIGH" if risk_pred.risk_level == "HIGH" else "CRITICAL",
                    reason="High stress and overdue patterns indicate immediate collection queue priority.",
                    affected_score="collection_score",
                    expected_impact="HIGH",
                    confidence=0.94,
                    action_category="ACCELERATED_COLLECTION",
                    value=None,
                )
            )

        return CustomerRecommendations(
            customer_id=customer_id,
            generated_date=datetime.now(UTC).date(),
            recommendations=recommendations,
        )

