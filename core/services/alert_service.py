from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.state_models import Alert, CustomerIntelligence
from core.repositories.alert import AlertRepository


class AlertService:
    """
    Service to manage alert triggers and validation workflows.
    Delegates database access directly to AlertRepository.
    """

    async def generate_alert(
        self,
        customer_id: str,
        alert_type: str,
        alert_severity: str,
        title: str,
        description: str,
        db_session: AsyncSession,
        workspace_id: str | None = None
    ) -> Alert | None:
        """
        Generates and persists a unique alert if one is not already active.
        """
        repo = AlertRepository(db_session)
        existing = await repo.get_active_alert_by_type(customer_id, alert_type)
        if existing:
            return None
        
        return await repo.create_alert(
            customer_id=customer_id,
            alert_type=alert_type,
            alert_severity=alert_severity,
            title=title,
            description=description,
            workspace_id=workspace_id
        )

    async def get_alerts(
        self,
        status: str | None,
        severity: str | None,
        customer_id: str | None,
        limit: int,
        offset: int,
        db_session: AsyncSession
    ) -> list[Alert]:
        """
        Queries and filters active warning alerts.
        """
        repo = AlertRepository(db_session)
        return await repo.get_alerts(
            status=status,
            severity=severity,
            customer_id=customer_id,
            limit=limit,
            offset=offset
        )

    async def get_alerts_count(self, db_session: AsyncSession) -> dict:
        """
        Retrieves total counts of active, critical, and warning alerts.
        """
        repo = AlertRepository(db_session)
        return await repo.get_alerts_count()

    async def acknowledge_alert(self, alert_id: str, user_id: str | None, db_session: AsyncSession) -> Alert | None:
        """
        Flags an alert as ACKNOWLEDGED.
        """
        repo = AlertRepository(db_session)
        alert = await repo.acknowledge_alert(alert_id, user_id)
        if alert:
            await db_session.commit()
        return alert

    async def scan_and_generate_alerts(self, customer_id: str, db_session: AsyncSession) -> list[Alert]:
        """
        Evaluates rules against CustomerIntelligence scores and creates alerts.
        """
        stmt = select(CustomerIntelligence).where(CustomerIntelligence.customer_id == customer_id)
        res = await db_session.execute(stmt)
        intel = res.scalars().first()

        if not intel:
            return []

        generated = []

        def map_state_label(s: str | None) -> str:
            if s == "declining":
                return "liquidity_stress"
            if s == "inactive":
                return "contract"
            if s == "irregular":
                return "monitor"
            return "healthy"

        def infer_prev_state(trust: float | None, risk: float | None) -> str:
            if trust is None or risk is None:
                return "healthy"
            stress = 1.0 - risk
            if stress > 0.50:
                return "liquidity_stress"
            if trust > 0.75 and stress < 0.15:
                return "healthy"
            if trust > 0.45 and stress < 0.35:
                return "healthy"
            return "monitor"

        # Rule 1: Risk Spike
        if intel.risk_score is not None and intel.risk_previous is not None:
            delta = intel.risk_score - intel.risk_previous
            if delta >= 0.15:
                alert = await self.generate_alert(
                    customer_id=customer_id,
                    alert_type="RISK_SPIKE",
                    alert_severity="CRITICAL",
                    title="Risk Score Spike",
                    description=f"Credit default risk increased significantly by {delta:.2f} (from {intel.risk_previous:.2f} to {intel.risk_score:.2f}).",
                    db_session=db_session
                )
                if alert:
                    generated.append(alert)

        # Rule 2: Trust Drop
        if intel.trust_score is not None and intel.trust_previous is not None:
            delta = intel.trust_previous - intel.trust_score
            if delta >= 0.15:
                alert = await self.generate_alert(
                    customer_id=customer_id,
                    alert_type="TRUST_DROP",
                    alert_severity="CRITICAL",
                    title="Trust Score Drop",
                    description=f"Customer prompt payment trust score dropped by {delta:.2f} (from {intel.trust_previous:.2f} to {intel.trust_score:.2f}).",
                    db_session=db_session
                )
                if alert:
                    generated.append(alert)

        # Rule 3: Outstanding Spike
        if intel.outstanding_current is not None and intel.outstanding_previous is not None:
            if intel.outstanding_previous >= 1000.0 and intel.outstanding_current >= 1.20 * intel.outstanding_previous:
                pct = (intel.outstanding_current / intel.outstanding_previous - 1.0) * 100.0
                alert = await self.generate_alert(
                    customer_id=customer_id,
                    alert_type="OUTSTANDING_SPIKE",
                    alert_severity="WARNING",
                    title="Outstanding Exposure Spike",
                    description=f"Outstanding balance spike of {pct:.1f}% detected (increased from {intel.outstanding_previous:,.2f} to {intel.outstanding_current:,.2f}).",
                    db_session=db_session
                )
                if alert:
                    generated.append(alert)

        # Rule 4: Payment behavior deterioration (DSO/Collection score drop)
        if intel.collection_score is not None and intel.collection_previous is not None:
            delta = intel.collection_previous - intel.collection_score
            if delta >= 0.15:
                alert = await self.generate_alert(
                    customer_id=customer_id,
                    alert_type="DSO_SPIKE",
                    alert_severity="WARNING",
                    title="Payment Behavior Deterioration",
                    description=f"Average collection settlement score dropped by {delta:.2f} (from {intel.collection_previous:.2f} to {intel.collection_score:.2f}).",
                    db_session=db_session
                )
                if alert:
                    generated.append(alert)

        # Rule 5: Segment Downgrade
        prev_state = infer_prev_state(intel.trust_previous, intel.risk_previous)
        curr_state = map_state_label(intel.state)
        if prev_state != curr_state:
            is_downgrade = False
            severity = "WARNING"
            if prev_state == "healthy" and curr_state in ["monitor", "liquidity_stress"]:
                is_downgrade = True
                severity = "CRITICAL" if curr_state == "liquidity_stress" else "WARNING"
            elif prev_state == "monitor" and curr_state == "liquidity_stress":
                is_downgrade = True
                severity = "CRITICAL"

            if is_downgrade:
                alert = await self.generate_alert(
                    customer_id=customer_id,
                    alert_type="SEGMENT_DOWNGRADE",
                    alert_severity=severity,
                    title="Segment Downgrade warning",
                    description=f"Debtor segment downgraded from {prev_state.upper()} to {curr_state.upper()}.",
                    db_session=db_session
                )
                if alert:
                    generated.append(alert)

        return generated
