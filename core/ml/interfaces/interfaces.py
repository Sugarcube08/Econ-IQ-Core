from abc import ABC, abstractmethod
from typing import Any


class IFeatureProvider(ABC):
    """
    Interface to retrieve features from the Feature Store boundary.
    """
    @abstractmethod
    async def get_features(self, customer_id: str) -> dict[str, Any]:
        pass

class IPredictionModel(ABC):
    """
    Interface for ML prediction models (XGBoost, LightGBM).
    """
    @abstractmethod
    async def predict(self, features: dict[str, Any]) -> dict[str, Any]:
        pass
