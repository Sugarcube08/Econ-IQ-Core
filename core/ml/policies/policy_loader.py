from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from core.ml.policies.policy_repository import PolicyRepository

async def seed_default_policies(session: AsyncSession):
    repo = PolicyRepository(session)
    profile = await repo.get_profile_by_name("default")
    if not profile:
        profile = await repo.create_profile("default", "Default platform scoring policies")
        version = await repo.create_version(profile.profile_id, "1.0.0", is_active=True)
        
        # Register standard thresholds
        await repo.set_threshold(version.version_id, "CHURN_WINDOW_DAYS", 90, "int")
        await repo.set_threshold(version.version_id, "DELINQUENCY_WINDOW_DAYS", 45, "int")
        await repo.set_threshold(version.version_id, "DISTRESS_THRESHOLD", 0.70, "float")
        await repo.set_threshold(version.version_id, "RECOVERY_THRESHOLD", 0.65, "float")
        await repo.set_threshold(version.version_id, "RECOVERY_WINDOW_DAYS", 60, "int")
        
        # Additional thresholds to replace hardcoded values in resolvers & features
        await repo.set_threshold(version.version_id, "PURCHASE_GAP_THRESHOLD_DAYS", 90, "int")
        await repo.set_threshold(version.version_id, "REPAYMENT_DELAY_THRESHOLD_DAYS", 45, "int")
        await repo.set_threshold(version.version_id, "RISK_SCORE_THRESHOLD", 0.70, "float")
        await repo.set_threshold(version.version_id, "COLLECTION_SCORE_THRESHOLD", 0.30, "float")
        await repo.set_threshold(version.version_id, "STRESSED_RISK_THRESHOLD", 0.50, "float")
        await repo.set_threshold(version.version_id, "OVERLEVERAGED_CREDIT_THRESHOLD", 0.35, "float")
        await repo.set_threshold(version.version_id, "DISTRESSED_DISCIPLINE_THRESHOLD", 0.25, "float")
        await repo.set_threshold(version.version_id, "STRESSED_DISCIPLINE_THRESHOLD", 0.45, "float")
        
        await session.commit()

async def load_active_policies(session: AsyncSession, profile_name: str = "default") -> Dict[str, Any]:
    repo = PolicyRepository(session)
    # Ensure seeded
    await seed_default_policies(session)
    
    thresholds = await repo.get_active_thresholds_for_profile(profile_name)
    # Fallback to local default dict if DB query returns empty (e.g. in test environments)
    if not thresholds:
        return {
            "CHURN_WINDOW_DAYS": 90,
            "DELINQUENCY_WINDOW_DAYS": 45,
            "DISTRESS_THRESHOLD": 0.70,
            "RECOVERY_THRESHOLD": 0.65,
            "RECOVERY_WINDOW_DAYS": 60,
            "PURCHASE_GAP_THRESHOLD_DAYS": 90,
            "REPAYMENT_DELAY_THRESHOLD_DAYS": 45,
            "RISK_SCORE_THRESHOLD": 0.70,
            "COLLECTION_SCORE_THRESHOLD": 0.30,
            "STRESSED_RISK_THRESHOLD": 0.50,
            "OVERLEVERAGED_CREDIT_THRESHOLD": 0.35,
            "DISTRESSED_DISCIPLINE_THRESHOLD": 0.25,
            "STRESSED_DISCIPLINE_THRESHOLD": 0.45
        }
    return thresholds
