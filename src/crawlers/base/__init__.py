"""
PubMed Scraper - Base Crawler Module

Provides abstract base classes and utilities for all source-specific crawlers.
"""

from src.crawlers.base.abstract_crawler import (
    Author,
    BaseCrawler,
    FilterParams,
    Paper,
)
from src.crawlers.base.rate_limiter import RateLimiter, TokenBucket, rate_limiter

__all__ = [
    "Author",
    "BaseCrawler",
    "FilterParams",
    "Paper",
    "RateLimiter",
    "TokenBucket",
    "rate_limiter",
]
