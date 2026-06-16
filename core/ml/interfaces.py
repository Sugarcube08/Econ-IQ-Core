from abc import ABC, abstractmethod
from typing import Any, Dict

class IFeatureProvider(ABC):
    """
    Interface to retrieve features from the Feature Store boundary.
    """
    @abstractmethod
    async def get_features(self, customer_id: str) -> Dict[str, Any]:
        pass

class IPredictionModel(ABC):
    """
    Interface for ML prediction models (XGBoost, LightGBM).
    """
    @abstractmethod
    async def predict(self, features: Dict[str, Any]) -> Dict[str, Any]:
        pass
