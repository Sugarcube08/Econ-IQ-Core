from typing import Dict, Any, List, Optional

class PredictionModelRegistry:
    """
    Registry for machine learning / heuristic prediction models.
    Allows registering and retrieving models by ID.
    """
    def __init__(self):
        self._registry: Dict[str, Any] = {}

    def register_model(self, model_id: str, model: Any) -> None:
        self._registry[model_id] = model

    def get_model(self, model_id: str) -> Optional[Any]:
        return self._registry.get(model_id)

    def list_models(self) -> List[str]:
        return list(self._registry.keys())

# Global registry instance
prediction_registry = PredictionModelRegistry()
