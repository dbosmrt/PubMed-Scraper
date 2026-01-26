"""
PubMed Scraper - Crawler Factory

Provides a unified interface for creating and managing source-specific crawlers.
"""

from typing import Type

from src.crawlers.arxiv import ArxivCrawler
from src.crawlers.base import BaseCrawler, FilterParams, Paper
from src.crawlers.biorxiv import BiorxivCrawler, MedrxivCrawler
from src.crawlers.pubmed import PubMedCrawler
from src.shared.constants import Source
from src.shared.exceptions import CrawlerError


class CrawlerFactory:
    """
    Factory for creating source-specific crawlers.

    Usage:
        crawler = CrawlerFactory.get(Source.PUBMED)
        async with crawler:
            async for paper in crawler.crawl("cancer"):
                print(paper.title)
    """

    _crawlers: dict[Source, Type[BaseCrawler]] = {
        Source.PUBMED: PubMedCrawler,
        Source.ARXIV: ArxivCrawler,
        Source.BIORXIV: BiorxivCrawler,
        Source.MEDRXIV: MedrxivCrawler,
    }

    @classmethod
    def get(cls, source: Source | str) -> BaseCrawler:
        """
        Get a crawler instance for the specified source.

        Args:
            source: Data source (Source enum or string)

        Returns:
            Crawler instance

        Raises:
            CrawlerError: If source is not supported
        """
        if isinstance(source, str):
            try:
                source = Source(source.lower())
            except ValueError:
                raise CrawlerError(f"Unknown source: {source}")

        crawler_class = cls._crawlers.get(source)
        if crawler_class is None:
            raise CrawlerError(f"No crawler available for source: {source}")

        return crawler_class()

    @classmethod
    def get_available_sources(cls) -> list[Source]:
        """Get list of available data sources."""
        return list(cls._crawlers.keys())

    @classmethod
    def register(cls, source: Source, crawler_class: Type[BaseCrawler]) -> None:
        """
        Register a new crawler for a source.

        Args:
            source: Data source
            crawler_class: Crawler class (must inherit from BaseCrawler)
        """
        cls._crawlers[source] = crawler_class


__all__ = [
    # Factory
    "CrawlerFactory",
    # Base classes
    "BaseCrawler",
    "FilterParams",
    "Paper",
    # Concrete crawlers
    "PubMedCrawler",
    "ArxivCrawler",
    "BiorxivCrawler",
    "MedrxivCrawler",
]
