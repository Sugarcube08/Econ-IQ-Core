import asyncio
import sys

from loguru import logger

from core.ml.prediction_service import MLPredictionService


async def main():
    from core.config.settings import settings
    if settings.RUNTIME_MODE == "SERVING":
        logger.warning("ML | Runtime mode is set to SERVING. ML pipelines are disabled. Exiting ML runner.")
        sys.exit(0)

    from core.storage.postgres import wait_for_db_tables
    if not await wait_for_db_tables(timeout=30):
        logger.error("ML | Database schema is not ready. Exiting.")
        sys.exit(1)

    # If no customer ID is passed, run a demo with a query
    if len(sys.argv) < 2:
        # Fetch a customer ID from the database for demo
        from sqlalchemy import text

        from core.storage.postgres import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT customer_id FROM customer_intelligence LIMIT 1"))
            customer_id = res.scalar()
        if not customer_id:
            logger.error("ML | No customers found in database to run ML stub.")
            sys.exit(1)
        logger.info(f"ML | No customer_id provided. Using demo customer: {customer_id}")
    else:
        customer_id = sys.argv[1]
        
    logger.info(f"ML | Running prediction inference for customer: {customer_id}")
    
    service = MLPredictionService()
    
    churn = await service.predict_churn(customer_id)
    risk = await service.predict_credit_risk(customer_id)
    delinq = await service.predict_delinquency(customer_id)
    
    print(f"\n--- ML PREDICTIONS FOR CUSTOMER: {customer_id} ---")
    print(f"  Churn:       Probability={churn['probability']:.4f} | Label={churn['label']}")
    print(f"  Credit Risk: Probability={risk['probability']:.4f} | Label={risk['label']}")
    print(f"  Delinquency: Probability={delinq['probability']:.4f} | Label={delinq['label']}")

if __name__ == "__main__":
    asyncio.run(main())
