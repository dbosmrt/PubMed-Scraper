"""
PubMed Scraper - Shared Module

Common utilities, configurations, and constants used across all microservices.
"""

from src.shared.config import Settings, get_settings, settings
from src.shared.constants import PaperType, Source
from src.shared.exceptions import (
    BaseScraperError,
    CrawlerError,
    ExportError,
    ParserError,
    RateLimitError,
    StorageError,
)

__all__ = [
    # Config
    "Settings",
    "get_settings",
    "settings",
    # Constants
    "PaperType",
    "Source",
    # Exceptions
    "BaseScraperError",
    "CrawlerError",
    "ParserError",
    "RateLimitError",
    "StorageError",
    "ExportError",
]
