from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.policies.policy_loader import load_active_policies


class PolicyService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache = None

    async def get_active_thresholds(self, profile_name: str = "default") -> dict[str, Any]:
        if self._cache is None:
            self._cache = await load_active_policies(self.session, profile_name)
        return self._cache

    async def get_threshold(self, key: str, default: Any = None, profile_name: str = "default") -> Any:
        thresholds = await self.get_active_thresholds(profile_name)
        return thresholds.get(key, default)
