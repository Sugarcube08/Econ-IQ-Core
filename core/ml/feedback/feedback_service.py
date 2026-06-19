import uuid
from datetime import UTC, datetime

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.feedback.feedback_metrics import compute_binary_metrics
from core.ml.feedback.feedback_repository import FeedbackRepository, PredictionFeedbackDTO
from core.models.state_models import CustomerPrediction, PredictionOutcome


async def calculate_and_persist_feedback_metrics(session: AsyncSession) -> list[PredictionFeedbackDTO]:
    """
    Retrieves all evaluated outcomes, groups them by model and prediction type,
    calculates classification metrics, and persists the feedback reports.
    """
    feedback_repo = FeedbackRepository(session)

    # Query all outcomes joined with the model ID from predictions
    stmt = (
        select(PredictionOutcome, CustomerPrediction.model_id)
        .join(CustomerPrediction, PredictionOutcome.prediction_id == CustomerPrediction.prediction_id)
    )
    res = await session.execute(stmt)
    rows = res.all()

    # Group outcomes by (model_id, prediction_type)
    groups: dict[tuple[str, str], list[PredictionOutcome]] = {}
    for outcome, model_id in rows:
        key = (model_id, outcome.prediction_type)
        if key not in groups:
            groups[key] = []
        groups[key].append(outcome)

    persisted_feedback = []

    for (model_id, pred_type), outcomes in groups.items():
        y_true = [float(o.actual_value) for o in outcomes]
        y_prob = [float(o.predicted_value) for o in outcomes]

        # Compute binary metrics
        metrics = compute_binary_metrics(y_true, y_prob)

        feedback_dto = PredictionFeedbackDTO(
            feedback_id=str(uuid.uuid4()),
            model_id=model_id,
            prediction_type=pred_type,
            samples=len(outcomes),
            accuracy=metrics["accuracy"],
            precision=metrics["precision"],
            recall=metrics["recall"],
            f1=metrics["f1"],
            roc_auc=metrics["roc_auc"],
            brier_score=metrics["brier_score"],
            ece=metrics["ece"],
            created_at=datetime.now(UTC)
        )

        await feedback_repo.insert_feedback(feedback_dto)
        persisted_feedback.append(feedback_dto)
        logger.info(f"ML | Feedback generated for {model_id} ({pred_type}) over {len(outcomes)} samples.")

    return persisted_feedback
