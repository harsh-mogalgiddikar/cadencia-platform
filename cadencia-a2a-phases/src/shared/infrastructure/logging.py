"""
Structured JSON logging via structlog.

context.md §5: structlog (structured JSON; request_id on every line).
context.md §14: mask sensitive fields (passwords, mnemonics, API keys).
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# Fields to mask in log output — context.md §14 data security
_SENSITIVE_FIELDS = frozenset(
    {
        "password",
        "password_hash",
        "mnemonic",
        "api_key",
        "secret",
        "token",
        "jwt",
        "private_key",
        "authorization",
    }
)
_MASK = "***REDACTED***"


def _mask_sensitive(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """Processor that redacts sensitive field values before logging."""
    for key in list(event_dict.keys()):
        if any(sensitive in key.lower() for sensitive in _SENSITIVE_FIELDS):
            event_dict[key] = _MASK
    return event_dict


def configure_logging() -> None:
    """
    Configure structlog with JSON rendering.

    Log level:
        DEBUG  — APP_ENV=development
        INFO   — all other environments

    Must be called once at application startup (in lifespan).
    """
    app_env = os.environ.get("APP_ENV", "development")
    log_level_str = "DEBUG" if app_env == "development" else "INFO"
    log_level = getattr(logging, log_level_str)

    # Standard library logging configuration
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _mask_sensitive,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if app_env == "development":
        # Pretty console output in development
        renderer: Any = structlog.dev.ConsoleRenderer()
    else:
        # Machine-readable JSON in production
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Return a named structlog logger.

    Usage:
        log = get_logger(__name__)
        log.info("event_name", key="value", request_id=request_id)
    """
    return structlog.get_logger(name)
