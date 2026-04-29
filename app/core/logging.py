"""
Structured logging with structlog.
JSON in production, coloured console in development.
"""
import logging
import sys
import structlog
from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    shared = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.ExceptionRenderer(),
    ]
    renderer = structlog.processors.JSONRenderer() if settings.is_production \
               else structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=renderer, foreign_pre_chain=shared
    ))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if settings.debug else logging.INFO)
    if settings.is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str = __name__):
    return structlog.get_logger(name)