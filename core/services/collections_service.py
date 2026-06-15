import uuid
from datetime import UTC, date, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import CollectionActivity, PaymentCommitment


class CollectionsService:
    """
    Service to log and retrieve collections outreach activities and payment commitments.
    """

    async def log_activity(
        self,
        customer_id: str,
        user_id: str,
        activity_type: str,
        notes: str,
        outcome: str,
        db_session: AsyncSession
    ) -> CollectionActivity:
        """
        Saves a collector outreach activity log to the database.
        """
        activity = CollectionActivity(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            user_id=user_id,
            activity_type=activity_type,
            notes=notes,
            outcome=outcome,
            created_at=datetime.now(UTC)
        )
        db_session.add(activity)
        await db_session.flush()
        logger.info(f"Collection activity logged for customer {customer_id} by user {user_id}")
        return activity

    async def get_activities(
        self,
        customer_id: str | None,
        limit: int,
        offset: int,
        db_session: AsyncSession
    ) -> list[CollectionActivity]:
        """
        Retrieves historical collection activities.
        """
        stmt = select(CollectionActivity)
        if customer_id:
            stmt = stmt.where(CollectionActivity.customer_id == customer_id)
        stmt = stmt.order_by(CollectionActivity.created_at.desc()).limit(limit).offset(offset)
        res = await db_session.execute(stmt)
        return list(res.scalars().all())

    async def log_commitment(
        self,
        customer_id: str,
        amount: float,
        promised_date: date,
        db_session: AsyncSession
    ) -> PaymentCommitment:
        """
        Saves a payment commitment to the database.
        """
        commitment = PaymentCommitment(
            id=str(uuid.uuid4()),
            customer_id=customer_id,
            amount=amount,
            promised_date=promised_date,
            status="PENDING",
            created_at=datetime.now(UTC)
        )
        db_session.add(commitment)
        await db_session.flush()
        logger.info(f"Payment commitment of {amount} logged for customer {customer_id} on {promised_date}")
        return commitment

    async def get_commitments(
        self,
        customer_id: str | None,
        status: str | None,
        db_session: AsyncSession
    ) -> list[PaymentCommitment]:
        """
        Retrieves registered payment commitments.
        """
        stmt = select(PaymentCommitment)
        if customer_id:
            stmt = stmt.where(PaymentCommitment.customer_id == customer_id)
        if status:
            stmt = stmt.where(PaymentCommitment.status == status)
        stmt = stmt.order_by(PaymentCommitment.promised_date.asc())
        res = await db_session.execute(stmt)
        return list(res.scalars().all())
