# Prediction Provenance & Reproducibility Lineage

Prediction Provenance guarantees that every single score emitted by the EconIQ intelligence platform can be forensically audited back to the exact snapshot, features vector, and model parameters that produced it.

## Provenance Metadata Payload

Every prediction stored in `customer_predictions` contains an enriched `metadata_json` field carrying the following metadata attributes:

```json
{
  "prediction": 0.82,
  "confidence": 0.55,
  "model_name": "recovery_v1",
  "model_version": "1.0.0",
  "trained_at": "2026-06-18",
  "dataset_rows": 2500,
  "prediction_source": "ML",
  "label_type": "semi_synthetic",
  "snapshot_date": "2026-06-18",
  "features_hash": "abcd1234"
}
```

### Metadata Fields Detail
- **`prediction`**: The raw probability output (ranges from `0.0` to `1.0`).
- **`confidence`**: The calculated reliability confidence score accounting for model performance, label quality, and data density.
- **`model_name`**: The registered name of the model identifier (e.g. `recovery_v1`, `distress_v1`).
- **`model_version`**: The model's semantic version from the Model Registry.
- **`trained_at`**: ISO date string representing when this specific model run was serialized.
- **`dataset_rows`**: The size of the training dataset at the time of model generation.
- **`prediction_source`**: Indicates whether the prediction was generated using a trained machine learning model (`ML`) or a heuristic fallback model (`HEURISTIC`).
- **`label_type`**: The categorization of target variables (e.g., `semi_synthetic` for derived transitions, or `empirical`).
- **`snapshot_date`**: The business date representing the point-in-time state of the customer.
- **`features_hash`**: A sha256 checksum of the customer features payload. This prevents silent data drifts and guarantees feature-to-prediction identity.

## Forensic Replayability

If an outcome is queried by an auditor:
1. Fetch the prediction record containing `snapshot_id` and `features_hash`.
2. Retrieve the immutable snapshot from `feature_snapshots` where `snapshot_id = snapshot_id`.
3. Compute the sha256 of the snapshot payload and verify it matches `features_hash`.
4. Load the pickle model file mapping to `model_name` and `model_version`.
5. Re-run inference to demonstrate 100% deterministic prediction parity.
