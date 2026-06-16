import time
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import polars as pl
from loguru import logger
from core.observability.failure_registry import FailureRegistry
from prometheus_client import Counter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.intelligence.validator import DataHealthStatus, IntelligenceIntegrityValidator, ValidationReport
from core.repositories.intelligence import IntelligenceRepository
from core.schemas.customers import (
    CustomerDeltaSchema,
    CustomerDetailSchema,
    CustomerProfileResponseData,
    CustomerScoreSchema,
    OrgContributionSchema,
)

# --- LAYER 4: PROMETHEUS METRICS ---
INTELLIGENCE_FAILURES = Counter(
    "intelligence_failures_total", 
    "Total unexpected intelligence computation exceptions", 
    ["error_type"]
)
VALIDATOR_STARVATION = Counter(
    "validator_starvation_total", 
    "Total validation reports indicating historical context starvation"
)
FALLBACK_RESPONSES = Counter(
    "fallback_responses_total", 
    "Total fallback/degraded responses served to frontend", 
    ["fallback_mode"]
)
DEGRADED_REQUESTS = Counter(
    "degraded_customer_requests_total", 
    "Total degraded customer profile requests"
)
STALE_CONNECTION_SUSPICIONS = Counter(
    "stale_connection_suspicions_total", 
    "Total counts of suspected connection pool or FDW stale states"
)


class ResilientOrchestrationMode(StrEnum):
    FULL = "FULL"
    PARTIAL = "PARTIAL"
    SNAPSHOT = "SNAPSHOT"
    NO_ACTIVITY = "NO_ACTIVITY"
    DEGRADED = "DEGRADED"


class ResilientExecutionResult(BaseModel):
    mode: ResilientOrchestrationMode
    health_status: DataHealthStatus
    data: CustomerProfileResponseData
    forensics: dict[str, Any]
    metadata: dict[str, Any]


class ResilientIntelligenceOrchestrator:
    def __init__(self, db: AsyncSession, correlation_id: str | None = None):
        self.db = db
        self.correlation_id = correlation_id or "UNKNOWN"
        self.validator = IntelligenceIntegrityValidator()
        self.repo = IntelligenceRepository(db)

    async def capture_forensics(
        self, 
        customer_id: str, 
        err: Exception | None, 
        df: pl.DataFrame | None = None, 
        stage: str = "initial"
    ) -> dict[str, Any]:
        """Layer 6: Capture complete forensic evidence before fallback triggers."""
        forensics = {
            "customer_id": customer_id,
            "correlation_id": self.correlation_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "stage": stage,
            "error_message": str(err) if err else None,
            "error_type": err.__class__.__name__ if err else None,
        }

        # 1. DB Connection & Transaction state
        try:
            pid_res = await self.db.execute(text("SELECT pg_backend_pid()"))
            pid = pid_res.scalar()
            forensics["db_pid"] = pid

            tx_age_res = await self.db.execute(text(
                "SELECT age(backend_xmin) FROM pg_stat_activity WHERE pid = pg_backend_pid()"
            ))
            tx_age = tx_age_res.scalar()
            forensics["transaction_age"] = str(tx_age) if tx_age else "0"

            tx_state_res = await self.db.execute(text(
                "SELECT state, query_start, state_change FROM pg_stat_activity WHERE pid = pg_backend_pid()"
            ))
            tx_state = tx_state_res.mappings().one_or_none()
            if tx_state:
                forensics["db_transaction_state"] = {
                    "state": tx_state.get("state"),
                    "query_start": tx_state.get("query_start").isoformat() if tx_state.get("query_start") else None,
                    "state_change": tx_state.get("state_change").isoformat() if tx_state.get("state_change") else None,
                }
        except Exception as e:
            forensics["db_diagnostics_error"] = f"Failed to query DB stats: {e}"

        # 2. DataFrame Metadata
        if df is not None:
            forensics["dataframe"] = {
                "shape": list(df.shape),
                "columns": list(df.columns),
            }
            if "events_window" in df.columns:
                events_window_col = df["events_window"]
                forensics["dataframe"]["events_window"] = {
                    "max": int(events_window_col.max() or 0),
                    "min": int(events_window_col.min() or 0),
                    "mean": float(events_window_col.mean() or 0.0),
                }
        
        # 3. Check cache availability
        try:
            cached = await self.repo.get_latest_customer_state(customer_id)
            forensics["cache_status"] = "AVAILABLE" if cached else "MISSING"
        except Exception:
            forensics["cache_status"] = "UNAVAILABLE_DUE_TO_DB_ERROR"

        logger.warning(f"Forensics captured for starvation/failure on customer {customer_id}: {forensics}")
        return forensics

    async def execute_resilient(
        self, 
        customer_id: str, 
        customer_basic: dict[str, Any], 
        curr_ctx: Any, 
        prev_ctx: Any,
        orchestrator: Any,
        start_time: float
    ) -> ResilientExecutionResult:
        """
        Layer 2: Resilient orchestration engine that manages graceful degradation.
        Evaluates data health and serves the highest-fidelity payload available.
        """
        forensics = {}

        try:
            # 1. Try FULL execution path (dynamic recomputation)
            curr_df = await orchestrator.run_dynamic([customer_id], curr_ctx)
            
            # Check validation health
            report: ValidationReport = getattr(curr_df, "validation_report", None)
            if not report:
                report = self.validator.validate(curr_df)

            if not report.is_valid:
                # Suspect stale connection/pool if graph has data but validator reports starvation
                VALIDATOR_STARVATION.inc()
                forensics = await self.capture_forensics(customer_id, None, curr_df, stage="current_validation_failed")
                
                # Check for suspicion of stale pool / FDW connection
                # (If total_records > 0 but rolling windows are starved)
                if report.status == DataHealthStatus.NO_ACTIVITY and curr_df.height > 0:
                    STALE_CONNECTION_SUSPICIONS.inc()
                
                # Degrade to snapshot/cache fallback
                return await self._degrade_to_snapshot_or_cache(
                    customer_id, customer_basic, curr_ctx, prev_ctx, orchestrator, start_time, report.status, forensics
                )

            # If current window is healthy, try previous window for deltas
            try:
                prev_df = await orchestrator.run_dynamic([customer_id], prev_ctx)
                prev_report: ValidationReport = getattr(prev_df, "validation_report", None)
                if not prev_report:
                    prev_report = self.validator.validate(prev_df)

                if not prev_report.is_valid:
                    # Previous window starved, degrade previous to snapshot/zeros while keeping current full
                    forensics = await self.capture_forensics(customer_id, None, prev_df, stage="previous_validation_failed")
                    VALIDATOR_STARVATION.inc()
                    
                    return self._build_partial_response(
                        customer_id, customer_basic, curr_df, prev_df, curr_ctx, prev_ctx, start_time, forensics
                    )

                # Both windows healthy -> FULL Mode
                return self._build_full_response(
                    customer_id, customer_basic, curr_df, prev_df, curr_ctx, prev_ctx, start_time
                )

            except Exception as prev_err:
                # Previous window crashed, log and degrade previous
                INTELLIGENCE_FAILURES.labels(error_type=prev_err.__class__.__name__).inc()
                forensics = await self.capture_forensics(customer_id, prev_err, stage="previous_calculation_exception")
                return self._build_partial_response(
                    customer_id, customer_basic, curr_df, pl.DataFrame(), curr_ctx, prev_ctx, start_time, forensics
                )

        except Exception as curr_err:
            # Current window crashed completely (e.g. database error, syntax, arrow crash)
            INTELLIGENCE_FAILURES.labels(error_type=curr_err.__class__.__name__).inc()
            DEGRADED_REQUESTS.inc()
            forensics = await self.capture_forensics(customer_id, curr_err, stage="current_calculation_exception")
            
            return await self._degrade_to_cache_or_minimal(
                customer_id, customer_basic, curr_ctx, prev_ctx, start_time, forensics
            )

    async def _degrade_to_snapshot_or_cache(
        self,
        customer_id: str,
        customer_basic: dict[str, Any],
        curr_ctx: Any,
        prev_ctx: Any,
        orchestrator: Any,
        start_time: float,
        health_status: DataHealthStatus,
        forensics: dict[str, Any]
    ) -> ResilientExecutionResult:
        """Degrades cleanly to Cache if available, or Snapshot if historical windows are starved."""
        # Check Layer 3: Fallback response builder to pull cached database state (highest-fidelity fallback)
        try:
            cached_intel = await self.repo.get_latest_customer_state(customer_id)
            if cached_intel:
                FALLBACK_RESPONSES.labels(fallback_mode="CACHE").inc()
                data = self._build_payload_from_cache(customer_basic, cached_intel)
                
                FailureRegistry.recover("CACHE_FALLBACK_FAILED")
                return ResilientExecutionResult(
                    mode=ResilientOrchestrationMode.DEGRADED,
                    health_status=health_status,
                    data=data,
                    forensics=forensics,
                    metadata={"fallback_source": "materialized_cache", "processing_time_ms": int((time.time() - start_time) * 1000)}
                )
        except Exception as e:
            FailureRegistry.record("CACHE_FALLBACK_FAILED", f"Failed to load cache fallback for customer {customer_id}: {e}", "ERROR", extra={"customer_id": customer_id})

        # Fallback to SNAPSHOT Mode (no cache, but we can return basic customer profile details)
        FALLBACK_RESPONSES.labels(fallback_mode="SNAPSHOT").inc()
        data = self._build_minimal_payload(customer_id, customer_basic, mode="SNAPSHOT")
        
        return ResilientExecutionResult(
            mode=ResilientOrchestrationMode.SNAPSHOT,
            health_status=health_status,
            data=data,
            forensics=forensics,
            metadata={"fallback_source": "minimal_snapshot", "processing_time_ms": int((time.time() - start_time) * 1000)}
        )

    async def _degrade_to_cache_or_minimal(
        self,
        customer_id: str,
        customer_basic: dict[str, Any],
        curr_ctx: Any,
        prev_ctx: Any,
        start_time: float,
        forensics: dict[str, Any]
    ) -> ResilientExecutionResult:
        """Fallback after complete dynamic failure: Cache fallback -> Minimal fallback."""
        try:
            cached_intel = await self.repo.get_latest_customer_state(customer_id)
            if cached_intel:
                FALLBACK_RESPONSES.labels(fallback_mode="CACHE_AFTER_EXCEPTION").inc()
                data = self._build_payload_from_cache(customer_basic, cached_intel)
                
                FailureRegistry.recover("CACHE_FALLBACK_FAILED")
                return ResilientExecutionResult(
                    mode=ResilientOrchestrationMode.DEGRADED,
                    health_status=DataHealthStatus.TRANSIENT_FAILURE,
                    data=data,
                    forensics=forensics,
                    metadata={"fallback_source": "materialized_cache_after_exception", "processing_time_ms": int((time.time() - start_time) * 1000)}
                )
        except Exception as e:
            FailureRegistry.record("CACHE_FALLBACK_FAILED", f"Failed to load cache fallback after exception for customer {customer_id}: {e}", "ERROR", extra={"customer_id": customer_id})

        # Minimal Fallback (Goal 4 & Goal 6)
        FALLBACK_RESPONSES.labels(fallback_mode="MINIMAL_FALLBACK").inc()
        data = self._build_minimal_payload(customer_id, customer_basic, mode="DEGRADED")
        
        return ResilientExecutionResult(
            mode=ResilientOrchestrationMode.DEGRADED,
            health_status=DataHealthStatus.TRANSIENT_FAILURE,
            data=data,
            forensics=forensics,
            metadata={"fallback_source": "minimal_degraded", "processing_time_ms": int((time.time() - start_time) * 1000)}
        )

    # --- LAYER 3: FALLBACK RESPONSE BUILDERS ---

    def _build_payload_from_cache(self, customer_basic: dict[str, Any], cached: Any) -> CustomerProfileResponseData:
        """Reconstructs full schema using cached materialized history (Highest-fidelity fallback)."""
        h_score = cached.health_score or 0.0
        h_prev = cached.health_previous or 0.0
        r_score = cached.risk_score or 0.0
        r_prev = cached.risk_previous or 0.0
        g_score = cached.growth_score or 0.0
        g_prev = cached.growth_previous or 0.0
        t_score = cached.trust_score or 0.0
        t_prev = cached.trust_previous or 0.0
        o_score = cached.opportunity_score or 0.0
        o_prev = cached.opportunity_previous or 0.0
        c_score = cached.credit_score or 0.0
        c_prev = cached.credit_previous or 0.0
        col_score = cached.collection_score or 0.0
        col_prev = cached.collection_previous or 0.0
        rel_score = cached.relationship_score or 0.0
        rel_prev = cached.relationship_previous or 0.0
        
        out_val = cached.outstanding_current or 0.0
        out_prev_val = cached.outstanding_previous or 0.0
        contrib_val = cached.contribution_current or 0.0
        contrib_prev_val = cached.contribution_previous or 0.0

        return CustomerProfileResponseData(
            customer=CustomerDetailSchema(
                customer_id=cached.customer_id,
                customer_name=customer_basic["customer_name"],
                city=customer_basic["city_name"],
                scores=CustomerScoreSchema(
                    health_score=h_score,
                    risk_score=r_score,
                    growth_score=g_score,
                    trust_score=t_score,
                    opportunity_score=o_score,
                    credit_score=c_score,
                    collection_score=col_score,
                    relationship_score=rel_score,
                    outstanding_current=out_val,
                    outstanding_previous=out_prev_val,
                ),
                deltas=CustomerDeltaSchema(
                    health_score=round(h_score - h_prev, 4),
                    risk_score=round(r_score - r_prev, 4),
                    growth_score=round(g_score - g_prev, 4),
                    trust_score=round(t_score - t_prev, 4),
                    opportunity_score=round(o_score - o_prev, 4),
                    credit_score=round(c_score - c_prev, 4),
                    collection_score=round(col_score - col_prev, 4),
                    relationship_score=round(rel_score - rel_prev, 4),
                    outstanding_delta=round(out_val - out_prev_val, 4),
                ),
                behavior_state=cached.state or "UNKNOWN",
                organization_contribution=OrgContributionSchema(
                    current_percentage=round(contrib_val, 2),
                    delta=round(contrib_val - contrib_prev_val, 4)
                ),
                last_purchased_at=cached.last_purchase_date.strftime("%Y-%m-%d") if cached.last_purchase_date else None,
                updated_at=cached.last_updated.isoformat() if cached.last_updated else None
            )
        )

    def _build_minimal_payload(self, customer_id: str, customer_basic: dict[str, Any], mode: str) -> CustomerProfileResponseData:
        """Returns baseline user details with safely initialized values instead of crashing."""
        return CustomerProfileResponseData(
            customer=CustomerDetailSchema(
                customer_id=customer_id,
                customer_name=customer_basic["customer_name"],
                city=customer_basic["city_name"],
                scores=CustomerScoreSchema(
                    health_score=0.0,
                    risk_score=0.0,
                    growth_score=0.0,
                    trust_score=0.0,
                    opportunity_score=0.0,
                    credit_score=0.0,
                    collection_score=0.0,
                    relationship_score=0.0,
                    outstanding_current=0.0,
                    outstanding_previous=0.0
                ),
                deltas=CustomerDeltaSchema(
                    health_score=0.0,
                    risk_score=0.0,
                    growth_score=0.0,
                    trust_score=0.0,
                    opportunity_score=0.0,
                    credit_score=0.0,
                    collection_score=0.0,
                    relationship_score=0.0,
                    outstanding_delta=0.0
                ),
                behavior_state=mode,
                organization_contribution=OrgContributionSchema(
                    current_percentage=0.0,
                    delta=0.0
                ),
                last_purchased_at=None,
                updated_at=datetime.now(UTC).isoformat()
            )
        )

    def _build_full_response(
        self, 
        customer_id: str, 
        customer_basic: dict[str, Any], 
        curr_df: pl.DataFrame, 
        prev_df: pl.DataFrame,
        curr_ctx: Any,
        prev_ctx: Any,
        start_time: float
    ) -> ResilientExecutionResult:
        """Constructs response payload from healthy dataframes."""
        curr_row = curr_df.row(0, named=True)
        prev_row = prev_df.row(0, named=True) if not prev_df.is_empty() else {}

        scores_dict = {
            "health_score": curr_row.get("health_score") or 0.0,
            "risk_score": curr_row.get("risk_score") or 0.0,
            "growth_score": curr_row.get("growth_score") or 0.0,
            "trust_score": curr_row.get("trust_score") or 0.0,
            "opportunity_score": curr_row.get("opportunity_score") or 0.0,
            "credit_score": curr_row.get("credit_score") or 0.0,
            "collection_score": curr_row.get("collection_score") or 0.0,
            "relationship_score": curr_row.get("relationship_score") or 0.0,
            "outstanding_current": curr_row.get("outstanding_balance") or 0.0,
            "outstanding_previous": prev_row.get("outstanding_balance") or 0.0,
        }

        deltas_dict = {
            "health_score": round(scores_dict["health_score"] - (prev_row.get("health_score") or 0.0), 4),
            "risk_score": round(scores_dict["risk_score"] - (prev_row.get("risk_score") or 0.0), 4),
            "growth_score": round(scores_dict["growth_score"] - (prev_row.get("growth_score") or 0.0), 4),
            "trust_score": round(scores_dict["trust_score"] - (prev_row.get("trust_score") or 0.0), 4),
            "opportunity_score": round(scores_dict["opportunity_score"] - (prev_row.get("opportunity_score") or 0.0), 4),
            "credit_score": round(scores_dict["credit_score"] - (prev_row.get("credit_score") or 0.0), 4),
            "collection_score": round(scores_dict["collection_score"] - (prev_row.get("collection_score") or 0.0), 4),
            "relationship_score": round(scores_dict["relationship_score"] - (prev_row.get("relationship_score") or 0.0), 4),
            "outstanding_delta": round(scores_dict["outstanding_current"] - scores_dict["outstanding_previous"], 4),
        }

        last_purchased_ts = curr_row.get("last_purchased_at")
        last_purchased_at = last_purchased_ts.strftime("%Y-%m-%d") if last_purchased_ts else None

        # Organization Contribution
        curr_contrib = curr_row.get("contribution_score_current") or 0.0
        prev_contrib = curr_row.get("contribution_score_previous") or 0.0

        data = CustomerProfileResponseData(
            customer=CustomerDetailSchema(
                customer_id=customer_id,
                customer_name=customer_basic["customer_name"],
                city=customer_basic["city_name"],
                scores=CustomerScoreSchema(**scores_dict),
                deltas=CustomerDeltaSchema(**deltas_dict),
                behavior_state=curr_row.get("behavioral_state") or "UNKNOWN",
                organization_contribution=OrgContributionSchema(
                    current_percentage=round(curr_contrib, 2),
                    delta=round(curr_contrib - prev_contrib, 4)
                ),
                last_purchased_at=last_purchased_at,
                updated_at=datetime.now(UTC).isoformat()
            )
        )

        return ResilientExecutionResult(
            mode=ResilientOrchestrationMode.FULL,
            health_status=DataHealthStatus.HEALTHY,
            data=data,
            forensics={},
            metadata={"processing_time_ms": int((time.time() - start_time) * 1000)}
        )

    def _build_partial_response(
        self, 
        customer_id: str, 
        customer_basic: dict[str, Any], 
        curr_df: pl.DataFrame, 
        prev_df: pl.DataFrame,
        curr_ctx: Any,
        prev_ctx: Any,
        start_time: float,
        forensics: dict[str, Any]
    ) -> ResilientExecutionResult:
        """Constructs response payload when previous comparison window delta calculations fail."""
        curr_row = curr_df.row(0, named=True)
        
        scores_dict = {
            "health_score": curr_row.get("health_score") or 0.0,
            "risk_score": curr_row.get("risk_score") or 0.0,
            "growth_score": curr_row.get("growth_score") or 0.0,
            "trust_score": curr_row.get("trust_score") or 0.0,
            "opportunity_score": curr_row.get("opportunity_score") or 0.0,
            "credit_score": curr_row.get("credit_score") or 0.0,
            "collection_score": curr_row.get("collection_score") or 0.0,
            "relationship_score": curr_row.get("relationship_score") or 0.0,
            "outstanding_current": curr_row.get("outstanding_balance") or 0.0,
            "outstanding_previous": 0.0,
        }

        deltas_dict = {
            "health_score": 0.0,
            "risk_score": 0.0,
            "growth_score": 0.0,
            "trust_score": 0.0,
            "opportunity_score": 0.0,
            "credit_score": 0.0,
            "collection_score": 0.0,
            "relationship_score": 0.0,
            "outstanding_delta": 0.0,
        }

        last_purchased_ts = curr_row.get("last_purchased_at")
        last_purchased_at = last_purchased_ts.strftime("%Y-%m-%d") if last_purchased_ts else None
        curr_contrib = curr_row.get("contribution_score_current") or 0.0

        data = CustomerProfileResponseData(
            customer=CustomerDetailSchema(
                customer_id=customer_id,
                customer_name=customer_basic["customer_name"],
                city=customer_basic["city_name"],
                scores=CustomerScoreSchema(**scores_dict),
                deltas=CustomerDeltaSchema(**deltas_dict),
                behavior_state=curr_row.get("behavioral_state") or "UNKNOWN",
                organization_contribution=OrgContributionSchema(
                    current_percentage=round(curr_contrib, 2),
                    delta=0.0
                ),
                last_purchased_at=last_purchased_at,
                updated_at=datetime.now(UTC).isoformat()
            )
        )

        return ResilientExecutionResult(
            mode=ResilientOrchestrationMode.PARTIAL,
            health_status=DataHealthStatus.PARTIAL,
            data=data,
            forensics=forensics,
            metadata={"fallback_source": "partial_previous_degraded", "processing_time_ms": int((time.time() - start_time) * 1000)}
        )
