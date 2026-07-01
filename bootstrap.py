import asyncio
import sys
import gc
from datetime import date, datetime, UTC
from sqlalchemy import text, select
from loguru import logger

from core.config.settings import settings
from core.storage.postgres import AsyncSessionLocal, wait_for_db_tables
from core.storage.redis import redis_manager
from core.ml.features.feature_snapshot import generate_snapshot
from core.ml.predictions.prediction_service import generate_predictions_for_snapshot
from core.recommendation.service import RecommendationService
from core.ml.outcomes.outcome_service import evaluate_pending_predictions
from core.ml.calibration.calibration_service import CalibrationService
from core.models.state_models import FeatureSnapshot, CustomerPrediction, Recommendation

async def main():
    logger.info("BOOTSTRAP | Starting EconIQ Bootstrap Pipeline")
    
    # 1. Validate database
    logger.info("BOOTSTRAP | Step 1: Validating database connection and schema...")
    if not await wait_for_db_tables(timeout=30):
        logger.error("BOOTSTRAP | Database schema is not ready. Exiting.")
        sys.exit(1)
        
    await redis_manager.connect()
    
    async with AsyncSessionLocal() as session:
        # Get all customer IDs
        res = await session.execute(text("SELECT id FROM customers"))
        customer_ids = [str(row[0]) for row in res.fetchall()]
        
        # Check existing snapshots, predictions, recommendations
        snap_res = await session.execute(text("SELECT DISTINCT customer_id FROM feature_snapshots"))
        existing_snaps = {str(row[0]) for row in snap_res.fetchall()}
        
        pred_res = await session.execute(text("SELECT DISTINCT customer_id FROM customer_predictions"))
        existing_preds = {str(row[0]) for row in pred_res.fetchall()}
        
        rec_res = await session.execute(text("SELECT DISTINCT customer_id FROM recommendations"))
        existing_recs = {str(row[0]) for row in rec_res.fetchall()}
        
    total_cust = len(customer_ids)
    logger.info(f"BOOTSTRAP | Found {total_cust} customers in database.")
    
    # 2. Generate missing feature snapshots
    logger.info("BOOTSTRAP | Step 2: Generating missing feature snapshots...")
    missing_snaps = [cid for cid in customer_ids if cid not in existing_snaps]
    logger.info(f"BOOTSTRAP | {len(missing_snaps)} customers missing snapshots. Generating...")
    
    for idx, cid in enumerate(missing_snaps):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await generate_snapshot(cid, session)
            if (idx + 1) % 100 == 0:
                gc.collect()
        except Exception as e:
            logger.error(f"BOOTSTRAP | Failed to generate snapshot for customer {cid}: {e}")
            
    # 3. Generate predictions (including SHAP top factors)
    logger.info("BOOTSTRAP | Step 3 & 5: Generating predictions and SHAP explanations...")
    missing_preds = [cid for cid in customer_ids if cid not in existing_preds]
    logger.info(f"BOOTSTRAP | {len(missing_preds)} customers missing predictions/SHAP. Generating...")
    
    for idx, cid in enumerate(missing_preds):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    # Get latest snapshot id
                    stmt = select(FeatureSnapshot).where(FeatureSnapshot.customer_id == cid).order_by(FeatureSnapshot.snapshot_date.desc()).limit(1)
                    snap = (await session.execute(stmt)).scalars().first()
                    if snap:
                        await generate_predictions_for_snapshot(cid, snap.snapshot_id, session)
            if (idx + 1) % 100 == 0:
                gc.collect()
        except Exception as e:
            logger.error(f"BOOTSTRAP | Failed to generate predictions for customer {cid}: {e}")
            
    # 4. Generate recommendations
    logger.info("BOOTSTRAP | Step 4: Generating recommendations...")
    missing_recs = [cid for cid in customer_ids if cid not in existing_recs]
    logger.info(f"BOOTSTRAP | {len(missing_recs)} customers missing recommendations. Generating...")
    
    for idx, cid in enumerate(missing_recs):
        try:
            async with AsyncSessionLocal() as session:
                async with session.begin():
                    await RecommendationService().generate_recommendations(session, cid)
            if (idx + 1) % 100 == 0:
                gc.collect()
        except Exception as e:
            logger.error(f"BOOTSTRAP | Failed to generate recommendations for customer {cid}: {e}")
            
    # 5. Outcome resolver
    logger.info("BOOTSTRAP | Step 5 (Outcomes): Resolving pending predictions...")
    try:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                resolved = await evaluate_pending_predictions(session)
        logger.info(f"BOOTSTRAP | Resolved {len(resolved)} prediction outcomes.")
    except Exception as e:
        logger.error(f"BOOTSTRAP | Outcome resolution failed: {e}")
        
    # 6. Validate calibration
    logger.info("BOOTSTRAP | Step 6: Running calibration audit...")
    try:
        async with AsyncSessionLocal() as session:
            # We don't wrap in transaction because CalibrationService might perform its own flushes
            await CalibrationService().run_calibration_audit(session)
            await session.commit()
        logger.info("BOOTSTRAP | Calibration audit completed.")
    except Exception as e:
        logger.error(f"BOOTSTRAP | Calibration audit failed: {e}")
        
    # 7. Validate integrity
    logger.info("BOOTSTRAP | Step 7: Verifying data integrity...")
    async with AsyncSessionLocal() as session:
        cust_count = (await session.execute(text("SELECT COUNT(*) FROM customers"))).scalar() or 0
        snap_count = (await session.execute(text("SELECT COUNT(*) FROM feature_snapshots"))).scalar() or 0
        pred_count = (await session.execute(text("SELECT COUNT(*) FROM customer_predictions"))).scalar() or 0
        rec_count = (await session.execute(text("SELECT COUNT(*) FROM recommendations"))).scalar() or 0
        
    summary = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ECONIQ BOOTSTRAP COMPLETE

Customers .......... {cust_count}
Feature Snapshots .. {snap_count}
Predictions ........ {pred_count}
Recommendations .... {rec_count}
SHAP ............... Ready

Status ............. SUCCESS

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    logger.info(summary)
    print(summary)
    
    await redis_manager.disconnect()
    logger.info("BOOTSTRAP | Exiting bootstrap successfully.")
    sys.exit(0)

if __name__ == "__main__":
    asyncio.run(main())
