from datetime import UTC, datetime, timedelta

import polars as pl
from loguru import logger
from sqlalchemy import select

from core.feature_store.engineer import FeatureEngineer
from core.intelligence.cadence.engine import CadenceEngine
from core.intelligence.causal.engine import CausalDiagnosisEngine
from core.intelligence.confidence.engine import ConfidenceEngine
from core.intelligence.exposure.pressure import ExposurePressureEngine
from core.intelligence.ledger.reconstruction import LedgerReconstructionEngine
from core.intelligence.payment.behavior import PaymentBehaviorEngine
from core.intelligence.payment.rhythm import PaymentRhythmEngine
from core.intelligence.rg.engine import RGBehaviorEngine
from core.intelligence.settlement.engine import SettlementMatchingEngine
from core.intelligence.states.engine import StateEngine
from core.intelligence.stress.engine import StressEngine
from core.intelligence.trade.consistency import TradeConsistencyEngine
from core.intelligence.trade.potential import TradePotentialEngine
from core.intelligence.trade.profile import TradeProfileEngine
from core.intelligence.trade.purchase import PurchaseBehaviorEngine
from core.intelligence.transitions.engine import TransitionEngine
from core.intelligence.trust.engine import TrustEngine
from core.intelligence.validator import IntelligenceIntegrityValidator
from core.ledger.context import LedgerContextService
from core.repositories.intelligence import IntelligenceRepository
from core.schemas.intelligence import AnalysisContext
from core.storage.postgres import AsyncSessionLocal


class IntelligenceOrchestrator:
    def __init__(self):
        self.feature_engineer = FeatureEngineer()
        self.cadence_engine = CadenceEngine()
        self.stress_engine = StressEngine()

        # Next-Gen Engines
        self.ledger_reconstruction = LedgerReconstructionEngine()
        self.settlement_engine = SettlementMatchingEngine()
        self.payment_rhythm = PaymentRhythmEngine()
        self.exposure_pressure = ExposurePressureEngine()
        self.trade_consistency = TradeConsistencyEngine()
        self.trade_potential = TradePotentialEngine()
        self.trade_profile = TradeProfileEngine()

        # Multidimensional Behavioral Engines
        self.purchase_behavior = PurchaseBehaviorEngine()
        self.payment_behavior = PaymentBehaviorEngine()
        self.rg_behavior = RGBehaviorEngine()

        self.trust_engine = TrustEngine()
        self.state_engine = StateEngine()
        self.confidence_engine = ConfidenceEngine()
        self.transition_engine = TransitionEngine()
        self.causal_engine = CausalDiagnosisEngine()
        self.ledger_context = LedgerContextService()
        self.validator = IntelligenceIntegrityValidator()

    def compute_intelligence(
        self, runtime_df: pl.DataFrame, context: AnalysisContext, org_metrics: dict | None = None, customer_avg_billing: dict | None = None
    ) -> tuple[pl.DataFrame, pl.DataFrame]:
        """Core intelligence computation shared by batch and dynamic execution."""
        # MANDATORY: Sort chronologically for rolling windows
        runtime_df = runtime_df.sort(["customer_id", "event_date"])

        # Filter out future events beyond end_date if provided
        if context.end_date:
            runtime_df = runtime_df.filter(pl.col("event_date").dt.date() <= context.end_date)

        # 2. Component Computation
        # Outstanding is the ONLY place where is_ok=0 logic is applied
        runtime_df_fin = runtime_df.filter(pl.col("is_ok") == 0)
        exposure_df_fin = self.ledger_reconstruction.reconstruct_exposure(runtime_df_fin, context)

        # All other engines use ALL events (ignoring is_ok)
        features_df = self.feature_engineer.compute_features(runtime_df, context)
        cadence_df = self.cadence_engine.compute(runtime_df, context)
        exposure_df_all = self.ledger_reconstruction.reconstruct_exposure(runtime_df, context)
        settlement_df_all = self.settlement_engine.compute_settlements(runtime_df, context)
        rhythm_df_all = self.payment_rhythm.compute_rhythm(runtime_df, context)
        pressure_df_all = self.exposure_pressure.compute_pressure(exposure_df_all, features_df, context)
        consistency_df = self.trade_consistency.compute_consistency(runtime_df, cadence_df, context)

        conf_df = self.confidence_engine.compute(features_df, context, org_metrics=org_metrics)
        stress_df = self.stress_engine.compute(features_df)

        # 3. Multidimensional Behavioral Scoring (Deterministic Pillars)
        purchase_df = self.purchase_behavior.compute_score(features_df, consistency_df, context, org_metrics=org_metrics)
        payment_df = self.payment_behavior.compute_score(settlement_df_all, rhythm_df_all, pressure_df_all, context, customer_avg_billing=customer_avg_billing)
        rg_df = self.rg_behavior.compute_score(features_df, context)
        
        # Telemetry: Log Confidence Cap Distribution
        if not payment_df.is_empty():
            cap_60 = payment_df.filter(pl.col("evidence_strength") < 0.2).height
            cap_75 = payment_df.filter((pl.col("evidence_strength") >= 0.2) & (pl.col("evidence_strength") < 0.4)).height
            cap_90 = payment_df.filter((pl.col("evidence_strength") >= 0.4) & (pl.col("evidence_strength") < 0.6)).height
            total = payment_df.height
            logger.debug(f"Confidence Cap Telemetry | Total: {total} | <0.2 (0.60 cap): {cap_60} ({cap_60/total:.1%}) | <0.4 (0.75 cap): {cap_75} ({cap_75/total:.1%}) | <0.6 (0.90 cap): {cap_90} ({cap_90/total:.1%})")

        # Trust Engine (Behavioral Fusion: Purchase 50%, Payment 50%)
        trust_df = self.trust_engine.compute(purchase_df, payment_df)

        # 4. State Inference (Behavioral Context)
        states_df = self.state_engine.compute(
            features_df,
            cadence_df,
            stress_df,
            trust_df,
            settlement_df_all,
            pressure_df_all,
            rhythm_df_all,
            consistency_df,
            conf_df,
            context,
        )

        # Realigned columns selection
        states_df = states_df.select(["customer_id", "date", "behavioral_state", "overall_class"])
        states_df = states_df.join(trust_df.select(["customer_id", "date", "trust_score"]), on=["customer_id", "date"], how="left")
        states_df = states_df.join(purchase_df.select(["customer_id", "date", "purchase_behavior_score"]), on=["customer_id", "date"], how="left")
        
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
        
        # Join payment and rg
        states_df = states_df.join(payment_df.select(["customer_id", "payment_behavior_score"]), on="customer_id", how="left")
        states_df = states_df.join(rg_df.select(["customer_id", "date", "rg_rate_score", "raw_rg_amount"]), on=["customer_id", "date"], how="left")

        # Join last_purchased_at from features_df
        states_df = states_df.join(
            features_df.select(["customer_id", "date", "last_purchased_at"]),
            on=["customer_id", "date"],
            how="left"
        )

        # Fill nulls for safety and rename columns to match the simplified schema
        states_df = states_df.with_columns(
            [
                pl.col("trust_score").fill_null(0.0),
                pl.col("purchase_behavior_score").fill_null(0.0),
                pl.col("payment_behavior_score").fill_null(0.0),
                pl.col("rg_rate_score").fill_null(0.0),
                pl.col("raw_rg_amount").fill_null(0.0),
            ]
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
                    "purchase_behavior_score",
                    "payment_behavior_score",
                    "rg_rate_score",
                    "avg_repayment_days",
                    "trade_regularity_score",
                    "clearance_strength",
                ]
            )
            .map_elements(
                lambda x: [
                    d
                    for d, v in [
                        (
                            "HIGH_TRADE_REGULARITY",
                            x["purchase_behavior_score"] is not None and x["purchase_behavior_score"] > 0.8,
                        ),
                        ("FAST_SETTLEMENT", x["avg_repayment_days"] is not None and x["avg_repayment_days"] <= 60),
                        (
                            "ELITE_LIQUIDITY",
                            x["payment_behavior_score"] is not None and x["payment_behavior_score"] > 0.85,
                        ),
                        (
                            "STRONG_DEBT_CLEARANCE",
                            x["clearance_strength"] is not None and x["clearance_strength"] > 0.8,
                        ),
                        ("LOW_CUSTOMER_RG", x["rg_rate_score"] is not None and x["rg_rate_score"] < 0.1),
                        (
                            "STABLE_PARTICIPATION",
                            x["trade_regularity_score"] is not None and x["trade_regularity_score"] > 0.7,
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
                    "purchase_behavior_score",
                    "payment_behavior_score",
                    "rg_rate_score",
                    "avg_repayment_days",
                    "stress_score",
                    "clearance_strength",
                    "unresolved_exposure_ratio",
                ]
            )
            .map_elements(
                lambda x: [
                    d
                    for d, v in [
                        ("SLOW_SETTLEMENT", x["avg_repayment_days"] is not None and x["avg_repayment_days"] > 90),
                        ("HIGH_OPERATIONAL_FRICTION", x["rg_rate_score"] is not None and x["rg_rate_score"] > 0.4),
                        (
                            "LIQUIDITY_STRESS",
                            x["payment_behavior_score"] is not None and x["payment_behavior_score"] < 0.4,
                        ),
                        (
                            "CHRONIC_DEBT_PRESSURE",
                            x["unresolved_exposure_ratio"] is not None and x["unresolved_exposure_ratio"] > 0.7,
                        ),
                        (
                            "WEAK_CLEARANCE_STRENGTH",
                            x["clearance_strength"] is not None and x["clearance_strength"] < 0.4,
                        ),
                        (
                            "INCONSISTENT_TRADING",
                            x["purchase_behavior_score"] is not None and x["purchase_behavior_score"] < 0.3,
                        ),
                        ("CRITICAL_BEHAVIORAL_STRESS", x["stress_score"] is not None and x["stress_score"] > 0.7),
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
        logger.debug(f"Starting Autonomous Intelligence Recomputation for {len(customer_ids)} customers (Window: 365d)")

        async with AsyncSessionLocal() as session:
            # 1. Load FULL history for all affected customers
            runtime_df = await self.ledger_context.load_customer_history(session, customer_ids)
            if runtime_df.is_empty():
                logger.debug("No historical events found for requested customers.")
                return

            repo = IntelligenceRepository(session)
            
            # 2. Define Windows anchored on CURRENT_DATE
            # MANDATORY: Analysis is always anchored to real CURRENT_DATE.
            # Future-dated events are ignored by ledger_context and IntelligenceRepository.
            now = datetime.now(UTC)
            effective_today = now.date()
            current_end = datetime.combine(effective_today, now.time(), tzinfo=UTC)

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

            # Bulk customer basic details
            names_map = {}
            cities_map = {}
            try:
                import uuid
                from sqlalchemy import MetaData, Table
                _metadata = MetaData()
                customers_tbl = await session.run_sync(
                    lambda sync_conn: Table("customers", _metadata, autoload_with=sync_conn.bind)
                )
                
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
                        customers_tbl.c.city
                    ).where(
                        customers_tbl.c.id.in_(uuid_cids)
                    )
                    
                    res = await session.execute(stmt)
                    for row in res.all():
                        names_map[str(row.id)] = row.business_name
                        cities_map[str(row.id)] = row.city
            except Exception as e:
                logger.warning(f"Could not load customer names and cities in bulk: {e}")

            # 4. Process each customer
            for cid in customer_ids:
                try:
                    async with session.begin_nested():
                        cust_df = runtime_df.filter(pl.col("customer_id") == cid)
                        
                        if cust_df.is_empty():
                            # Handle Zero-History Customer (inactive initialization)
                            logger.debug(f"Initializing inactive state for zero-history customer {cid}")
                            intel_data = {
                                "customer_id": cid,
                                "customer_name": names_map.get(cid),
                                "city": cities_map.get(cid),
                                "trust_score": 0.0,
                                "purchase_score": 0.0,
                                "payment_score": 0.0,
                                "rg_score": 0.0,
                                "contribution_current": 0.0,
                                "outstanding_current": 0.0,
                                "state": "inactive",
                                "trust_previous": 0.0,
                                "purchase_previous": 0.0,
                                "payment_previous": 0.0,
                                "rg_previous": 0.0,
                                "contribution_previous": 0.0,
                                "outstanding_previous": 0.0,
                                "last_purchase_date": None,
                            }
                            await repo.persist_intelligence(intel_data)
                            continue

                        # Current Window Analysis (last 365d)
                        current_ctx = AnalysisContext(window_days=365, end_date=current_end.date())
                        curr_states, curr_conf = self.compute_intelligence(cust_df, current_ctx, org_metrics=curr_org_metrics, customer_avg_billing=curr_avg_billing)
                        curr_row = curr_states.sort("date").tail(1).to_dicts()[0] if not curr_states.is_empty() else {}

                        # Extract absolute outstanding at current_end
                        curr_outstanding = curr_row.get("outstanding_balance", 0.0) if curr_row else 0.0

                        # Previous Window Analysis (730d -> 365d)
                        prev_ctx = AnalysisContext(window_days=365, end_date=prev_end.date())
                        prev_states, prev_conf = self.compute_intelligence(cust_df, prev_ctx, org_metrics=prev_org_metrics, customer_avg_billing=prev_avg_billing)
                        prev_row = prev_states.sort("date").tail(1).to_dicts()[0] if not prev_states.is_empty() else {}

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

                        # 5. Populate Consolidated Intelligence Data (Cache)
                        intel_data = {
                            "customer_id": cid,
                            "customer_name": names_map.get(cid),
                            "city": cities_map.get(cid),
                            "trust_score": curr_row.get("trust_score"),
                            "purchase_score": curr_row.get("purchase_behavior_score"),
                            "payment_score": curr_row.get("payment_behavior_score"),
                            "rg_score": curr_row.get("rg_rate_score"),
                            "contribution_current": curr_contrib,
                            "outstanding_current": curr_outstanding,
                            "state": curr_row.get("behavioral_state"),
                            "trust_previous": prev_row.get("trust_score"),
                            "purchase_previous": prev_row.get("purchase_behavior_score"),
                            "payment_previous": prev_row.get("payment_behavior_score"),
                            "rg_previous": prev_row.get("rg_rate_score"),
                            "contribution_previous": prev_contrib,
                            "outstanding_previous": prev_outstanding,
                            "last_purchase_date": last_purchase_date,
                        }

                        await repo.persist_intelligence(intel_data)

                except Exception as e:
                    logger.error(f"Failed to recompute intelligence for customer {cid}: {e}")
                    continue

            await session.commit()

    async def run_dynamic(self, customer_ids: list[str], context: AnalysisContext) -> pl.DataFrame:
        """
        Dynamically computes intelligence for the requested customers and context.
        Does NOT persist to database.
        """
        logger.debug(
            f"Dynamically computing intelligence for {len(customer_ids)} customers | Context: {context.window_str}"
        )

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
        logger.debug(
            f"Computing intelligence timeline for customer {customer_id} | Context: {context.window_str}"
        )

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
