import os
import pickle

import polars as pl
import xgboost as xgb
from loguru import logger
from sklearn.metrics import (
    auc,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def train_and_save_models(dataset_path: str = "training_dataset.parquet", models_dir: str = "models", session: AsyncSession | None = None) -> dict:
    """
    Trains XGBoost v1 classifiers for Churn, Delinquency, Distress, Recovery, and State Transition, and saves them to pickle files.
    """
    os.makedirs(models_dir, exist_ok=True)
    
    if not os.path.exists(dataset_path):
        logger.warning(f"ML | Dataset file {dataset_path} not found. Cannot train models.")
        return {}

    df = pl.read_parquet(dataset_path)
    if df.is_empty():
        logger.warning("ML | Training dataset is empty. Cannot train models.")
        return {}

    feature_cols = [
        "health_score", "risk_score", "trust_score", "billing_30d", "billing_90d", "billing_180d",
        "payments_30d", "payments_90d", "payments_180d", "returns_30d", "returns_90d",
        "purchase_gap", "purchase_frequency", "payment_delay_avg", "payment_delay_trend",
        "collection_efficiency", "outstanding_current", "outstanding_ratio", "credit_utilization"
    ]
    
    targets = {
        "churn": ("CHURN", "churn_v1.pkl"),
        "delinquency": ("DELINQUENCY", "delinquency_v1.pkl"),
        "distress": ("DISTRESS", "distress_v1.pkl"),
        "recovery": ("RECOVERY", "recovery_v1.pkl"),
        "state_transition": ("STATE_TRANSITION", "state_transition_v1.pkl")
    }

    report = {}

    for name, (pred_type, filename) in targets.items():
        sub_df = df.filter(pl.col("prediction_type") == pred_type)
        if sub_df.height < 5:
            logger.warning(f"ML | Insufficient samples for {pred_type} ({sub_df.height}). Skipping training.")
            continue
            
        # P2: Only train if positive samples >= 20 (Sprint 5)
        positives = sub_df.filter(pl.col("target_label") == 1.0).height
        if positives < 20:
            logger.warning(f"ML | Skipped {name} - only {positives} positives.")
            continue

        # Sprint 4: Temporal train/test split
        dates = sub_df["snapshot_date"].sort()
        metrics = {}
        if dates.len() >= 10:
            cutoff_idx = int(dates.len() * 0.7)
            cutoff_date = dates[cutoff_idx]
            
            train_df = sub_df.filter(pl.col("snapshot_date") < cutoff_date)
            test_df = sub_df.filter(pl.col("snapshot_date") >= cutoff_date)
            
            if train_df.height >= 5 and not test_df.is_empty():
                X_train = train_df.select(feature_cols).to_pandas()
                y_train = train_df["target_label"].to_numpy()
                X_test = test_df.select(feature_cols).to_pandas()
                y_test = test_df["target_label"].to_numpy()
                
                # Check class counts in split
                if len(set(y_train)) >= 2 and len(set(y_test)) >= 2:
                    val_model = xgb.XGBClassifier(
                        n_estimators=50,
                        max_depth=3,
                        learning_rate=0.1,
                        random_state=42,
                        eval_metric="logloss"
                    )
                    val_model.fit(X_train, y_train)
                    y_prob = val_model.predict_proba(X_test)[:, 1]
                    y_pred = (y_prob > 0.5).astype(float)
                    
                    # Compute metrics
                    roc_auc = roc_auc_score(y_test, y_prob)
                    precisions, recalls, _ = precision_recall_curve(y_test, y_prob)
                    pr_auc = auc(recalls, precisions)
                    prec = precision_score(y_test, y_pred, zero_division=0)
                    rec = recall_score(y_test, y_pred, zero_division=0)
                    f1 = f1_score(y_test, y_pred, zero_division=0)
                    brier = brier_score_loss(y_test, y_prob)
                    
                    metrics = {
                        "roc_auc": float(roc_auc),
                        "pr_auc": float(pr_auc),
                        "precision": float(prec),
                        "recall": float(rec),
                        "f1": float(f1),
                        "brier": float(brier)
                    }
                    logger.info(f"ML | Validation metrics for {pred_type} (cutoff {cutoff_date}): {metrics}")

        # Train final model on FULL dataset
        X = sub_df.select(feature_cols).to_pandas()
        y = sub_df["target_label"].to_numpy()
        
        unique_y = set(y)
        if len(unique_y) < 2:
            logger.warning(f"ML | Only one class present for {pred_type}. Mocking basic model fit.")
            model = xgb.XGBClassifier(n_estimators=2, max_depth=1)
            model.fit(X, y)
        else:
            model = xgb.XGBClassifier(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                random_state=42,
                eval_metric="logloss"
            )
            model.fit(X, y)
            
        # Save model
        model_path = os.path.join(models_dir, filename)
        with open(model_path, "wb") as f:
            pickle.dump(model, f)
            
        # Expose and Persist Model Metadata (Phase A)
        prediction_count = 0
        model_id = filename.replace(".pkl", "")
        if session is not None:
            try:
                res_count = await session.execute(
                    text("SELECT COUNT(*) FROM customer_predictions WHERE model_id = :model_name"),
                    {"model_name": model_id}
                )
                prediction_count = res_count.scalar() or 0
                
                import uuid
                from datetime import UTC, datetime

                from core.ml.model_registry.model_metadata_dto import ModelMetadataDTO
                from core.ml.model_registry.model_registry_repository import ModelRegistryRepository
                
                repo = ModelRegistryRepository(session)
                existing_meta = await repo.get_model_by_name(model_id)
                meta_id = existing_meta.id if existing_meta else str(uuid.uuid4())
                
                dto = ModelMetadataDTO(
                    id=meta_id,
                    model_name=model_id,
                    version="1.0.0",
                    status="ACTIVE",
                    trained_at=datetime.now(UTC),
                    dataset_rows=len(y),
                    positives=positives,
                    negatives=len(y) - positives,
                    auc=metrics.get("roc_auc", 0.0),
                    f1=metrics.get("f1", 0.0),
                    precision=metrics.get("precision", 0.0),
                    recall=metrics.get("recall", 0.0),
                    pr_auc=metrics.get("pr_auc", 0.0),
                    brier=metrics.get("brier", 0.0),
                    prediction_count=prediction_count,
                    feedback_count=0,
                    notes=f"Trained XGBoost model for target type {pred_type}."
                )
                await repo.upsert_model_metadata(dto)
            except Exception as e:
                logger.error(f"ML | Failed to upsert model registry metadata for {model_id}: {e}")

        report[name] = {
            "samples": len(y),
            "features": len(feature_cols),
            "model_path": model_path,
            "metrics": metrics
        }
        logger.info(f"ML | Trained and saved model: {model_path}")

    return report
