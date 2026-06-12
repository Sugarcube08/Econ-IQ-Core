from loguru import logger

from core.prediction.interfaces.estimator import IModelEstimator, IModelRegistry


class ModelRegistry(IModelRegistry):
    """
    Thread-safe Singleton Model Registry implementing the IModelRegistry contract.
    """
    _instance = None
    _models: dict[tuple[str, str], IModelEstimator] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def register_model(self, model_type: str, version: str, estimator: IModelEstimator) -> None:
        key = (model_type.upper(), version)
        self._models[key] = estimator
        logger.info(f"Successfully registered model [{model_type.upper()}] version [{version}] in Registry.")

    def get_model(self, model_type: str, version: str | None = None) -> IModelEstimator:
        m_type = model_type.upper()
        
        # Resolve latest version if not explicitly requested
        if not version:
            matching_keys = [k for k in self._models.keys() if k[0] == m_type]
            if not matching_keys:
                raise KeyError(f"No model of type [{m_type}] registered in Registry.")
            # Simple sorting by version string (semantic versioning)
            matching_keys.sort(key=lambda k: [int(x) if x.isdigit() else x for x in k[1].split(".")])
            key = matching_keys[-1]
            logger.debug(f"Resolved latest model version for [{m_type}] to version [{key[1]}].")
        else:
            key = (m_type, version)
            if key not in self._models:
                raise KeyError(f"Model type [{m_type}] version [{version}] not found in Registry.")

        return self._models[key]


# Global Model Registry instance
model_registry = ModelRegistry()
