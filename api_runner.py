import uvicorn
from core.config.settings import settings

if __name__ == "__main__":
    # Start the API server
    uvicorn.run(
        "core.main:app",
        host=settings.HOST,
        port=settings.PORT,
        workers=settings.WORKERS,
        reload=settings.DEBUG if settings.APP_ENV == "development" else False
    )
