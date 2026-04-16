"""
Structured Logging Configuration.

Uses structlog for structured, context-rich log output:
  - Development: coloured, human-readable console output
  - Production:  JSON output compatible with Datadog, CloudWatch,
                 Grafana Loki, and any log aggregation platform

Every log entry automatically includes:
  - timestamp (ISO 8601)
  - log level
  - logger name (module path)
  - event message
  - any key=value pairs passed at the call site

Usage anywhere in the codebase:
    from app.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("order_placed", order_id=order_id, total=total)
    logger.warning("low_stock", product_id=product_id, stock=stock)
    logger.error("payment_failed", reference=ref, error=str(e))

Configuration is called once at startup in main.py via configure_logging().
"""
import logging
import sys

import structlog

from app.core.config import get_settings


def configure_logging() -> None:
    """
    Configure structlog and the stdlib logging bridge.

    Call this exactly once, at application startup (in main.py),
    before any logger is used.
    """
    settings = get_settings()

    # Processors shared between structlog and the stdlib bridge.
    # These run on every log record regardless of renderer.
    shared_processors: list = [
        # Merge any context variables bound with structlog.contextvars.bind_contextvars()
        # Useful for binding request_id at middleware level so it appears in all logs
        structlog.contextvars.merge_contextvars,
        # Add the logger's name (module path) to every event
        structlog.stdlib.add_logger_name,
        # Add the log level string ("info", "warning", etc.)
        structlog.stdlib.add_log_level,
        # ISO 8601 timestamp on every record
        structlog.processors.TimeStamper(fmt="iso"),
        # Render stack traces as structured data (not raw strings)
        structlog.processors.StackInfoRenderer(),
        # Format exception info when exc_info=True is passed
        structlog.processors.ExceptionRenderer(),
    ]

    # Choose renderer based on environment
    if settings.is_production:
        # Compact JSON — one line per log entry, machine-parseable
        renderer = structlog.processors.JSONRenderer()
    else:
        # Coloured, human-readable output for local development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    # Configure structlog itself
    structlog.configure(
        processors=shared_processors + [
            # Wrap the event dict so stdlib's ProcessorFormatter can handle it
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        # Cache the logger on first use for performance
        cache_logger_on_first_use=True,
    )

    # Bridge: make stdlib logging go through structlog's pipeline
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # Replace any existing handlers (avoids duplicate output)
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)

    # Silence noisy third-party loggers in production
    if settings.is_production:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str = __name__):
    """
    Get a structlog logger bound to the given name.

    Conventionally called at module level:
        logger = get_logger(__name__)

    The name appears as the "logger" field in every log record,
    making it easy to filter logs by module in production.
    """
    return structlog.get_logger(name)
