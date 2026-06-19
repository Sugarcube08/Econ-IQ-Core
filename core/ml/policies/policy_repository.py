from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.policies.policy_models import MLPolicyProfile, PolicyThreshold, PolicyVersion


class PolicyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_profile_by_name(self, name: str) -> MLPolicyProfile | None:
        stmt = select(MLPolicyProfile).where(MLPolicyProfile.name == name)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def create_profile(self, name: str, description: str | None = None) -> MLPolicyProfile:
        profile = MLPolicyProfile(name=name, description=description, is_active=True)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def create_version(self, profile_id: str, version_code: str, is_active: bool = True) -> PolicyVersion:
        if is_active:
            # Deactivate other versions for this profile
            await self.session.execute(
                update(PolicyVersion)
                .where(PolicyVersion.profile_id == profile_id)
                .values(is_active=False)
            )
        version = PolicyVersion(profile_id=profile_id, version_code=version_code, is_active=is_active)
        self.session.add(version)
        await self.session.flush()
        return version

    async def set_threshold(self, version_id: str, key: str, value: Any, value_type: str) -> PolicyThreshold:
        stmt = select(PolicyThreshold).where(
            PolicyThreshold.version_id == version_id,
            PolicyThreshold.key == key
        )
        res = await self.session.execute(stmt)
        existing = res.scalar_one_or_none()
        if existing:
            existing.value = str(value)
            existing.value_type = value_type
            return existing
        else:
            thresh = PolicyThreshold(
                version_id=version_id,
                key=key,
                value=str(value),
                value_type=value_type
            )
            self.session.add(thresh)
            await self.session.flush()
            return thresh

    async def get_active_thresholds_for_profile(self, profile_name: str) -> dict[str, Any]:
        stmt = (
            select(PolicyThreshold)
            .join(PolicyVersion, PolicyVersion.version_id == PolicyThreshold.version_id)
            .join(MLPolicyProfile, MLPolicyProfile.profile_id == PolicyVersion.profile_id)
            .where(MLPolicyProfile.name == profile_name)
            .where(PolicyVersion.is_active)
            .where(MLPolicyProfile.is_active)
        )
        res = await self.session.execute(stmt)
        thresholds = res.scalars().all()
        
        result = {}
        for t in thresholds:
            if not hasattr(t, "value_type"):
                continue
            if t.value_type == "int":
                result[t.key] = int(t.value)
            elif t.value_type == "float":
                result[t.key] = float(t.value)
            elif t.value_type == "bool":
                result[t.key] = t.value.lower() in ("true", "1", "yes")
            else:
                result[t.key] = t.value
        return result
