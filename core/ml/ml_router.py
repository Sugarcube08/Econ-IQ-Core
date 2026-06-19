
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.calibration.calibration_service import CalibrationService
from core.ml.model_registry.model_metadata_dto import ModelMetadataDTO
from core.ml.model_registry.model_registry_repository import ModelRegistryRepository
from core.storage.postgres import get_db

router = APIRouter(prefix="/ml", tags=["ML General Operations"])

@router.get("/status")
async def get_ml_status(db: AsyncSession = Depends(get_db)):
    """
    Retrieves the overall health, count, and last training cycle of ML models.
    """
    repo = ModelRegistryRepository(db)
    models = await repo.get_all_models()
    active = await repo.get_active_models()
    last_trained = models[0].trained_at if models else None
    return {
        "status": "healthy",
        "total_models": len(models),
        "active_models_count": len(active),
        "last_trained_at": last_trained
    }

@router.get("/models", response_model=list[ModelMetadataDTO])
async def get_all_models(db: AsyncSession = Depends(get_db)):
    """
    Lists metadata for all trained or baseline models registered in the system.
    """
    repo = ModelRegistryRepository(db)
    return await repo.get_all_models()

@router.get("/models/active", response_model=list[ModelMetadataDTO])
async def get_active_models(db: AsyncSession = Depends(get_db)):
    """
    Lists metadata for all currently ACTIVE models registered in the system.
    """
    repo = ModelRegistryRepository(db)
    return await repo.get_active_models()

@router.get("/models/{name}", response_model=ModelMetadataDTO)
async def get_model_by_name(name: str, db: AsyncSession = Depends(get_db)):
    """
    Retrieves metadata for a specific registered model by name.
    """
    repo = ModelRegistryRepository(db)
    model = await repo.get_model_by_name(name)
    if not model:
        raise HTTPException(status_code=404, detail=f"Model metadata not found for name: {name}")
    return model

@router.get("/calibration")
async def get_calibration(db: AsyncSession = Depends(get_db)):
    """
    Computes and retrieves binary calibration evaluation metrics (ECE, Brier Score, Reliability Curve)
    and updates system artifacts.
    """
    service = CalibrationService()
    try:
        result = await service.run_calibration_audit(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Calibration audit failed: {e}") from e
