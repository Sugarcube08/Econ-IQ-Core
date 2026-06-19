
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.ml.model_registry.model_metadata_dto import ModelMetadataDTO
from core.models.state_models import ModelRegistry


class ModelRegistryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_models(self) -> list[ModelMetadataDTO]:
        stmt = select(ModelRegistry).order_by(ModelRegistry.trained_at.desc())
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [ModelMetadataDTO.model_validate(m) for m in models]

    async def get_model_by_name(self, name: str) -> ModelMetadataDTO | None:
        stmt = (
            select(ModelRegistry)
            .where(ModelRegistry.model_name == name)
            .order_by(ModelRegistry.trained_at.desc())
            .limit(1)
        )
        res = await self.session.execute(stmt)
        model = res.scalars().first()
        if not model:
            return None
        return ModelMetadataDTO.model_validate(model)

    async def get_active_models(self) -> list[ModelMetadataDTO]:
        stmt = (
            select(ModelRegistry)
            .where(ModelRegistry.status == "ACTIVE")
            .order_by(ModelRegistry.model_name.asc())
        )
        res = await self.session.execute(stmt)
        models = res.scalars().all()
        return [ModelMetadataDTO.model_validate(m) for m in models]

    async def upsert_model_metadata(self, dto: ModelMetadataDTO) -> None:
        stmt = select(ModelRegistry).where(ModelRegistry.id == dto.id)
        res = await self.session.execute(stmt)
        existing = res.scalars().first()
        if existing:
            for k, v in dto.model_dump().items():
                setattr(existing, k, v)
        else:
            if dto.status == "ACTIVE":
                await self.session.execute(
                    update(ModelRegistry)
                    .where(and_(ModelRegistry.model_name == dto.model_name, ModelRegistry.status == "ACTIVE"))
                    .values(status="BASELINE")
                )
            model = ModelRegistry(**dto.model_dump())
            self.session.add(model)
        await self.session.flush()
