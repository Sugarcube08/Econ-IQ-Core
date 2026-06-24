import asyncio
import json
import uuid
from datetime import date, timedelta

from sqlalchemy import text

from core.storage.postgres import AsyncSessionLocal

# Define UUID constants
WHALE_ID = "00000000-0000-0000-0000-000000000001"
DISTRESSED_ID = "00000000-0000-0000-0000-000000000002"
RECOVERING_ID = "00000000-0000-0000-0000-000000000003"
DORMANT_ID = "00000000-0000-0000-0000-000000000004"
EXPANSION_ID = "00000000-0000-0000-0000-000000000005"

async def seed():
    print("DEMO SEED | Connecting to database...")
    async with AsyncSessionLocal() as s:
        # 1. Clean existing records for these IDs to ensure clean re-runs
        ids = [WHALE_ID, DISTRESSED_ID, RECOVERING_ID, DORMANT_ID, EXPANSION_ID]
        print(f"DEMO SEED | Cleaning old entries for: {ids}...")
        
        id_str = "('00000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000005')"
        
        await s.execute(text(f"DELETE FROM decision_audit WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM recommendations WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM payment_commitments WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM collections_activity WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM alerts WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM feature_snapshots WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM event_ledger WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM customer_intelligence WHERE customer_id IN {id_str}"))
        await s.execute(text(f"DELETE FROM customers WHERE id IN {id_str}"))
        
        await s.commit()
        print("DEMO SEED | Clean-up complete.")

        # 2. Seed `customers` table
        print("DEMO SEED | Inserting into customers table...")
        customers_data = [
            {
                "id": WHALE_ID, "code": "CUST-WHALE", "name": "Titan B2B Industries",
                "city": "Mumbai", "state": "Maharashtra", "limit": 5000000, "days": 30,
                "profile": {
                    "state": "elite",
                    "v2_scores": {
                        "dimensions": {
                            "activity": 0.95, "discipline": 0.94, "credit": 0.95,
                            "relationship": 0.93, "product": 0.85, "friction": 0.05,
                            "growth": 0.85, "stability": 0.92
                        }
                    }
                }
            },
            {
                "id": DISTRESSED_ID, "code": "CUST-DISTRESSED", "name": "Deccan Logistics Ltd",
                "city": "Hyderabad", "state": "Telangana", "limit": 1000000, "days": 30,
                "profile": {
                    "state": "declining",
                    "v2_scores": {
                        "dimensions": {
                            "activity": 0.40, "discipline": 0.15, "credit": 0.20,
                            "relationship": 0.40, "product": 0.50, "friction": 0.88,
                            "growth": 0.15, "stability": 0.31
                        }
                    }
                }
            },
            {
                "id": RECOVERING_ID, "code": "CUST-RECOVERING", "name": "Himalayan Forge Corp",
                "city": "Shimla", "state": "Himachal Pradesh", "limit": 1500000, "days": 45,
                "profile": {
                    "state": "irregular",
                    "v2_scores": {
                        "dimensions": {
                            "activity": 0.65, "discipline": 0.82, "credit": 0.58,
                            "relationship": 0.65, "product": 0.45, "friction": 0.32,
                            "growth": 0.45, "stability": 0.61
                        }
                    }
                }
            },
            {
                "id": DORMANT_ID, "code": "CUST-DORMANT", "name": "Coromandel Retailers",
                "city": "Chennai", "state": "Tamil Nadu", "limit": 2000000, "days": 30,
                "profile": {
                    "state": "inactive",
                    "v2_scores": {
                        "dimensions": {
                            "activity": 0.10, "discipline": 0.91, "credit": 0.65,
                            "relationship": 0.30, "product": 0.20, "friction": 0.15,
                            "growth": 0.10, "stability": 0.27
                        }
                    }
                }
            },
            {
                "id": EXPANSION_ID, "code": "CUST-EXPANSION", "name": "Narmada Agri Solutions",
                "city": "Bhopal", "state": "Madhya Pradesh", "limit": 3000000, "days": 30,
                "profile": {
                    "state": "active",
                    "v2_scores": {
                        "dimensions": {
                            "activity": 0.85, "discipline": 0.85, "credit": 0.80,
                            "relationship": 0.85, "product": 0.88, "friction": 0.08,
                            "growth": 0.88, "stability": 0.83
                        }
                    }
                }
            }
        ]

        for c in customers_data:
            stmt = text("""
                INSERT INTO customers (id, customer_code, business_name, city, state, credit_limit, payment_terms_days, is_active, behavioral_profile, registration_date, created_at, updated_at)
                VALUES (:id, :code, :name, :city, :state, :limit, :days, TRUE, :profile, :reg_date, NOW(), NOW())
            """)
            await s.execute(stmt, {
                "id": uuid.UUID(c["id"]),
                "code": c["code"],
                "name": c["name"],
                "city": c["city"],
                "state": c["state"],
                "limit": c["limit"],
                "days": c["days"],
                "profile": json.dumps(c["profile"]),
                "reg_date": date.today() - timedelta(days=365)
            })

        # 3. Seed `customer_intelligence` table
        print("DEMO SEED | Inserting into customer_intelligence table...")
        intelligence_data = [
            # 1. Whale
            {
                "id": WHALE_ID, "name": "Titan B2B Industries", "city": "Mumbai",
                "health": 0.92, "risk": 0.08, "growth": 0.85, "trust": 0.94,
                "opp": 0.35, "credit": 0.95, "coll": 0.02, "rel": 0.93,
                "outstanding": 1250000.0, "contrib": 0.142, "state": "elite",
                "curr_state": "healthy", "archetype": "whale", "risk_dir": "stable", "trust_dir": "stable"
            },
            # 2. Distressed
            {
                "id": DISTRESSED_ID, "name": "Deccan Logistics Ltd", "city": "Hyderabad",
                "health": 0.31, "risk": 0.89, "growth": 0.15, "trust": 0.25,
                "opp": 0.65, "credit": 0.20, "coll": 0.88, "rel": 0.40,
                "outstanding": 840000.0, "contrib": 0.021, "state": "declining",
                "curr_state": "declining", "archetype": "declining_retailer", "risk_dir": "increasing", "trust_dir": "decreasing"
            },
            # 3. Recovering
            {
                "id": RECOVERING_ID, "name": "Himalayan Forge Corp", "city": "Shimla",
                "health": 0.61, "risk": 0.38, "growth": 0.45, "trust": 0.82,
                "opp": 0.50, "credit": 0.58, "coll": 0.32, "rel": 0.65,
                "outstanding": 320000.0, "contrib": 0.054, "state": "irregular",
                "curr_state": "recovering", "archetype": "liquidity_stressed", "risk_dir": "decreasing", "trust_dir": "increasing"
            },
            # 4. Dormant
            {
                "id": DORMANT_ID, "name": "Coromandel Retailers", "city": "Chennai",
                "health": 0.27, "risk": 0.45, "growth": 0.10, "trust": 0.91,
                "opp": 0.82, "credit": 0.65, "coll": 0.15, "rel": 0.30,
                "outstanding": 0.0, "contrib": 0.0, "state": "inactive",
                "curr_state": "dormant", "archetype": "stable_retailer", "risk_dir": "stable", "trust_dir": "stable"
            },
            # 5. Expansion
            {
                "id": EXPANSION_ID, "name": "Narmada Agri Solutions", "city": "Bhopal",
                "health": 0.83, "risk": 0.12, "growth": 0.88, "trust": 0.85,
                "opp": 0.88, "credit": 0.80, "coll": 0.08, "rel": 0.85,
                "outstanding": 150000.0, "contrib": 0.083, "state": "active",
                "curr_state": "growing", "archetype": "growing_retailer", "risk_dir": "stable", "trust_dir": "stable"
            }
        ]

        for i in intelligence_data:
            stmt = text("""
                INSERT INTO customer_intelligence (
                    customer_id, customer_name, city, health_score, risk_score, growth_score,
                    trust_score, opportunity_score, credit_score, collection_score, relationship_score,
                    outstanding_current, outstanding_previous, contribution_current, contribution_previous,
                    state, current_state, customer_archetype, risk_direction, trust_direction,
                    health_previous, risk_previous, growth_previous, trust_previous, opportunity_previous,
                    credit_previous, collection_previous, relationship_previous,
                    last_purchase_date, last_updated
                ) VALUES (
                    :id, :name, :city, :health, :risk, :growth,
                    :trust, :opp, :credit, :coll, :rel,
                    :outstanding, :outstanding_prev, :contrib, :contrib_prev,
                    :state, :curr_state, :archetype, :risk_dir, :trust_dir,
                    :health_prev, :risk_prev, :growth, :trust, :opp,
                    :credit, :coll, :rel,
                    :last_purchase, NOW()
                )
            """)
            await s.execute(stmt, {
                "id": i["id"],
                "name": i["name"],
                "city": i["city"],
                "health": i["health"],
                "risk": i["risk"],
                "growth": i["growth"],
                "trust": i["trust"],
                "opp": i["opp"],
                "credit": i["credit"],
                "coll": i["coll"],
                "rel": i["rel"],
                "outstanding": i["outstanding"],
                "outstanding_prev": max(0.0, i["outstanding"] * 0.95),
                "contrib": i["contrib"] * 100.0,
                "contrib_prev": max(0.0, i["contrib"] * 95.0),
                "state": i["state"],
                "curr_state": i["curr_state"],
                "archetype": i["archetype"],
                "risk_dir": i["risk_dir"],
                "trust_dir": i["trust_dir"],
                "health_prev": max(0.0, i["health"] - 0.02),
                "risk_prev": max(0.0, i["risk"] + 0.01),
                "last_purchase": date.today() - timedelta(days=5 if i["id"] != DORMANT_ID else 200)
            })

        # 4. Seed Event Ledger (so graph aggregates function properly)
        print("DEMO SEED | Inserting into event_ledger table...")
        ledger_events = []
        base_date = date.today()
        
        # Helper to push ledger rows
        def add_event(cid, etype, days_offset, amount):
            evt_id = str(uuid.uuid4())
            dt = base_date - timedelta(days=days_offset)
            ledger_events.append({
                "event_id": evt_id, "customer_id": cid, "event_type": etype,
                "event_date": dt, "amount": float(amount)
            })

        # Whale Ledger (Very active, clean cycle)
        for d in [90, 60, 30]:
            add_event(WHALE_ID, "SALE", d, 500000)
            add_event(WHALE_ID, "PAYMENT", d - 10, 500000)
        add_event(WHALE_ID, "SALE", 5, 1250000) # Current outstanding

        # Distressed Ledger (Active sales in past, but zero recent payments)
        add_event(DISTRESSED_ID, "SALE", 120, 300000)
        add_event(DISTRESSED_ID, "SALE", 90, 300000)
        add_event(DISTRESSED_ID, "SALE", 60, 240000)
        add_event(DISTRESSED_ID, "PAYMENT", 110, 100000)
        add_event(DISTRESSED_ID, "RETURN", 50, 40000)
        # Net outstanding: 300k+300k+240k - 100k - 40k = 700k. Let's adjust outstanding score match.

        # Recovering Ledger ( Delinquency past, recent recovery payment )
        add_event(RECOVERING_ID, "SALE", 80, 400000)
        add_event(RECOVERING_ID, "PAYMENT", 75, 50000) # Missed balance
        add_event(RECOVERING_ID, "PAYMENT", 5, 230000)  # Major cash infusion

        # Dormant Ledger (Historical transactions only)
        add_event(DORMANT_ID, "SALE", 240, 200000)
        add_event(DORMANT_ID, "PAYMENT", 210, 200000)

        # Expansion Ledger (Small clean cycles)
        add_event(EXPANSION_ID, "SALE", 40, 150000)
        add_event(EXPANSION_ID, "SALE", 5, 150000)
        add_event(EXPANSION_ID, "PAYMENT", 35, 150000)

        for e in ledger_events:
            stmt = text("""
                INSERT INTO event_ledger (event_id, customer_id, event_type, event_date, amount, metadata, is_voided, is_ok, created_at, updated_at)
                VALUES (:event_id, :customer_id, :event_type, :event_date, :amount, '{}', FALSE, 0, NOW(), NOW())
            """)
            await s.execute(stmt, e)

        # 5. Seed Alerts (So operations queue and dashboard are active)
        print("DEMO SEED | Inserting alerts...")
        alerts = [
            {
                "customer_id": DISTRESSED_ID,
                "type": "SEVERE_CREDIT_DEFAULT",
                "severity": "CRITICAL",
                "title": "Outstanding Limit Exceeded",
                "desc": "Outstanding exposure (INR 840,000) has exceeded credit threshold (INR 1,000,000) with zero payments over 90 days."
            },
            {
                "customer_id": RECOVERING_ID,
                "type": "DELINQUENCY_WARNING",
                "severity": "WARNING",
                "title": "Unscheduled Payment Lag",
                "desc": "Account showed average payment delays of 18 days above baseline during prior cycle."
            }
        ]
        
        for a in alerts:
            stmt = text("""
                INSERT INTO alerts (id, customer_id, alert_type, alert_severity, title, description, status, created_at)
                VALUES (:id, :customer_id, :type, :severity, :title, :desc, 'ACTIVE', NOW())
            """)
            await s.execute(stmt, {
                "id": str(uuid.uuid4()), "customer_id": a["customer_id"],
                "type": a["type"], "severity": a["severity"],
                "title": a["title"], "desc": a["desc"]
            })

        # 6. Seed prioritized recommendations
        print("DEMO SEED | Inserting recommendations...")
        recs = [
            {
                "customer_id": DISTRESSED_ID, "type": "CREDIT_HOLD", "severity": "CRITICAL",
                "reason": "High distress risk (0.89) combined with collection score of 0.88 requires immediate credit line suspension.",
                "conf": 0.94
            },
            {
                "customer_id": RECOVERING_ID, "type": "CREATE_PAYMENT_PLAN", "severity": "MEDIUM",
                "reason": "Payment trust has recovered to 0.82. Lock in remaining INR 320,000 balance using structured installments.",
                "conf": 0.81
            },
            {
                "customer_id": EXPANSION_ID, "type": "PROPOSE_CATALOG_EXPANSION", "severity": "HIGH",
                "reason": "Exceptional growth opportunity (0.88) and low risk (0.12) signals client eligibility for product financing packages.",
                "conf": 0.88
            }
        ]

        for r in recs:
            stmt = text("""
                INSERT INTO recommendations (id, customer_id, recommendation_type, severity, reason, confidence, status, created_at)
                VALUES (:id, :customer_id, :type, :severity, :reason, :conf, 'ACTIVE', NOW())
            """)
            await s.execute(stmt, {
                "id": str(uuid.uuid4()), "customer_id": r["customer_id"],
                "type": r["type"], "severity": r["severity"],
                "reason": r["reason"], "conf": r["conf"]
            })

        # 7. Seed model registry
        print("DEMO SEED | Confirming model registry matches...")
        models_check = await s.execute(text("SELECT COUNT(*) FROM model_registry"))
        if (models_check.scalar() or 0) == 0:
            print("DEMO SEED | Populating default model metadata registry...")
            m_types = ["churn", "delinquency", "distress"]
            for m in m_types:
                stmt = text("""
                    INSERT INTO model_registry (id, model_name, version, status, trained_at, dataset_rows, positives, negatives, auc, f1, precision, recall, pr_auc, brier, prediction_count, feedback_count)
                    VALUES (:id, :name, '1.0.0', 'ACTIVE', NOW(), 1000, 200, 800, 0.89, 0.81, 0.83, 0.79, 0.84, 0.08, 0, 0)
                """)
                await s.execute(stmt, {"id": str(uuid.uuid4()), "name": f"behavioral_{m}_xgboost"})
        
        # 8. Seed Feature Snapshots so Simulator works
        print("DEMO SEED | Seeding Feature snapshots for counterfactual simulation...")
        for cid in ids:
            snap_id = str(uuid.uuid4())
            # Find the corresponding data from intelligence_data to keep it consistent
            c_data = next(item for item in intelligence_data if item["id"] == cid)
            
            stmt = text("""
                INSERT INTO feature_snapshots (
                    snapshot_id, customer_id, snapshot_date, snapshot_source, snapshot_version, generator_version, feature_hash,
                    health_score, risk_score, trust_score, growth_score, collection_score, relationship_score, credit_score, opportunity_score,
                    current_state, customer_archetype, risk_direction, trust_direction,
                    billing_30d, billing_90d, billing_180d, payments_30d, payments_90d, payments_180d, returns_30d, returns_90d,
                    purchase_gap, purchase_frequency, payment_delay_avg, payment_delay_trend, collection_efficiency,
                    outstanding_current, outstanding_ratio, credit_utilization, feature_payload_json, created_at
                ) VALUES (
                    :snap_id, :cid, :snap_date, 'BATCH', '1.0.0', '1.0.0', :fhash,
                    :health, :risk, 0.8, 0.8, 0.1, 0.8, 0.8, 0.8,
                    :curr_state, :archetype, :risk_dir, :trust_dir,
                    100000, 300000, 600000, 100000, 300000, 600000, 0, 0,
                    5, 2.5, 3.2, 0.0, 0.95,
                    200000, 0.1, 0.25, '{}', NOW()
                )
            """)
            await s.execute(stmt, {
                "snap_id": snap_id, "cid": cid, "snap_date": date.today(),
                "fhash": str(uuid.uuid4())[:8],
                "health": 0.92 if cid == WHALE_ID else 0.31 if cid == DISTRESSED_ID else 0.61 if cid == RECOVERING_ID else 0.27 if cid == DORMANT_ID else 0.83,
                "risk": 0.08 if cid == WHALE_ID else 0.89 if cid == DISTRESSED_ID else 0.38 if cid == RECOVERING_ID else 0.45 if cid == DORMANT_ID else 0.12,
                "curr_state": c_data["curr_state"],
                "archetype": c_data["archetype"],
                "risk_dir": c_data["risk_dir"],
                "trust_dir": c_data["trust_dir"]
            })

        await s.commit()
        print("DEMO SEED | All tables successfully seeded with the 5 Showcase Customers!")

if __name__ == "__main__":
    asyncio.run(seed())
