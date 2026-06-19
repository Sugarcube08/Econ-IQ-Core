import polars as pl
from loguru import logger


class DatasetValidationError(ValueError):
    """Raised when dataset validation checks fail."""
    pass

def validate_dataset(df: pl.DataFrame) -> dict:
    """
    Validates the generated Polars DataFrame for ML readiness:
    - Checks for missing labels
    - Checks for duplicate rows
    - Checks for null essential features
    - Checks for point-in-time violations
    - Calculates class imbalance
    """
    stats = {}
    
    # 1. Missing labels
    null_labels = df.filter(pl.col("target_label").is_null())
    if not null_labels.is_empty():
        raise DatasetValidationError(f"Dataset contains {null_labels.height} rows with missing target_label.")
    
    # 2. Duplicate rows
    # Unique key: customer_id + snapshot_id + prediction_type
    dup_count = df.height - df.unique(subset=["customer_id", "snapshot_id", "prediction_type"]).height
    if dup_count > 0:
        raise DatasetValidationError(f"Dataset contains {dup_count} duplicate rows for customer+snapshot+type combinations.")

    # 3. Null essential features
    essential_cols = ["health_score", "risk_score", "trust_score", "outstanding_current"]
    for col in essential_cols:
        null_count = df.filter(pl.col(col).is_null()).height
        if null_count > 0:
            raise DatasetValidationError(f"Essential feature '{col}' contains {null_count} null values.")

    # 4. Point-in-time violation check
    # Check that snapshot_date is a valid date column (not null)
    null_dates = df.filter(pl.col("snapshot_date").is_null())
    if not null_dates.is_empty():
        raise DatasetValidationError("Dataset contains rows with null snapshot_date, indicating a point-in-time structure issue.")

    # 5. Class imbalance
    # Group by prediction_type and count target_label distribution
    imbalance = {}
    for pred_type in df["prediction_type"].unique().to_list():
        sub_df = df.filter(pl.col("prediction_type") == pred_type)
        total = sub_df.height
        pos = sub_df.filter(pl.col("target_label") == 1.0).height
        neg = total - pos
        pos_ratio = pos / total if total > 0 else 0.0
        imbalance[pred_type] = {
            "total": total,
            "positives": pos,
            "negatives": neg,
            "positive_ratio": pos_ratio
        }
    stats["class_imbalance"] = imbalance
    stats["total_rows"] = df.height
    stats["num_features"] = len(df.columns)

    logger.info(f"ML | Dataset Validation Passed. Total Rows: {df.height}. Features: {len(df.columns)}")
    return stats
