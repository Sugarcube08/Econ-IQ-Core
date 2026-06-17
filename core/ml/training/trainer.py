import os
import pickle
import polars as pl
import xgboost as xgb
from loguru import logger

def train_and_save_models(dataset_path: str = "training_dataset.parquet", models_dir: str = "models") -> dict:
    """
    Trains XGBoost v1 classifiers for Churn, Delinquency, and Distress, and saves them to pickle files.
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
        "distress": ("DISTRESS", "distress_v1.pkl")
    }

    report = {}

    for name, (pred_type, filename) in targets.items():
        sub_df = df.filter(pl.col("prediction_type") == pred_type)
        if sub_df.height < 5:
            logger.warning(f"ML | Insufficient samples for {pred_type} ({sub_df.height}). Skipping training.")
            continue
            
        X = sub_df.select(feature_cols).to_pandas()
        y = sub_df["target_label"].to_numpy()
        
        # Check class counts
        unique_y = set(y)
        if len(unique_y) < 2:
            logger.warning(f"ML | Only one class present for {pred_type}. Mocking basic model fit.")
            # If only one class is present, fit a dummy/simple model to ensure training succeeds
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
            
        report[name] = {
            "samples": len(y),
            "features": len(feature_cols),
            "model_path": model_path
        }
        logger.info(f"ML | Trained and saved model: {model_path}")

    return report
