import polars as pl
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.datasets.dataset_repository import DatasetRepository
from core.ml.datasets.dataset_validator import validate_dataset


async def build_training_dataset(session: AsyncSession, output_path: str = "training_dataset.parquet") -> tuple[pl.DataFrame, dict]:
    """
    Builds, validates, and persists the training dataset from PostgreSQL FeatureSnapshots and PredictionOutcomes.
    """
    repo = DatasetRepository(session)
    records = await repo.get_raw_dataset_records()
    
    if not records:
        # Return an empty DataFrame matching the schema structure
        df = pl.DataFrame(schema={
            "snapshot_id": pl.String,
            "customer_id": pl.String,
            "snapshot_date": pl.Date,
            "health_score": pl.Float64,
            "risk_score": pl.Float64,
            "trust_score": pl.Float64,
            "billing_30d": pl.Float64,
            "billing_90d": pl.Float64,
            "billing_180d": pl.Float64,
            "payments_30d": pl.Float64,
            "payments_90d": pl.Float64,
            "payments_180d": pl.Float64,
            "returns_30d": pl.Float64,
            "returns_90d": pl.Float64,
            "purchase_gap": pl.Int64,
            "purchase_frequency": pl.Float64,
            "payment_delay_avg": pl.Float64,
            "payment_delay_trend": pl.Float64,
            "collection_efficiency": pl.Float64,
            "outstanding_current": pl.Float64,
            "outstanding_ratio": pl.Float64,
            "credit_utilization": pl.Float64,
            "prediction_type": pl.String,
            "target_label": pl.Float64,
            "predicted_value": pl.Float64,
            "is_correct": pl.Boolean
        })
        stats = {"total_rows": 0, "num_features": len(df.columns), "class_imbalance": {}}
        df.write_parquet(output_path)
        return df, stats

    df = pl.DataFrame(records)
    
    # Cast dates and types explicitly to guarantee clean Parquet types
    df = df.with_columns([
        pl.col("snapshot_date").cast(pl.Date),
        pl.col("target_label").cast(pl.Float64),
        pl.col("predicted_value").cast(pl.Float64),
        pl.col("is_correct").cast(pl.Boolean)
    ])
    
    # Run validation
    stats = validate_dataset(df)
    
    # Persist as Parquet
    df.write_parquet(output_path)
    
    return df, stats
