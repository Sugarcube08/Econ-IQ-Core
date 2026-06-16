from enum import StrEnum
from typing import Any

import polars as pl
from loguru import logger
from pydantic import BaseModel


class DataHealthStatus(StrEnum):
    HEALTHY = "HEALTHY"
    SPARSE = "SPARSE"
    NO_ACTIVITY = "NO_ACTIVITY"
    PARTIAL = "PARTIAL"
    CORRUPTED = "CORRUPTED"
    TRANSIENT_FAILURE = "TRANSIENT_FAILURE"


class ValidationReport(BaseModel):
    is_valid: bool
    status: DataHealthStatus
    details: dict[str, Any]


class RuntimeIntelligenceCollapseError(RuntimeError):
    """Raised when the intelligence runtime produces degenerate or context-starved outputs."""

    pass


class IntelligenceIntegrityValidator:
    """
    Detects pipeline integrity failures such as state collapse,
    feature starvation, and degenerate trajectories.
    """

    def validate(self, intelligence_df: pl.DataFrame) -> ValidationReport:
        if intelligence_df.is_empty():
            return ValidationReport(
                is_valid=True,
                status=DataHealthStatus.NO_ACTIVITY,
                details={"message": "Empty dataframe, no activity to validate."}
            )

        total = intelligence_df.height
        is_valid = True
        status = DataHealthStatus.HEALTHY
        details = {
            "total_records": total,
            "columns": intelligence_df.columns,
        }

        # 1. State Diversity Check (Entropy) - skip if only 1 customer
        num_customers = intelligence_df["customer_id"].n_unique() if "customer_id" in intelligence_df.columns else 0
        state_counts = intelligence_df["behavioral_state"].value_counts()
        details["num_customers"] = num_customers
        details["state_counts"] = state_counts.to_dicts()

        if num_customers > 1:
            for row in state_counts.to_dicts():
                ratio = row["count"] / total
                if ratio > 0.95 and total > 5:
                    logger.error(
                        f"INTEGRITY FAILURE: State Collapse detected for '{row['behavioral_state']}' ({ratio:.1%})"
                    )
                    is_valid = False
                    status = DataHealthStatus.CORRUPTED
                    details["error"] = f"State collapse into '{row['behavioral_state']}'"
                    return ValidationReport(is_valid=is_valid, status=status, details=details)

            # 2. Feature Entropy (Diversity of scores)
            unique_trust = intelligence_df["trust_score"].n_unique()
            details["unique_trust_scores"] = unique_trust
            if unique_trust == 1 and total > 5:
                logger.error("INTEGRITY FAILURE: Zero trust score entropy - all customers identical")
                is_valid = False
                status = DataHealthStatus.CORRUPTED
                details["error"] = "Zero feature entropy detected"
                return ValidationReport(is_valid=is_valid, status=status, details=details)
        else:
            unique_trust = intelligence_df["trust_score"].n_unique()
            details["unique_trust_scores"] = unique_trust

        # 3. Historical Context Starvation Check
        # If customers have zero events_window, this is a sign of starvation
        if "events_window" in intelligence_df.columns and total > 0:
            max_events = int(intelligence_df["events_window"].max() or 0)
            details["max_events_window"] = max_events
            if max_events == 0:
                logger.warning("INTEGRITY WARNING: Total historical context starvation detected (all windows empty)")
                is_valid = False
                # If it's a single customer, they might just have no activity in this range
                status = DataHealthStatus.NO_ACTIVITY if num_customers <= 1 else DataHealthStatus.SPARSE
                details["error"] = "Historical context starvation: all rolling windows are empty"
                return ValidationReport(is_valid=is_valid, status=status, details=details)

        if "trajectory" in intelligence_df.columns:
            unique_traj = intelligence_df["trajectory"].n_unique()
            details["unique_trajectories"] = unique_traj
            if unique_traj == 1 and total > 20:
                logger.warning("Extremely low trajectory diversity detected")

        return ValidationReport(is_valid=is_valid, status=status, details=details)

