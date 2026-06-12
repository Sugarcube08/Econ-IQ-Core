from abc import ABC, abstractmethod
from typing import Any

import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from core.prediction.contracts.prediction_contracts import ModelMetadataContract


class IModelEstimator(ABC):
    """
    Standard interface contract for all predictive model estimators.
    """

    @abstractmethod
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> Any:
        """
        Runs model inference on the provided feature DataFrame for a given customer.
        """
        pass

    @abstractmethod
    def get_metadata(self) -> ModelMetadataContract:
        """
        Returns model structure and version metadata details.
        """
        pass


class IModelRegistry(ABC):
    """
    Registry interface to store, version, and swap prediction models dynamically.
    """

    @abstractmethod
    def register_model(self, model_type: str, version: str, estimator: IModelEstimator) -> None:
        """Registers a model estimator for a specific target type and version."""
        pass

    @abstractmethod
    def get_model(self, model_type: str, version: str | None = None) -> IModelEstimator:
        """Retrieves a registered model estimator (defaulting to the latest version)."""
        pass


class IInferenceEngine(ABC):
    """
    Engine to coordinate context loads, feature engineering, and estimator execution.
    """

    @abstractmethod
    async def run_inference(self, session: AsyncSession, customer_id: str, model_type: str, version: str | None = None) -> Any:
        """
        Orchestrates the end-to-end inference lifecycle for a single customer.
        """
        pass


class IPredictionMonitor(ABC):
    """
    Inference monitoring interface to track data drift, predict output variance, and log audit entries.
    """

    @abstractmethod
    def log_prediction(self, customer_id: str, model_type: str, version: str, prediction_output: Any) -> None:
        """Logs prediction values and features snapshot for drift and consistency tracking."""
        pass
