from abc import ABC, abstractmethod
import polars as pl
from typing import Any


class IModelEstimator(ABC):
    """
    Standard interface contract for all predictive models in Econiq Core.
    Implementations will wrap XGBoost, LightGBM, or Deep Learning models.
    """

    @abstractmethod
    def predict(self, customer_id: str, features_df: pl.DataFrame) -> Any:
        """
        Runs model inference on the provided feature DataFrame for a given customer.
        """
        pass
