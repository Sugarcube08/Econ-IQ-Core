import sys

from loguru import logger

from core.config.settings import settings


def setup_logging():
    logger.remove()

    # Standard output handler (JSON or Human-readable)
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=settings.LOG_LEVEL.upper(),
    )

    logger.info("Logging initialized (Pure Stateless/Postgres Mode).")


setup_logging()
