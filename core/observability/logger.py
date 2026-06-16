import sys

from loguru import logger

from core.config.settings import settings


def setup_logging():
    logger.remove()

    def formatter(record):
        extra = record["extra"]
        extra_str = ""
        if extra:
            extra_str = " | " + " ".join(f"{k}={v}" for k, v in extra.items())
        return f"<green>{{time:YYYY-MM-DD HH:mm:ss.SSS}}</green> | <level>{{level: <8}}</level> | <level>{{message}}{extra_str}</level>\n"

    # Standard output handler
    logger.add(
        sys.stdout,
        colorize=True,
        format=formatter,
        level=settings.LOG_LEVEL.upper(),
    )

    logger.info("SYSTEM | Logging initialized (Pure Stateless/Postgres Mode)")


setup_logging()
