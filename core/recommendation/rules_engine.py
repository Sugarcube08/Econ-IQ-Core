import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import CustomerIntelligence, Recommendation
from core.schemas.recommendation import (
    ActionRecommendation,
    CustomerRecommendations,
    RecommendationType,
)


class RecommendationRulesEngine:
    """
    Evaluates credit rules and generates persistent credit policy recommendations.
    """
    def __init__(self, *args, **kwargs):
        pass

    async def evaluate_policies(self, session: AsyncSession, customer_id: str) -> CustomerRecommendations:
        """
        Calculates credit recommendations based on customer score thresholds and saves them.
        """
        logger.debug("BUSINESS | Evaluating credit policies", extra={"customer_id": customer_id})
        
        # 1. Fetch relevant customer intelligence scores
        stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
        res = await session.execute(stmt)
        intel = res.scalars().first()

        if not intel:
            logger.warning("BUSINESS | No customer intelligence found during credit policy evaluation", extra={"customer_id": customer_id})
            return CustomerRecommendations(customer_id=customer_id, generated_date=datetime.now(UTC).date(), recommendations=[])

        # 2. Clear existing ACTIVE recommendations for this customer
        await session.execute(
            delete(Recommendation).where(
                Recommendation.customer_id == customer_id,
                Recommendation.status == "ACTIVE"
            )
        )

        # 3. Rules Engine Execution
        recs_to_add = []
        
        h_score = intel.health_score or 0.0
        r_score = intel.risk_score or 0.0
        g_score = intel.growth_score or 0.0
        t_score = intel.trust_score or 0.0
        c_score = intel.collection_score or 0.0
        state = intel.state or "active"

        # Rule 1: High Growth Opportunity
        is_high_growth = False
        if h_score >= 0.75 and r_score < 0.25 and g_score >= 0.70:
            is_high_growth = True
            recs_to_add.append(
                Recommendation(
                    id=str(uuid.uuid4()),
                    customer_id=customer_id,
                    recommendation_type="HIGH_GROWTH_OPPORTUNITY",
                    severity="INFO",
                    reason="Customer shows strong commercial growth with exceptionally low credit risk profile.",
                    confidence=0.90,
                    status="ACTIVE",
                    created_at=datetime.now(UTC)
                )
            )

        # Rule 2: Increase Credit (only if not already high growth opportunity)
        if not is_high_growth and t_score >= 0.70 and r_score < 0.35:
            recs_to_add.append(
                Recommendation(
                    id=str(uuid.uuid4()),
                    customer_id=customer_id,
                    recommendation_type="INCREASE_CREDIT",
                    severity="INFO",
                    reason="Debtor shows high prompt payment trust, qualifying for credit limit expansion.",
                    confidence=0.85,
                    status="ACTIVE",
                    created_at=datetime.now(UTC)
                )
            )

        # Rule 3: Maintain Credit (stable baseline)
        if not recs_to_add and t_score >= 0.40 and r_score < 0.60:
            recs_to_add.append(
                Recommendation(
                    id=str(uuid.uuid4()),
                    customer_id=customer_id,
                    recommendation_type="MAINTAIN_CREDIT",
                    severity="INFO",
                    reason="Customer credit metrics are stable within normal operating thresholds.",
                    confidence=0.80,
                    status="ACTIVE",
                    created_at=datetime.now(UTC)
                )
            )

        # Rule 4: Review Account (Deterioration)
        if r_score >= 0.60 or h_score < 0.40:
            recs_to_add.append(
                Recommendation(
                    id=str(uuid.uuid4()),
                    customer_id=customer_id,
                    recommendation_type="REVIEW_ACCOUNT",
                    severity="WARNING",
                    reason="Deterioration in behavioral health indicators; account requires analyst review.",
                    confidence=0.85,
                    status="ACTIVE",
                    created_at=datetime.now(UTC)
                )
            )

        # Rule 5: Reduce Exposure (High risk)
        if r_score >= 0.70 or c_score < 0.30:
            recs_to_add.append(
                Recommendation(
                    id=str(uuid.uuid4()),
                    customer_id=customer_id,
                    recommendation_type="REDUCE_EXPOSURE",
                    severity="WARNING",
                    reason="Risk score exceeded threshold. Suggest reducing credit exposure boundaries.",
                    confidence=0.90,
                    status="ACTIVE",
                    created_at=datetime.now(UTC)
                )
            )

        # Rule 6: Immediate Collection (Critical stress)
        if r_score >= 0.80 or state == "declining":
            recs_to_add.append(
                Recommendation(
                    id=str(uuid.uuid4()),
                    customer_id=customer_id,
                    recommendation_type="IMMEDIATE_COLLECTION",
                    severity="CRITICAL",
                    reason="Deteriorating credit state matches liquidity distress thresholds. Flagged for immediate outreach.",
                    confidence=0.95,
                    status="ACTIVE",
                    created_at=datetime.now(UTC)
                )
            )

        # Persist new recommendations
        for r in recs_to_add:
            session.add(r)
        
        await session.flush()

        # 4. Fetch all ACTIVE recommendations from DB to return
        stmt = select(Recommendation).where(
            Recommendation.customer_id == customer_id,
            Recommendation.status == "ACTIVE"
        )
        res = await session.execute(stmt)
        db_recs = res.scalars().all()

        recommendations = []
        for r in db_recs:
            rec_type = RecommendationType.CREDIT_LIMIT
            action_cat = "MAINTAIN_CREDIT_LIMIT"
            priority = "LOW"
            impact = "LOW"
            val = None
            affected_score = "credit_score"

            if r.recommendation_type == "HIGH_GROWTH_OPPORTUNITY":
                rec_type = RecommendationType.CREDIT_LIMIT
                action_cat = "INCREASE_CREDIT_LIMIT"
                val = "20% Increase"
                priority = "MEDIUM"
                impact = "HIGH"
                affected_score = "growth_score"
            elif r.recommendation_type == "INCREASE_CREDIT":
                rec_type = RecommendationType.CREDIT_LIMIT
                action_cat = "INCREASE_CREDIT_LIMIT"
                val = "10% Increase"
                priority = "MEDIUM"
                impact = "MEDIUM"
                affected_score = "trust_score"
            elif r.recommendation_type == "MAINTAIN_CREDIT":
                rec_type = RecommendationType.CREDIT_LIMIT
                action_cat = "MAINTAIN_CREDIT_LIMIT"
                val = "No Change"
                priority = "LOW"
                impact = "LOW"
                affected_score = "credit_score"
            elif r.recommendation_type == "REVIEW_ACCOUNT":
                rec_type = RecommendationType.CREDIT_LIMIT
                action_cat = "MAINTAIN_CREDIT_LIMIT"
                val = "Needs Review"
                priority = "MEDIUM"
                impact = "MEDIUM"
                affected_score = "health_score"
            elif r.recommendation_type == "REDUCE_EXPOSURE":
                rec_type = RecommendationType.CREDIT_LIMIT
                action_cat = "DECREASE_CREDIT_LIMIT"
                val = "20% Decrease"
                priority = "HIGH"
                impact = "HIGH"
                affected_score = "risk_score"
            elif r.recommendation_type == "IMMEDIATE_COLLECTION":
                rec_type = RecommendationType.COLLECTION_STRATEGY
                action_cat = "ACCELERATED_COLLECTION"
                val = "Immediate"
                priority = "CRITICAL"
                impact = "HIGH"
                affected_score = "collection_score"

            recommendations.append(
                ActionRecommendation(
                    type=rec_type,
                    priority=priority,
                    reason=r.reason,
                    affected_score=affected_score,
                    expected_impact=impact,
                    confidence=r.confidence,
                    action_category=action_cat,
                    value=val
                )
            )

        return CustomerRecommendations(
            customer_id=customer_id,
            generated_date=datetime.now(UTC).date(),
            recommendations=recommendations,
        )

    # For backward compatibility with routes/orchestrator
    async def generate_recommendations(self, session: AsyncSession, customer_id: str) -> CustomerRecommendations:
        return await self.evaluate_policies(session, customer_id)
