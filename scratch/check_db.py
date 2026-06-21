import asyncio

from sqlalchemy import func, select

from core.models.state_models import CustomerIntelligence
from core.storage.postgres import AsyncSessionLocal


async def check():
    async with AsyncSessionLocal() as s:
        # 1. Risk Analytics
        risk_stmt = select(
            func.avg(CustomerIntelligence.risk_score).label("avg_risk"),
            func.sum(CustomerIntelligence.outstanding_current).label("total_outstanding")
        )
        risk_res = await s.execute(risk_stmt)
        risk_row = risk_res.mappings().one()
        avg_risk = float(risk_row["avg_risk"] or 0.0)
        total_outstanding = float(risk_row["total_outstanding"] or 0.0)

        high_risk_stmt = select(
            func.sum(CustomerIntelligence.outstanding_current)
        ).where(CustomerIntelligence.risk_score > 0.6)
        high_risk_res = await s.execute(high_risk_stmt)
        high_risk_exposure = float(high_risk_res.scalar() or 0.0)
        high_risk_exposure_pct = (high_risk_exposure / total_outstanding * 100.0) if total_outstanding > 0 else 0.0
        
        print(f"Average risk score: {avg_risk}")
        print(f"High risk exposure percentage: {high_risk_exposure_pct}%")

if __name__ == "__main__":
    asyncio.run(check())
