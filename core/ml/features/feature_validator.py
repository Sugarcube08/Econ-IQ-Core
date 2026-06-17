import hashlib
import json
from datetime import date
from core.ml.shared.enums import CustomerState, RiskDirection, TrustDirection
from core.ml.shared.types import FeatureSnapshotDTO

class SnapshotValidationError(ValueError):
    """Raised when feature snapshot validation fails."""
    pass

def compute_feature_hash(customer_id: str, snapshot_date: date, payload: dict) -> str:
    """Consistently computes a SHA-256 hash of a customer's feature snapshot data."""
    payload_str = json.dumps(payload, sort_keys=True)
    raw = f"{customer_id}{snapshot_date.isoformat()}{payload_str}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def validate_snapshot(dto: FeatureSnapshotDTO) -> None:
    """
    Validates a FeatureSnapshotDTO against business constraints:
    - Health Score between 0 and 1
    - Risk Score between 0 and 1
    - Trust Score between 0 and 1
    - Outstanding >= 0
    - State is a valid CustomerState enum
    - Directions are valid Risk/Trust Direction enums
    - Feature Hash matches computed hash
    """
    # 1. Health Score check
    if dto.health_score is not None:
        if not (0.0 <= dto.health_score <= 1.0):
            raise SnapshotValidationError(f"health_score must be between 0 and 1, got {dto.health_score}")

    # 2. Risk Score check
    if dto.risk_score is not None:
        if not (0.0 <= dto.risk_score <= 1.0):
            raise SnapshotValidationError(f"risk_score must be between 0 and 1, got {dto.risk_score}")

    # 3. Trust Score check
    if dto.trust_score is not None:
        if not (0.0 <= dto.trust_score <= 1.0):
            raise SnapshotValidationError(f"trust_score must be between 0 and 1, got {dto.trust_score}")

    # 4. Outstanding check
    if dto.outstanding_current is not None:
        # Avoid float precision issues slightly below 0 (e.g. -1e-9)
        if dto.outstanding_current < -1e-6:
            raise SnapshotValidationError(f"outstanding_current must be >= 0, got {dto.outstanding_current}")

    # 5. State check
    if dto.current_state is not None:
        try:
            CustomerState(dto.current_state)
        except ValueError:
            raise SnapshotValidationError(f"Invalid current_state: {dto.current_state}")

    # 6. Directions check
    if dto.risk_direction is not None:
        try:
            RiskDirection(dto.risk_direction)
        except ValueError:
            raise SnapshotValidationError(f"Invalid risk_direction: {dto.risk_direction}")

    if dto.trust_direction is not None:
        try:
            TrustDirection(dto.trust_direction)
        except ValueError:
            raise SnapshotValidationError(f"Invalid trust_direction: {dto.trust_direction}")

    # 7. Hash verification
    expected_hash = compute_feature_hash(dto.customer_id, dto.snapshot_date, dto.feature_payload_json)
    if dto.feature_hash != expected_hash:
        raise SnapshotValidationError(f"feature_hash mismatch: expected {expected_hash}, got {dto.feature_hash}")
