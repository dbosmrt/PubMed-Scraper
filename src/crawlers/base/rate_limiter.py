"""
PubMed Scraper - Rate Limiter

Implements token bucket rate limiting for API requests.
Supports per-source rate limits as required by different APIs.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict

from src.shared.constants import DEFAULT_RATE_LIMITS, Source
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass
class TokenBucket:
    """
    Token bucket rate limiter implementation.

    Tokens are added at a fixed rate, and each request consumes one token.
    If no tokens are available, the request waits until a token is available.
    """

    rate: float  # Tokens per second
    capacity: float  # Maximum tokens in bucket
    tokens: float = field(init=False)
    last_update: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)

    def __post_init__(self) -> None:
        self.tokens = self.capacity
        self.last_update = time.monotonic()

    async def acquire(self) -> float:
        """
        Acquire a token, waiting if necessary.

        Returns:
            Time waited in seconds
        """
        async with self._lock:
            now = time.monotonic()

            # Add tokens based on elapsed time
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return 0.0

            # Calculate wait time for next token
            wait_time = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(wait_time)

            self.tokens = 0.0
            self.last_update = time.monotonic()
            return wait_time


class RateLimiter:
    """
    Manages rate limiters for multiple sources.

    Usage:
        limiter = RateLimiter()
        await limiter.acquire(Source.PUBMED)  # Waits if rate limited
    """

    def __init__(self) -> None:
        self._buckets: Dict[Source, TokenBucket] = {}
        self._init_buckets()

    def _init_buckets(self) -> None:
        """Initialize token buckets for all sources."""
        for source, rate in DEFAULT_RATE_LIMITS.items():
            self._buckets[source] = TokenBucket(
                rate=rate,
                capacity=rate * 2,  # Allow small bursts
            )
        logger.debug("Rate limiter initialized", sources=list(DEFAULT_RATE_LIMITS.keys()))

    async def acquire(self, source: Source) -> float:
        """
        Acquire permission to make a request to the given source.

        Args:
            source: The data source

        Returns:
            Time waited in seconds
        """
        if source not in self._buckets:
            logger.warning("Unknown source, using default rate limit", source=str(source))
            self._buckets[source] = TokenBucket(rate=1.0, capacity=2.0)

        wait_time = await self._buckets[source].acquire()

        if wait_time > 0:
            logger.debug(
                "Rate limited",
                source=str(source),
                waited_seconds=round(wait_time, 3),
            )

        return wait_time

    def update_rate(self, source: Source, new_rate: float) -> None:
        """
        Update the rate limit for a source.

        Useful when API returns rate limit headers indicating a different limit.

        Args:
            source: The data source
            new_rate: New rate in requests per second
        """
        self._buckets[source] = TokenBucket(rate=new_rate, capacity=new_rate * 2)
        logger.info("Rate limit updated", source=str(source), new_rate=new_rate)


# Global rate limiter instance
rate_limiter = RateLimiter()
