from typing import Any

from core.prediction.interfaces.estimator import IPredictionMonitor


class PredictionMonitor(IPredictionMonitor):
    """
    Standard implementation of IPredictionMonitor.
    """
    def log_prediction(self, customer_id: str, model_type: str, version: str, prediction_output: Any) -> None:
        pass

# Global Prediction Monitor instance
prediction_monitor = PredictionMonitor()
