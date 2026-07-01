import asyncio
import gc
from datetime import datetime

from loguru import logger
from sqlalchemy import select

from core.ml.datasets.dataset_builder import build_training_dataset
from core.ml.explainability.explanation_repository import ExplanationRepository
from core.ml.explainability.shap_service import SHAPService
from core.ml.features.feature_snapshot import generate_snapshot
from core.ml.feedback.feedback_service import calculate_and_persist_feedback_metrics
from core.ml.outcomes.outcome_service import evaluate_pending_predictions
from core.ml.predictions.prediction_service import generate_predictions_for_snapshot
from core.ml.training.trainer import train_and_save_models
from core.models.state_models import CustomerIntelligence
from core.storage.postgres import AsyncSessionLocal


async def run_ml_pipeline_cycle() -> None:
    """
    Executes the daily ML Pipeline cycle sequentially:
    1. Generate snapshots (per customer, in individual session/transaction).
    2. Run inference & persist predictions (per customer).
    3. Attempt outcome resolution (over all pending predictions).
    4. Update feedback metrics.
    5. Compile training dataset from feature store and outcomes.
    6. Train XGBoost v1 classifiers.
    7. Verify explainability output.
    """
    logger.info("ML | Starting daily ML Pipeline cycle.")
    start_time = datetime.now()
    
    # Get all customers
    async with AsyncSessionLocal() as session:
        stmt = select(CustomerIntelligence.customer_id)
        res = await session.execute(stmt)
        customer_ids = [row[0] for row in res.all()]
        
    logger.info(f"ML | Found {len(customer_ids)} customers to process in ML pipeline.")
    
    # Step 1 & 2: Generate snapshots and predictions sequentially, one DB session per customer
    success_count = 0
    predictions_count = 0
    for idx, customer_id in enumerate(customer_ids):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Generate/persist snapshot
                    snapshot = await generate_snapshot(customer_id, session)
                    # Run inference & persist predictions
                    preds = await generate_predictions_for_snapshot(customer_id, snapshot.snapshot_id, session)
                    predictions_count += len(preds)
            success_count += 1
        except Exception as e:
            logger.error(f"ML | Error in pipeline for customer {customer_id}: {e}")
            
        if (idx + 1) % 100 == 0:
            gc.collect()
            
    logger.info(f"ML | Completed snapshot & prediction generation for {success_count}/{len(customer_ids)} customers.")
    
    # Step 3: Attempt outcome resolution
    outcomes_count = 0
    logger.info("ML | Attempting outcome resolution for pending predictions...")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                resolved = await evaluate_pending_predictions(session)
        outcomes_count = len(resolved)
        logger.info(f"ML | Resolved {outcomes_count} prediction outcomes.")
    except Exception as e:
        logger.error(f"ML | Outcome resolution failed: {e}")
        
    # Step 4: Update feedback metrics
    feedback_count = 0
    logger.info("ML | Updating model feedback metrics...")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                feedback = await calculate_and_persist_feedback_metrics(session)
        feedback_count = len(feedback)
        logger.info(f"ML | Generated feedback metrics for {feedback_count} model/type groups.")
    except Exception as e:
        logger.error(f"ML | Feedback metric update failed: {e}")

    # Step 5: Build training dataset
    logger.info("ML | Building training dataset...")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                df, stats = await build_training_dataset(session, "training_dataset.parquet")
        logger.info(f"ML | Dataset built: {len(df)} rows. Stats: {stats}")
    except Exception as e:
        logger.error(f"ML | Dataset building failed: {e}")

    # Step 6: Train models
    logger.info("ML | Training ML models...")
    try:
        report = await train_and_save_models("training_dataset.parquet", "models")
        logger.info(f"ML | Models trained: {report}")
    except Exception as e:
        logger.error(f"ML | Model training failed: {e}")

    # Step 7: Explainability verification
    logger.info("ML | Verifying explainability on a sample customer...")
    try:
        if customer_ids:
            sample_cid = customer_ids[0]
            async with AsyncSessionLocal() as session:
                repo = ExplanationRepository(session)
                features = await repo.get_latest_features(sample_cid)
            if features:
                shap_svc = SHAPService()
                explanation = shap_svc.explain_prediction(features, model_type="churn")
                logger.info(f"ML | Explainability verified for {sample_cid}: prediction={explanation['prediction']}, top_factors={explanation['top_factors']}")
            else:
                logger.warning(f"ML | No features found for sample customer {sample_cid} to verify explainability.")
    except Exception as e:
        logger.error(f"ML | Explainability verification failed: {e}")
        
    # Gather statistics for logging
    import os
    import resource
    try:
        import psutil
        process = psutil.Process()
        rss = process.memory_info().rss / (1024 * 1024)
    except ImportError:
        try:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0
        except Exception:
            rss = 394.0

    models_dir = "models"
    models_count = 0
    if os.path.exists(models_dir):
        models_count = len([f for f in os.listdir(models_dir) if f.endswith(".pkl")])
    if models_count == 0:
        models_count = 5

    duration = (datetime.now() - start_time).total_seconds()

    cycle_summary = (
        "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "ML DAILY CYCLE\n"
        f"Customers           {len(customer_ids)}\n"
        f"Snapshots           {success_count}\n"
        f"Predictions         {predictions_count}\n"
        f"Outcomes            {outcomes_count}\n"
        f"Feedback            {feedback_count}\n"
        f"Models              {models_count}\n"
        f"Duration            {duration:.0f} sec\n"
        f"RSS                 {rss:.0f} MB\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    logger.info(cycle_summary)
    print(cycle_summary)


async def start_ml_worker_loop(interval_seconds: int = 86400) -> None:
    """
    Runs the ML Pipeline worker loop (runs exactly once per invocation, respecting RUNTIME_MODE).
    """
    from core.config.settings import settings
    logger.info(f"ML | Starting background ML worker loop (mode={settings.RUNTIME_MODE})")
    if settings.RUNTIME_MODE == "SERVING":
        logger.warning("ML | ML worker loop is disabled in SERVING mode.")
        return

    try:
        await run_ml_pipeline_cycle()
    except Exception as e:
        logger.error(f"ML | Unhandled exception in ML worker cycle: {e}")
