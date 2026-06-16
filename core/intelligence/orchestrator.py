from datetime import UTC, datetime, timedelta

import polars as pl
from loguru import logger
from sqlalchemy import select
from core.observability.failure_registry import FailureRegistry

from core.feature_store.engineer import FeatureEngineer
from core.intelligence.cadence.engine import CadenceEngine
from core.intelligence.confidence.engine import ConfidenceEngine

# V2 Dimension Engines
from core.intelligence.dimensions.activity import ActivityDimensionEngine
from core.intelligence.dimensions.credit import CreditDimensionEngine
from core.intelligence.dimensions.discipline import DisciplineDimensionEngine
from core.intelligence.dimensions.friction import FrictionDimensionEngine
from core.intelligence.dimensions.growth import GrowthDimensionEngine
from core.intelligence.dimensions.product import ProductDimensionEngine
from core.intelligence.dimensions.relationship import RelationshipDimensionEngine
from core.intelligence.dimensions.stability import StabilityDimensionEngine
from core.intelligence.exposure.pressure import ExposurePressureEngine
from core.intelligence.ledger.reconstruction import LedgerReconstructionEngine
from core.intelligence.meta.scores import MetaScoreEngine
from core.intelligence.payment.rhythm import PaymentRhythmEngine
from core.intelligence.settlement.engine import SettlementMatchingEngine
from core.intelligence.states.engine import StateEngine
from core.intelligence.trade.consistency import TradeConsistencyEngine
from core.intelligence.validator import IntelligenceIntegrityValidator
from core.ledger.context import LedgerContextService
from core.repositories.intelligence import IntelligenceRepository
from core.schemas.intelligence import AnalysisContext
from core.storage.postgres import AsyncSessionLocal


class IntelligenceOrchestrator:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.cadence_engine = CadenceEngine()

        self.ledger_reconstruction = LedgerReconstructionEngine()
        self.settlement_engine = SettlementMatchingEngine()
        self.payment_rhythm = PaymentRhythmEngine()
        self.exposure_pressure = ExposurePressureEngine()
        self.trade_consistency = TradeConsistencyEngine()

        self.confidence_engine = ConfidenceEngine()
        self.ledger_context = LedgerContextService()
        self.validator = IntelligenceIntegrityValidator()

        # V2 Dimensions
        self.dim_activity = ActivityDimensionEngine()
        self.dim_discipline = DisciplineDimensionEngine()
        self.dim_credit = CreditDimensionEngine()
        self.dim_relationship = RelationshipDimensionEngine()
        self.dim_product = ProductDimensionEngine()
        self.dim_friction = FrictionDimensionEngine()
        self.dim_growth = GrowthDimensionEngine()
        self.dim_stability = StabilityDimensionEngine()
        
        self.meta_scores = MetaScoreEngine()
        self.state_engine = StateEngine()
        
        pass

    def compute_intelligence(
        self, runtime_df: pl.DataFrame, context: AnalysisContext, org_metrics: dict | None = None, customer_avg_billing: dict | None = None
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Core intelligence computation shared by batch and dynamic execution."""
        runtime_df = runtime_df.sort(["customer_id", "event_date"])

        if context.end_date:
            runtime_df = runtime_df.filter(pl.col("event_date").dt.date() <= context.end_date)

        # 2. Component Computation
        runtime_df_fin = runtime_df.filter(pl.col("is_ok") == 0)
        exposure_df_fin = self.ledger_reconstruction.reconstruct_exposure(runtime_df_fin, context)

        features_df = self.feature_engineer.compute_features(runtime_df, context)
        cadence_df = self.cadence_engine.compute(runtime_df, context)
        exposure_df_all = self.ledger_reconstruction.reconstruct_exposure(runtime_df, context)
        settlement_df_all = self.settlement_engine.compute_settlements(runtime_df, context)
        rhythm_df_all = self.payment_rhythm.compute_rhythm(runtime_df, context)
        pressure_df_all = self.exposure_pressure.compute_pressure(exposure_df_all, features_df, context)
        consistency_df = self.trade_consistency.compute_consistency(runtime_df, cadence_df, context, org_metrics=org_metrics)

        conf_df = self.confidence_engine.compute(features_df, context, org_metrics=org_metrics)

        # Inject date column into settlement and pressure dataframes for dimensional engine compatibility
        if not features_df.is_empty():
            latest_dates = features_df.select(["customer_id", "date"])
            if not settlement_df_all.is_empty() and "date" not in settlement_df_all.columns:
                settlement_df_all = settlement_df_all.join(latest_dates, on="customer_id", how="left")
            if not pressure_df_all.is_empty() and "date" not in pressure_df_all.columns:
                pressure_df_all = pressure_df_all.join(latest_dates, on="customer_id", how="left")

        # 3. V2 Dimensions
        dim_activity_df = self.dim_activity.compute(features_df, org_metrics=org_metrics)
        dim_discipline_df = self.dim_discipline.compute(settlement_df_all, rhythm_df_all, org_metrics=org_metrics)
        dim_credit_df = self.dim_credit.compute(pressure_df_all, org_metrics=org_metrics)
        dim_relationship_df = self.dim_relationship.compute(features_df, consistency_df, org_metrics=org_metrics)
        dim_product_df = self.dim_product.compute(features_df, org_metrics=org_metrics)
        dim_friction_df = self.dim_friction.compute(features_df, org_metrics=org_metrics)
        dim_growth_df = self.dim_growth.compute(features_df, org_metrics=org_metrics)
        dim_stability_df = self.dim_stability.compute(features_df, consistency_df, org_metrics=org_metrics)

        # Base frame
        dimensions_df = features_df.select(["customer_id", "date"])

        # Join all dimensions
        for dim_df in [
            dim_activity_df, dim_discipline_df, dim_credit_df, 
            dim_relationship_df, dim_product_df, dim_friction_df, 
            dim_growth_df, dim_stability_df
        ]:
            if not dim_df.is_empty():
                dimensions_df = dimensions_df.join(dim_df, on=["customer_id", "date"], how="left")

        # Ensure all 8 dimensions exist in dimensions_df to prevent Downstream ColumnNotFound errors
        for col in [
            "dim_activity", "dim_discipline", "dim_credit", 
            "dim_relationship", "dim_product", "dim_friction", 
            "dim_growth", "dim_stability"
        ]:
            if col not in dimensions_df.columns:
                dimensions_df = dimensions_df.with_columns(pl.lit(0.0).alias(col))

        # 4. Meta Scores
        meta_scores_df = self.meta_scores.compute(dimensions_df)

        # 5. State Inference
        states_df = self.state_engine.compute(features_df, meta_scores_df, context)

        # 6. Assemble Final Dataframe
        states_df = states_df.join(meta_scores_df, on=["customer_id", "date"], how="left")
        states_df = states_df.join(dimensions_df.drop(["date"]), on=["customer_id"], how="left")

        # Make sure relationship_score and resilience_score are present in states_df
        # relationship_score is already in states_df from meta_scores_df
        if "relationship_score" not in states_df.columns:
            states_df = states_df.with_columns(pl.lit(0.0).alias("relationship_score"))
        else:
            states_df = states_df.with_columns(pl.col("relationship_score").fill_null(0.0))
        
        # resilience_score is deprecated but kept as 0.0 for schema compatibility
        if "resilience_score" not in states_df.columns:
            states_df = states_df.with_columns(pl.lit(0.0).alias("resilience_score"))
        else:
            states_df = states_df.with_columns(pl.col("resilience_score").fill_null(0.0))
        
        # MANDATORY: Join FINANCIAL exposure (is_ok=0) for outstanding balance reporting
        states_df = states_df.sort(["customer_id", "date"]).with_columns(pl.col("date").cast(pl.Date).set_sorted())
        exposure_df_fin = exposure_df_fin.sort(["customer_id", "date"]).with_columns(pl.col("date").cast(pl.Date).set_sorted())
        
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="Sortedness of columns cannot be checked")
            states_df = states_df.join_asof(
                exposure_df_fin,
                on="date",
                by="customer_id",
                strategy="backward"
            )
        
        # Forward fill outstanding balance
        states_df = states_df.with_columns(
            pl.col("outstanding_balance").forward_fill().over("customer_id").fill_null(0.0)
        )

        # Join last_purchased_at from features_df
        states_df = states_df.join(
            features_df.select(["customer_id", "date", "last_purchased_at"]),
            on=["customer_id", "date"],
            how="left"
        )

        # Integrity Validation
        report = self.validator.validate(states_df)
        states_df.validation_report = report

        return states_df, conf_df

    def _generate_behavioral_drivers(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Generates interpretable behavioral drivers for the multidimensional scores.
        """
        # Primary Drivers (Positive)
        df = df.with_columns(
            pl.struct(
                [
                    "dim_activity",
                    "dim_discipline",
                    "trust_score",
                    "dim_credit",
                    "dim_friction",
                    "dim_stability",
                ]
            )
            .map_elements(
                lambda x: [
                    d
                    for d, v in [
                        (
                            "HIGH_TRADE_REGULARITY",
                            x["dim_activity"] is not None and x["dim_activity"] > 0.8,
                        ),
                        ("FAST_SETTLEMENT", x["dim_discipline"] is not None and x["dim_discipline"] > 0.8),
                        (
                            "ELITE_LIQUIDITY",
                            x["trust_score"] is not None and x["trust_score"] > 0.85,
                        ),
                        (
                            "STRONG_DEBT_CLEARANCE",
                            x["dim_credit"] is not None and x["dim_credit"] > 0.8,
                        ),
                        ("LOW_CUSTOMER_RG", x["dim_friction"] is not None and x["dim_friction"] > 0.9),
                        (
                            "STABLE_PARTICIPATION",
                            x["dim_stability"] is not None and x["dim_stability"] > 0.7,
                        ),
                    ]
                    if v
                ],
                return_dtype=pl.List(pl.Utf8),
            )
            .alias("primary_drivers")
        )

        # Negative Drivers
        df = df.with_columns(
            pl.struct(
                [
                    "dim_activity",
                    "dim_discipline",
                    "risk_score",
                    "dim_credit",
                    "dim_friction",
                ]
            )
            .map_elements(
                lambda x: [
                    d
                    for d, v in [
                        ("SLOW_SETTLEMENT", x["dim_discipline"] is not None and x["dim_discipline"] < 0.4),
                        ("HIGH_OPERATIONAL_FRICTION", x["dim_friction"] is not None and x["dim_friction"] < 0.6),
                        (
                            "LIQUIDITY_STRESS",
                            x["risk_score"] is not None and x["risk_score"] < 0.4,
                        ),
                        (
                            "CHRONIC_DEBT_PRESSURE",
                            x["dim_credit"] is not None and x["dim_credit"] < 0.3,
                        ),
                        (
                            "WEAK_CLEARANCE_STRENGTH",
                            x["dim_credit"] is not None and x["dim_credit"] < 0.4,
                        ),
                        (
                            "INCONSISTENT_TRADING",
                            x["dim_activity"] is not None and x["dim_activity"] < 0.3,
                        ),
                        ("CRITICAL_BEHAVIORAL_STRESS", x["risk_score"] is not None and x["risk_score"] < 0.3),
                    ]
                    if v
                ],
                return_dtype=pl.List(pl.Utf8),
            )
            .alias("negative_drivers")
        )

        return df

    async def run(self, customer_ids: list[str], batch_id: str | None = None) -> None:
        """
        Autonomous recomputation loop for a set of customers.
        Computes Current (365d) and Previous (730d-365d) windows and persists to cache.
        """
        start_time = datetime.now(UTC)
        failures_count = 0
        warnings_count = 0
        alerts_count = 0
        commitments_count = 0
        broken_commitments_count = 0

        async with AsyncSessionLocal() as session:
            # 1. Load FULL history for all affected customers
            runtime_df = await self.ledger_context.load_customer_history(session, customer_ids)
            if runtime_df.is_empty():
                return

            repo = IntelligenceRepository(session)
            
            # Anchor to latest event date for these customers to avoid artificial dormancy/timezone mismatches
            try:
                from sqlalchemy import text
                max_event_res = await session.execute(
                    text("SELECT MAX(event_date) FROM event_ledger WHERE customer_id = ANY(:cids)"),
                    {"cids": customer_ids}
                )
                max_event_date = max_event_res.scalar()
                if max_event_date:
                    now = datetime.combine(max_event_date, datetime.min.time())
                else:
                    global_res = await session.execute(text("SELECT MAX(event_date) FROM event_ledger"))
                    global_date = global_res.scalar()
                    if global_date:
                        now = datetime.combine(global_date, datetime.min.time())
                    else:
                        now = datetime.now(UTC)
            except Exception:
                now = datetime.now(UTC)
            current_end = now.replace(minute=0, second=0, microsecond=0)

            current_start = current_end - timedelta(days=365)
            prev_end = current_start - timedelta(microseconds=1)
            prev_start = current_start - timedelta(days=365)

            # 3. PRE-FETCH BULK DATA
            curr_org_metrics = await repo.get_org_distribution_metrics(current_start, current_end)
            prev_org_metrics = await repo.get_org_distribution_metrics(prev_start, prev_end)
            
            curr_avg_billing = await repo.get_bulk_avg_monthly_billing(current_start, current_end, customer_ids)
            prev_avg_billing = await repo.get_bulk_avg_monthly_billing(prev_start, prev_end, customer_ids)

            curr_org_sales = await repo.get_total_sales_in_window(current_start, current_end)
            prev_org_sales = await repo.get_total_sales_in_window(prev_start, prev_end)

            curr_bulk_sales = await repo.get_bulk_total_sales_in_window(current_start, current_end, customer_ids)
            prev_bulk_sales = await repo.get_bulk_total_sales_in_window(prev_start, prev_end, customer_ids)

            # Bulk customer details
            customer_details_map = {}
            try:
                import uuid

                from core.storage.postgres import get_reflected_table
                customers_tbl = await get_reflected_table("customers", session)
                
                if customers_tbl is not None:
                    # Convert customer_ids to UUID objects for querying
                    uuid_cids = []
                    for cid in customer_ids:
                        try:
                            uuid_cids.append(uuid.UUID(cid))
                        except ValueError:
                            pass
                    
                    if uuid_cids:
                        stmt = select(
                            customers_tbl.c.id,
                            customers_tbl.c.business_name,
                            customers_tbl.c.city,
                            customers_tbl.c.business_type,
                            customers_tbl.c.credit_limit,
                            customers_tbl.c.behavioral_profile
                        ).where(
                            customers_tbl.c.id.in_(uuid_cids)
                        )
                        
                        res = await session.execute(stmt)
                        for row in res.all():
                            customer_details_map[str(row.id)] = {
                                "business_name": row.business_name,
                                "city": row.city,
                                "business_type": row.business_type,
                                "credit_limit": float(row.credit_limit) if row.credit_limit is not None else 0.0,
                                "behavioral_profile": row.behavioral_profile or {}
                            }
            except Exception as e:
                FailureRegistry.record("CUSTOMER_DETAILS_LOAD_FAILED", f"Could not load customer details in bulk: {e}", "WARNING", extra={"error": str(e)})

            # 4. Process each customer
            import uuid as uuid_pkg

            from core.models.state_models import EventLedger

            for cid in customer_ids:
                try:
                    async with session.begin_nested():
                        cust_df = runtime_df.filter(pl.col("customer_id") == cid)
                        cust_details = customer_details_map.get(cid, {})
                        customer_name = cust_details.get("business_name")
                        city_name = cust_details.get("city")
                        business_type = cust_details.get("business_type")
                        credit_limit = cust_details.get("credit_limit", 0.0)
                        behavioral_profile = cust_details.get("behavioral_profile") or {}

                        # Derive archetype
                        if business_type in ("manufacturer", "distributor") or (business_type == "wholesaler" and credit_limit > 500000.0):
                            archetype_val = "whale"
                        else:
                            params = behavioral_profile.get("params", {})
                            gp = params.get("growth_potential", 5)
                            cp = params.get("churn_probability", 0.5)
                            liq = params.get("liquidity", 5)
                            if gp >= 15:
                                archetype_val = "growing_retailer"
                            elif cp >= 0.7:
                                archetype_val = "declining_retailer"
                            elif liq <= 3:
                                archetype_val = "liquidity_stressed"
                            else:
                                archetype_val = "stable_retailer"
                        
                        if cust_df.is_empty():
                            # Handle Zero-History Customer (inactive initialization)
                            intel_data = {
                                "customer_id": cid,
                                "customer_name": customer_name,
                                "city": city_name,
                                "health_score": 0.0,
                                "risk_score": 0.0,
                                "growth_score": 0.0,
                                "trust_score": 0.0,
                                "opportunity_score": 0.0,
                                "credit_score": 0.0,
                                "collection_score": 0.0,
                                "relationship_score": 0.0,
                                "contribution_current": 0.0,
                                "outstanding_current": 0.0,
                                "state": "dormant",
                                "current_state": "dormant",
                                "customer_archetype": archetype_val,
                                "risk_direction": "stable",
                                "trust_direction": "stable",
                                "health_previous": 0.0,
                                "risk_previous": 0.0,
                                "growth_previous": 0.0,
                                "trust_previous": 0.0,
                                "opportunity_previous": 0.0,
                                "credit_previous": 0.0,
                                "collection_previous": 0.0,
                                "relationship_previous": 0.0,
                                "contribution_previous": 0.0,
                                "outstanding_previous": 0.0,
                                "last_purchase_date": None,
                                "v2_scores": {
                                    "growth_score": 0.0,
                                    "risk_score": 0.0,
                                    "relationship_score": 0.0,
                                    "resilience_score": 0.0,
                                    "opportunity_score": 0.0,
                                }
                            }
                            await repo.persist_intelligence(intel_data)
                            continue

                        # Current Window Analysis (last 365d)
                        current_ctx = AnalysisContext(window_days=365, end_date=current_end.date())
                        curr_states, curr_conf = self.compute_intelligence(cust_df, current_ctx, org_metrics=curr_org_metrics, customer_avg_billing=curr_avg_billing)
                        curr_row = curr_states.sort("date").row(-1, named=True) if not curr_states.is_empty() else {}

                        # Extract absolute outstanding at current_end
                        curr_outstanding = curr_row.get("outstanding_balance", 0.0) if curr_row else 0.0

                        # Previous Window Analysis (730d -> 365d)
                        prev_ctx = AnalysisContext(window_days=365, end_date=prev_end.date())
                        prev_states, prev_conf = self.compute_intelligence(cust_df, prev_ctx, org_metrics=prev_org_metrics, customer_avg_billing=prev_avg_billing)
                        prev_row = prev_states.sort("date").row(-1, named=True) if not prev_states.is_empty() else {}

                        # Extract absolute outstanding at prev_end
                        prev_outstanding = prev_row.get("outstanding_balance", 0.0) if prev_row else 0.0

                        # Use Pre-fetched data for contribution
                        curr_cust_sales = curr_bulk_sales.get(cid, 0.0)
                        prev_cust_sales = prev_bulk_sales.get(cid, 0.0)

                        curr_contrib = (curr_cust_sales / curr_org_sales * 100) if curr_org_sales > 0 else 0.0
                        prev_contrib = (prev_cust_sales / prev_org_sales * 100) if prev_org_sales > 0 else 0.0

                        # Extract last purchase date
                        last_purchase_date = None
                        if curr_row.get("last_purchased_at"):
                            last_purchase_date = curr_row.get("last_purchased_at")
                            if isinstance(last_purchase_date, datetime):
                                last_purchase_date = last_purchase_date.date()

                        # Derive directions
                        curr_trust = curr_row.get("trust_score") or 0.0
                        prev_trust = prev_row.get("trust_score") or 0.0
                        curr_risk = curr_row.get("risk_score") or 0.0
                        prev_risk = prev_row.get("risk_score") or 0.0
                        curr_health = curr_row.get("health_score") or 0.0
                        prev_health = prev_row.get("health_score") or 0.0
                        curr_coll = curr_row.get("collection_score") or 0.0
                        prev_coll = prev_row.get("collection_score") or 0.0
                        
                        dim_credit = curr_row.get("dim_credit") or 0.5
                        dim_discipline = curr_row.get("dim_discipline") or 0.5
                        behavioral_state = curr_row.get("behavioral_state")
                        trajectory = curr_row.get("trajectory")

                        if curr_trust > prev_trust + 0.05:
                            trust_dir = "increasing"
                        elif curr_trust < prev_trust - 0.05:
                            trust_dir = "decreasing"
                        else:
                            trust_dir = "stable"

                        if curr_risk > prev_risk + 0.05:
                            risk_dir = "increasing"
                        elif curr_risk < prev_risk - 0.05:
                            risk_dir = "decreasing"
                        else:
                            risk_dir = "stable"

                        # Trust score refinement (directional influence)
                        trust_score = curr_trust
                        if trust_dir == "decreasing":
                            trust_score = max(0.0, curr_trust - 0.05)
                        elif trust_dir == "increasing":
                            trust_score = min(1.0, curr_trust + 0.05)

                        # State Inference
                        if behavioral_state == "inactive":
                            state_val = "dormant"
                        elif curr_risk >= 0.70 or dim_discipline < 0.25:
                            state_val = "distressed"
                        elif curr_risk >= 0.50 or dim_discipline < 0.45:
                            state_val = "stressed"
                        elif dim_credit < 0.35:
                            state_val = "overleveraged"
                        elif trajectory in ("COLLAPSING", "DECLINING") or behavioral_state == "declining":
                            state_val = "declining"
                        elif curr_risk < prev_risk - 0.05 and dim_discipline >= 0.5:
                            state_val = "recovering"
                        elif trajectory == "ACCELERATING":
                            state_val = "expanding"
                        elif trajectory == "GROWING":
                            state_val = "growing"
                        else:
                            state_val = "healthy"

                        # Fetch existing state for transition timeline triggers
                        existing_intel = await repo.get_latest_customer_state(cid)
                        prev_state_name = existing_intel.state if existing_intel else None
                        prev_trust_val = existing_intel.trust_score if existing_intel else None

                        event_date_to_use = current_end.date()
                        
                        # Helper to check if event already exists
                        async def event_exists(evt_type: str) -> bool:
                            check_stmt = select(EventLedger.event_id).where(
                                EventLedger.customer_id == cid,
                                EventLedger.event_type == evt_type,
                                EventLedger.event_date == event_date_to_use
                            ).limit(1)
                            check_res = await session.execute(check_stmt)
                            return check_res.scalar() is not None

                        events_to_add = []
                        if prev_state_name and prev_state_name != state_val:
                            # State change event
                            if state_val in ("stressed", "distressed") and prev_state_name not in ("stressed", "distressed"):
                                if not await event_exists("financial_stress_detected"):
                                    events_to_add.append(EventLedger(
                                        event_id=f"EVT_STRESS_{cid}_{event_date_to_use.isoformat()}_{str(uuid_pkg.uuid4())[:8]}",
                                        customer_id=cid,
                                        event_type="financial_stress_detected",
                                        event_date=event_date_to_use,
                                        amount=0.0,
                                        is_ok=1,
                                        metadata_={"description": f"Customer entered {state_val.capitalize()} State", "from_state": prev_state_name, "to_state": state_val}
                                    ))
                            elif state_val in ("declining", "dormant") and prev_state_name not in ("declining", "dormant"):
                                if not await event_exists("churn_risk_detected"):
                                    events_to_add.append(EventLedger(
                                        event_id=f"EVT_CHURN_{cid}_{event_date_to_use.isoformat()}_{str(uuid_pkg.uuid4())[:8]}",
                                        customer_id=cid,
                                        event_type="churn_risk_detected",
                                        event_date=event_date_to_use,
                                        amount=0.0,
                                        is_ok=1,
                                        metadata_={"description": "Churn Risk Detected: purchase intervals or active states declining", "from_state": prev_state_name, "to_state": state_val}
                                    ))
                            elif state_val in ("healthy", "recovering", "growing", "expanding") and prev_state_name in ("stressed", "distressed", "declining"):
                                if not await event_exists("risk_recovery"):
                                    events_to_add.append(EventLedger(
                                        event_id=f"EVT_RECOVERY_{cid}_{event_date_to_use.isoformat()}_{str(uuid_pkg.uuid4())[:8]}",
                                        customer_id=cid,
                                        event_type="risk_recovery",
                                        event_date=event_date_to_use,
                                        amount=0.0,
                                        is_ok=1,
                                        metadata_={"description": f"Recovery Detected: customer transitioned to {state_val.capitalize()} state", "from_state": prev_state_name, "to_state": state_val}
                                    ))

                        if prev_trust_val and abs(trust_score - prev_trust_val) >= 0.10:
                            evt_type = "purchase_pacing_shifted" if trust_score < prev_trust_val else "trust_improved"
                            if not await event_exists(evt_type):
                                events_to_add.append(EventLedger(
                                    event_id=f"EVT_TRUST_{cid}_{evt_type}_{event_date_to_use.isoformat()}_{str(uuid_pkg.uuid4())[:8]}",
                                    customer_id=cid,
                                    event_type=evt_type,
                                    event_date=event_date_to_use,
                                    amount=0.0,
                                    is_ok=1,
                                    metadata_={"description": f"Trust Score changed by {int((trust_score - prev_trust_val)*100)}%", "old_value": prev_trust_val, "new_value": trust_score}
                                ))

                        if prev_coll and curr_coll < prev_coll - 0.10:
                            if not await event_exists("stress_delay_accumulated"):
                                events_to_add.append(EventLedger(
                                    event_id=f"EVT_DELAY_{cid}_{event_date_to_use.isoformat()}_{str(uuid_pkg.uuid4())[:8]}",
                                    customer_id=cid,
                                    event_type="stress_delay_accumulated",
                                    event_date=event_date_to_use,
                                    amount=0.0,
                                    is_ok=1,
                                    metadata_={"description": f"Payment Delay worsened: collection score dropped by {int((prev_coll - curr_coll)*100)}%", "old_value": prev_coll, "new_value": curr_coll}
                                ))

                        for evt in events_to_add:
                            session.add(evt)

                        # 5. Populate Consolidated Intelligence Data (Cache)
                        intel_data = {
                            "customer_id": cid,
                            "customer_name": customer_name,
                            "city": city_name,
                            "health_score": curr_health,
                            "risk_score": curr_risk,
                            "growth_score": curr_row.get("growth_score"),
                            "trust_score": trust_score,
                            "opportunity_score": curr_row.get("opportunity_score"),
                            "credit_score": curr_row.get("credit_score"),
                            "collection_score": curr_coll,
                            "relationship_score": curr_row.get("relationship_score"),
                            "contribution_current": curr_contrib,
                            "outstanding_current": curr_outstanding,
                            "state": state_val,
                            "current_state": state_val,
                            "customer_archetype": archetype_val,
                            "risk_direction": risk_dir,
                            "trust_direction": trust_dir,
                            "health_previous": prev_health,
                            "risk_previous": prev_risk,
                            "growth_previous": prev_row.get("growth_score"),
                            "trust_previous": prev_trust,
                            "opportunity_previous": prev_row.get("opportunity_score"),
                            "credit_previous": prev_row.get("credit_score"),
                            "collection_previous": prev_coll,
                            "relationship_previous": prev_row.get("relationship_score"),
                            "contribution_previous": prev_contrib,
                            "outstanding_previous": prev_outstanding,
                            "last_purchase_date": last_purchase_date,
                            "v2_scores": {
                                "health_score": curr_health,
                                "risk_score": curr_risk,
                                "growth_score": curr_row.get("growth_score", 0.0),
                                "trust_score": trust_score,
                                "opportunity_score": curr_row.get("opportunity_score", 0.0),
                                "credit_score": curr_row.get("credit_score", 0.0),
                                "collection_score": curr_coll,
                                "relationship_score": curr_row.get("relationship_score", 0.0),
                                "dimensions": {
                                    "activity": curr_row.get("dim_activity", 0.0),
                                    "discipline": curr_row.get("dim_discipline", 0.0),
                                    "credit": curr_row.get("dim_credit", 0.0),
                                    "relationship": curr_row.get("dim_relationship", 0.0),
                                    "product": curr_row.get("dim_product", 0.0),
                                    "friction": curr_row.get("dim_friction", 0.0),
                                    "growth": curr_row.get("dim_growth", 0.0),
                                    "stability": curr_row.get("dim_stability", 0.0),
                                }
                            }
                        }

                        await repo.persist_intelligence(intel_data)

                        # Trigger persistent alerts & recommendations generation
                        try:
                            from core.services.alert_service import AlertService
                            generated_alerts = await AlertService().scan_and_generate_alerts(cid, session)
                            alerts_count += len(generated_alerts)
                        except Exception as e_alert:
                            warnings_count += 1

                        try:
                            from core.recommendation.service import RecommendationService
                            await RecommendationService().generate_recommendations(session, cid)
                        except Exception as e_rec:
                            warnings_count += 1

                        try:
                            from core.services.collections_service import CollectionsService
                            eval_commitments, broken_commitments = await CollectionsService().evaluate_commitments(cid, session)
                            commitments_count += eval_commitments
                            broken_commitments_count += broken_commitments
                        except Exception as e_comm:
                            warnings_count += 1

                except Exception as e:
                    failures_count += 1
                    continue

            await session.commit()
            duration = (datetime.now(UTC) - start_time).total_seconds()
            
            # Query the count of activities logged for these customers during the batch timeframe
            from sqlalchemy import func
            from core.models.state_models import CollectionActivity
            activities_stmt = select(func.count(CollectionActivity.id)).where(
                CollectionActivity.customer_id.in_(customer_ids),
                CollectionActivity.created_at >= start_time - timedelta(minutes=5)
            )
            activities_res = await session.execute(activities_stmt)
            activities_count = activities_res.scalar() or 0

            logger.info(
                "recompute_completed",
                extra={
                    "duration_sec": duration,
                    "customers": len(customer_ids),
                    "alerts": alerts_count
                }
            )
            logger.info(
                "collection_cycle_completed",
                extra={
                    "activities": activities_count,
                    "commitments": commitments_count,
                    "broken_commitments": broken_commitments_count
                }
            )

    async def run_dynamic(self, customer_ids: list[str], context: AnalysisContext) -> pl.DataFrame:
        """
        Dynamically computes intelligence for the requested customers and context.
        Does NOT persist to database.
        """

        async with AsyncSessionLocal() as session:
            repo = IntelligenceRepository(session)
            
            # Anchor on latest data if no end_date provided in context
            if not context.end_date:
                latest_data_date = await repo.get_latest_ledger_date()
                if latest_data_date:
                    context.end_date = latest_data_date
                    # Re-calculate windows if they were based on system clock
                    # Note: AnalysisContext start_date might need sync if it was provided
            
            runtime_df = await self.ledger_context.load_customer_history(session, customer_ids)
            if runtime_df.is_empty():
                return pl.DataFrame()

            # Resolve Contribution Scores for Dynamic Context
            # Dynamic calculation needs to perform the same O(N) aggregate as batch for org totals
            end_dt = datetime.combine(context.end_date or datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
            start_dt = end_dt - timedelta(days=context.window_days)
            
            # Previous window for delta
            prev_end_dt = start_dt - timedelta(microseconds=1)
            prev_start_dt = prev_end_dt - timedelta(days=context.window_days)

            # Global Org Sales (Cached for this call)
            curr_org_sales = await repo.get_total_sales_in_window(start_dt, end_dt)
            prev_org_sales = await repo.get_total_sales_in_window(prev_start_dt, prev_end_dt)

            # Recalibration Metrics
            org_metrics = await repo.get_org_distribution_metrics(start_dt, end_dt)
            bulk_avg_billing = await repo.get_bulk_avg_monthly_billing(start_dt, end_dt, customer_ids)

        states_df, conf_df = self.compute_intelligence(runtime_df, context, org_metrics=org_metrics, customer_avg_billing=bulk_avg_billing)

        # Only return the final state/row per customer based on the temporal context
        latest_states_df = states_df.sort("date").group_by("customer_id").tail(1)
        latest_conf_df = conf_df.sort("date").group_by("customer_id").tail(1)

        # Join states and confidence
        final_df = latest_states_df.join(latest_conf_df, on=["customer_id", "date"], how="left")
        
        # Inject contribution scores into the result set
        async with AsyncSessionLocal() as session:
            repo = IntelligenceRepository(session)
            contrib_data = []
            for cid in customer_ids:
                curr_cust_sales = await repo.get_total_sales_in_window(start_dt, end_dt, customer_id=cid)
                prev_cust_sales = await repo.get_total_sales_in_window(prev_start_dt, prev_end_dt, customer_id=cid)
                
                curr_contrib = (curr_cust_sales / curr_org_sales * 100) if curr_org_sales > 0 else 0.0
                prev_contrib = (prev_cust_sales / prev_org_sales * 100) if prev_org_sales > 0 else 0.0
                
                contrib_data.append({
                    "customer_id": cid,
                    "contribution_score_current": curr_contrib,
                    "contribution_score_previous": prev_contrib
                })
        
        contrib_df = pl.DataFrame(contrib_data)
        final_df = final_df.join(contrib_df, on="customer_id", how="left")

        return final_df

    async def run_dynamic_timeline(self, customer_id: str, context: AnalysisContext) -> pl.DataFrame:
        """
        Dynamically computes the full intelligence timeline for a single customer.
        Returns the joined states and confidence dataframe for all days in the window.
        """

        async with AsyncSessionLocal() as session:
            repo = IntelligenceRepository(session)
            runtime_df = await self.ledger_context.load_customer_history(session, [customer_id])
            if runtime_df.is_empty():
                return pl.DataFrame()
            
            # Resolve Context for normalization
            end_dt = datetime.combine(context.end_date or datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
            start_dt = end_dt - timedelta(days=context.window_days)
            
            org_metrics = await repo.get_org_distribution_metrics(start_dt, end_dt)
            bulk_avg_billing = await repo.get_bulk_avg_monthly_billing(start_dt, end_dt, [customer_id])

        states_df, conf_df = self.compute_intelligence(runtime_df, context, org_metrics=org_metrics, customer_avg_billing=bulk_avg_billing)

        # Join full timelines
        final_df = states_df.join(conf_df, on=["customer_id", "date"], how="left")
        return final_df
