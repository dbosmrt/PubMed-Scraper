"""
PubMed Scraper - Abstract Base Crawler

Defines the interface and common functionality for all source-specific crawlers.
Implements retry logic, rate limiting, and standardized data output.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Any, AsyncIterator, Generic, TypeVar

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.shared.config import settings
from src.shared.constants import DEFAULT_RATE_LIMITS, MAX_RETRIES, PaperType, Source
from src.shared.exceptions import CrawlerError, RateLimitError, SourceUnavailableError
from src.shared.logging import LoggerMixin


@dataclass
class FilterParams:
    """Parameters for filtering search results."""

    year_start: int | None = None
    year_end: int | None = None
    countries: list[str] = field(default_factory=list)
    paper_types: list[PaperType] = field(default_factory=list)
    exclude_preprints: bool = False
    languages: list[str] = field(default_factory=lambda: ["en"])
    max_results: int = 1000

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "year_start": self.year_start,
            "year_end": self.year_end,
            "countries": self.countries,
            "paper_types": [str(pt) for pt in self.paper_types],
            "exclude_preprints": self.exclude_preprints,
            "languages": self.languages,
            "max_results": self.max_results,
        }


@dataclass
class Author:
    """Standardized author representation."""

    name: str
    affiliation: str | None = None
    country: str | None = None
    orcid: str | None = None
    email: str | None = None


@dataclass
class Paper:
    """Standardized paper representation across all sources."""

    # Identifiers
    id: str  # Source-specific ID (PMID, arXiv ID, etc.)
    doi: str | None = None
    source: Source = Source.PUBMED

    # Core metadata
    title: str = ""
    abstract: str = ""
    authors: list[Author] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)

    # Publication info
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publication_date: date | None = None
    year: int | None = None

    # Classification
    paper_type: PaperType = PaperType.UNKNOWN
    categories: list[str] = field(default_factory=list)  # Subject categories
    mesh_terms: list[str] = field(default_factory=list)  # MeSH terms (PubMed)

    # URLs
    url: str | None = None
    pdf_url: str | None = None
    pmc_id: str | None = None  # PubMed Central ID

    # Additional metadata
    language: str = "en"
    countries: list[str] = field(default_factory=list)  # Extracted from affiliations
    citations_count: int | None = None
    references_count: int | None = None

    # Raw data for debugging
    raw_data: dict[str, Any] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "id": self.id,
            "doi": self.doi,
            "source": str(self.source),
            "title": self.title,
            "abstract": self.abstract,
            "authors": [
                {
                    "name": a.name,
                    "affiliation": a.affiliation,
                    "country": a.country,
                }
                for a in self.authors
            ],
            "keywords": self.keywords,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "publication_date": str(self.publication_date) if self.publication_date else None,
            "year": self.year,
            "paper_type": str(self.paper_type),
            "categories": self.categories,
            "mesh_terms": self.mesh_terms,
            "url": self.url,
            "pdf_url": self.pdf_url,
            "pmc_id": self.pmc_id,
            "language": self.language,
            "countries": self.countries,
            "citations_count": self.citations_count,
        }


# Type variable for source-specific raw response types
RawResponseT = TypeVar("RawResponseT")


class BaseCrawler(ABC, LoggerMixin, Generic[RawResponseT]):
    """
    Abstract base class for all source crawlers.

    Provides:
    - HTTP client with connection pooling
    - Retry logic with exponential backoff
    - Rate limiting
    - Standardized paper output format
    """

    source: Source  # Must be set by subclasses

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._rate_limit = DEFAULT_RATE_LIMITS.get(self.source, 1)

    @property
    def client(self) -> httpx.AsyncClient:
        """Lazy-initialized HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
                follow_redirects=True,
                headers=self._get_default_headers(),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _get_default_headers(self) -> dict[str, str]:
        """Get default HTTP headers for requests."""
        return {
            "User-Agent": (
                f"PubMed-Scraper/1.0 ({settings.external_api.ncbi_email})"
            ),
            "Accept": "application/xml, application/json, text/xml",
        }

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Make an HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            **kwargs: Additional arguments for httpx

        Returns:
            HTTP response

        Raises:
            RateLimitError: If rate limit is exceeded
            SourceUnavailableError: If source returns 5xx error
            CrawlerError: For other HTTP errors
        """
        self.logger.debug("Making request", method=method, url=url)

        try:
            response = await self.client.request(method, url, **kwargs)

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(str(self.source), retry_after=retry_after)

            if response.status_code >= 500:
                raise SourceUnavailableError(str(self.source), response.status_code)

            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as e:
            self.logger.error("HTTP error", status_code=e.response.status_code, url=url)
            raise CrawlerError(str(e)) from e

    @abstractmethod
    async def search(
        self,
        query: str,
        filters: FilterParams | None = None,
    ) -> list[str]:
        """
        Search for papers matching the query.

        Args:
            query: Search query string
            filters: Optional filters (year range, country, etc.)

        Returns:
            List of paper IDs
        """
        ...

    @abstractmethod
    async def fetch(self, paper_ids: list[str]) -> list[RawResponseT]:
        """
        Fetch full paper data for given IDs.

        Args:
            paper_ids: List of paper identifiers

        Returns:
            List of raw response objects
        """
        ...

    @abstractmethod
    def parse(self, raw_data: RawResponseT) -> Paper:
        """
        Parse raw response into standardized Paper format.

        Args:
            raw_data: Source-specific raw data

        Returns:
            Standardized Paper object
        """
        ...

    async def crawl(
        self,
        query: str,
        filters: FilterParams | None = None,
    ) -> AsyncIterator[Paper]:
        """
        Full crawl pipeline: search → fetch → parse.

        Yields papers one at a time for memory efficiency.

        Args:
            query: Search query
            filters: Optional filters

        Yields:
            Parsed Paper objects
        """
        self.logger.info(
            "Starting crawl",
            source=str(self.source),
            query=query,
            filters=filters.to_dict() if filters else None,
        )

        # Search for paper IDs
        paper_ids = await self.search(query, filters)
        self.logger.info("Found papers", count=len(paper_ids))

        if not paper_ids:
            return

        # Fetch and parse in batches
        batch_size = getattr(self, "batch_size", 100)
        for i in range(0, len(paper_ids), batch_size):
            batch_ids = paper_ids[i : i + batch_size]
            self.logger.debug("Fetching batch", start=i, size=len(batch_ids))

            try:
                raw_papers = await self.fetch(batch_ids)
                for raw_paper in raw_papers:
                    try:
                        paper = self.parse(raw_paper)
                        yield paper
                    except Exception as e:
                        self.logger.warning("Parse error", error=str(e))
                        continue
            except RetryError as e:
                self.logger.error("Fetch failed after retries", batch_start=i)
                continue

    async def __aenter__(self) -> "BaseCrawler":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
