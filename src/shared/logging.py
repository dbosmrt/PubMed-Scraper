"""
PubMed Scraper - Structured Logging Module

Provides structured logging using structlog with JSON output for production
and colored console output for development.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor

from src.shared.config import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""

    # Determine if we're in development or production
    is_dev = not settings.app.is_production

    # Shared processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        # Development: colored console output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.app.log_level),
    )


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """
    Get a logger instance with optional initial context.

    Args:
        name: Logger name (usually __name__)
        **initial_context: Key-value pairs to bind to the logger

    Returns:
        Configured structlog logger

    Example:
        >>> logger = get_logger(__name__, source="pubmed", job_id="123")
        >>> logger.info("Starting crawl", query="cancer")
    """
    logger = structlog.get_logger(name)
    if initial_context:
        logger = logger.bind(**initial_context)
    return logger


class LoggerMixin:
    """
    Mixin class to add logging capabilities to any class.

    Example:
        >>> class MyCrawler(LoggerMixin):
        ...     def crawl(self):
        ...         self.logger.info("Starting crawl")
    """

    @property
    def logger(self) -> structlog.stdlib.BoundLogger:
        if not hasattr(self, "_logger"):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


# Initialize logging on module import
setup_logging()
