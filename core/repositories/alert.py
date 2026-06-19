import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import Alert


class AlertRepository:
    """
    SQLAlchemy repository to manage data access for system alerts.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_active_alert_by_type(self, customer_id: str, alert_type: str) -> Alert | None:
        stmt = select(Alert).where(
            Alert.customer_id == customer_id,
            Alert.alert_type == alert_type,
            Alert.status == "ACTIVE"
        )
        res = await self.db.execute(stmt)
        return res.scalars().first()

    async def create_alert(
        self,
        customer_id: str,
        alert_type: str,
        alert_severity: str,
        title: str,
        description: str,
        workspace_id: str | None = None
    ) -> Alert:
        alert = Alert(
            id=str(uuid.uuid4()),
            workspace_id=workspace_id,
            customer_id=customer_id,
            alert_type=alert_type,
            alert_severity=alert_severity,
            title=title,
            description=description,
            status="ACTIVE",
            created_at=datetime.now(UTC)
        )
        self.db.add(alert)
        logger.info("BUSINESS | Alert Created", extra={"customer_id": customer_id, "alert_type": alert_type, "alert_severity": alert_severity})
        return alert

    async def get_alerts(
        self,
        status: str | None,
        severity: str | None,
        customer_id: str | None,
        limit: int,
        offset: int
    ) -> list[Alert]:
        stmt = select(Alert)
        if status:
            stmt = stmt.where(Alert.status == status)
        if severity:
            stmt = stmt.where(Alert.alert_severity == severity)
        if customer_id:
            stmt = stmt.where(Alert.customer_id == customer_id)
        stmt = stmt.order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        res = await self.db.execute(stmt)
        return list(res.scalars().all())

    async def get_alerts_count(self) -> dict:
        active_stmt = select(func.count(Alert.id)).where(Alert.status == "ACTIVE")
        critical_stmt = select(func.count(Alert.id)).where(Alert.status == "ACTIVE", Alert.alert_severity == "CRITICAL")
        warning_stmt = select(func.count(Alert.id)).where(Alert.status == "ACTIVE", Alert.alert_severity == "WARNING")

        active_res = await self.db.execute(active_stmt)
        critical_res = await self.db.execute(critical_stmt)
        warning_res = await self.db.execute(warning_stmt)

        return {
            "active": active_res.scalar() or 0,
            "critical": critical_res.scalar() or 0,
            "warning": warning_res.scalar() or 0
        }

    async def acknowledge_alert(self, alert_id: str, user_id: str | None) -> Alert | None:
        stmt = select(Alert).where(Alert.id == alert_id)
        res = await self.db.execute(stmt)
        alert = res.scalars().first()
        if alert:
            alert.status = "ACKNOWLEDGED"
            alert.acknowledged_at = datetime.now(UTC)
            alert.acknowledged_by = user_id
            logger.info("BUSINESS | Alert Resolved", extra={"customer_id": alert.customer_id, "alert_id": alert.id, "acknowledged_by": user_id})
        return alert
