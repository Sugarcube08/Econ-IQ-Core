from typing import Any

from loguru import logger

from core.prediction.interfaces.estimator import IPredictionMonitor


class PredictionMonitor(IPredictionMonitor):
    """
    Standard implementation of IPredictionMonitor.
    """

    def log_prediction(self, customer_id: str, model_type: str, version: str, prediction_output: Any) -> None:
        score = getattr(prediction_output, "score", None)
        confidence = getattr(prediction_output, "confidence", None)
        
        logger.info(
            f"[Telemetry] Logged Prediction | Customer: [{customer_id}] | "
            f"Model: [{model_type.upper()}] | Version: [{version}] | "
            f"Score: {score} | Confidence: {confidence}"
        )
        
        # Real-time sanity checks (Drift Warning logs)
        if score is not None:
            if score > 0.95 or score < 0.05:
                logger.warning(
                    f"[Prediction Alert] Boundary score detected for customer [{customer_id}] | "
                    f"Value: {score}. Check for target leakage or data anomalies."
                )


# Global Prediction Monitor instance
prediction_monitor = PredictionMonitor()
