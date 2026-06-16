import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import DecisionAudit, Recommendation


class DecisionAuditService:
    """
    Service to manage decision actions, log overrides/approvals, and retrieve audit histories.
    """

    async def record_action(
        self,
        customer_id: str,
        recommendation_id: str | None,
        action_taken: str,
        performed_by: str,
        reason: str,
        db_session: AsyncSession
    ) -> DecisionAudit:
        """
        Logs an analyst action in the decision audit trail, and updates
        the status of the referenced recommendation.
        """
        if recommendation_id:
            stmt = select(Recommendation).where(Recommendation.id == recommendation_id)
            res = await db_session.execute(stmt)
            rec = res.scalars().first()
            if rec:
                if action_taken == "APPROVED":
                    rec.status = "RESOLVED"
                elif action_taken == "OVERRIDDEN":
                    rec.status = "OVERRIDDEN"
                elif action_taken == "REJECTED":
                    rec.status = "RESOLVED"
                logger.info("BUSINESS | Updated recommendation status", extra={"recommendation_id": recommendation_id, "new_status": rec.status})

        audit = DecisionAudit(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            recommendation_id=recommendation_id,
            action_taken=action_taken,
            performed_by=performed_by,
            reason=reason,
            timestamp=datetime.now(UTC)
        )
        db_session.add(audit)
        await db_session.flush()
        logger.info("BUSINESS | Credit Decision logged", extra={"customer_id": customer_id, "action_taken": action_taken, "performed_by": performed_by})
        return audit

    async def get_history(
        self,
        customer_id: str | None,
        db_session: AsyncSession
    ) -> list[DecisionAudit]:
        """
        Retrieves decision audit history logs.
        """
        stmt = select(DecisionAudit)
        if customer_id:
            stmt = stmt.where(DecisionAudit.customer_id == customer_id)
        stmt = stmt.order_by(DecisionAudit.timestamp.desc())
        res = await db_session.execute(stmt)
        return list(res.scalars().all())
