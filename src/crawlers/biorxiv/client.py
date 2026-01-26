"""
PubMed Scraper - bioRxiv/medRxiv API Client

Implements the bioRxiv crawler using the bioRxiv API.
Supports fetching preprints by date range and server (biorxiv/medrxiv).

API Documentation: https://api.biorxiv.org/
"""

from datetime import datetime
from typing import Any

from src.crawlers.base import Author, BaseCrawler, FilterParams, Paper, rate_limiter
from src.shared.config import settings
from src.shared.constants import BIORXIV_BATCH_SIZE, PaperType, Source
from src.shared.exceptions import ParserError


class BiorxivCrawler(BaseCrawler[dict[str, Any]]):
    """
    Crawler for bioRxiv and medRxiv preprint servers.

    Uses the official bioRxiv API which returns JSON data.
    Supports date range filtering and pagination.
    """

    source = Source.BIORXIV
    batch_size = BIORXIV_BATCH_SIZE

    def __init__(self, server: str = "biorxiv") -> None:
        """
        Initialize bioRxiv crawler.

        Args:
            server: Either "biorxiv" or "medrxiv"
        """
        super().__init__()
        self.server = server
        self.base_url = settings.external_api.biorxiv_base_url.replace("biorxiv", server)

    async def search(
        self,
        query: str,
        filters: FilterParams | None = None,
    ) -> list[str]:
        """
        Search bioRxiv for papers.

        Note: bioRxiv API doesn't support keyword search directly.
        We fetch by date range and filter client-side.

        Args:
            query: Search query (used for client-side filtering)
            filters: Filters with date range

        Returns:
            List of bioRxiv DOIs
        """
        await rate_limiter.acquire(self.source)

        # Determine date range
        if filters:
            start_date = f"{filters.year_start or 2013}-01-01"
            end_date = f"{filters.year_end or 2099}-12-31"
        else:
            # Default to last 30 days
            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now().replace(day=1)).strftime("%Y-%m-%d")

        max_results = filters.max_results if filters else 1000

        self.logger.info(
            "Searching bioRxiv",
            server=self.server,
            start_date=start_date,
            end_date=end_date,
            query=query,
        )

        # bioRxiv API: /details/{server}/{start}/{end}/{cursor}
        all_dois = []
        cursor = 0

        while len(all_dois) < max_results:
            url = f"{self.base_url}/{start_date}/{end_date}/{cursor}"

            try:
                response = await self._request("GET", url)
                data = response.json()

                collection = data.get("collection", [])
                if not collection:
                    break

                # Filter by query if provided
                for paper in collection:
                    if len(all_dois) >= max_results:
                        break

                    # Client-side filtering by query
                    if query:
                        title = paper.get("title", "").lower()
                        abstract = paper.get("abstract", "").lower()
                        query_lower = query.lower()

                        if query_lower not in title and query_lower not in abstract:
                            continue

                    doi = paper.get("doi")
                    if doi:
                        all_dois.append(doi)

                # Check if more pages available
                messages = data.get("messages", [])
                total = 0
                for msg in messages:
                    if msg.get("status") == "ok":
                        total = msg.get("total", 0)

                cursor += len(collection)
                if cursor >= total:
                    break

                await rate_limiter.acquire(self.source)

            except Exception as e:
                self.logger.warning("bioRxiv search page failed", cursor=cursor, error=str(e))
                break

        self.logger.info("bioRxiv search complete", found=len(all_dois))
        return all_dois

    async def fetch(self, paper_ids: list[str]) -> list[dict[str, Any]]:
        """
        Fetch full metadata for given DOIs.

        For bioRxiv, we use the /pubs endpoint with DOI.

        Args:
            paper_ids: List of DOIs

        Returns:
            List of paper metadata dictionaries
        """
        if not paper_ids:
            return []

        papers = []

        for doi in paper_ids:
            await rate_limiter.acquire(self.source)

            try:
                # bioRxiv pubs endpoint: /pubs/{server}/{doi}
                url = f"https://api.biorxiv.org/pubs/{self.server}/{doi}"

                response = await self._request("GET", url)
                data = response.json()

                collection = data.get("collection", [])
                if collection:
                    papers.append(collection[0])

            except Exception as e:
                self.logger.warning("Failed to fetch DOI", doi=doi, error=str(e))
                continue

        self.logger.debug("Fetched papers", count=len(papers))
        return papers

    def parse(self, raw_data: dict[str, Any]) -> Paper:
        """
        Parse bioRxiv JSON into standardized Paper format.

        Args:
            raw_data: Dictionary of paper metadata

        Returns:
            Parsed Paper object
        """
        try:
            doi = raw_data.get("doi", "")
            biorxiv_doi = raw_data.get("biorxiv_doi") or doi

            # Parse authors (comes as semicolon-separated string)
            authors = self._parse_authors(raw_data.get("authors", ""))

            # Parse date
            date_str = raw_data.get("date")
            pub_date = None
            if date_str:
                try:
                    pub_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

            # Category
            category = raw_data.get("category", "")
            categories = [category] if category else []

            # Published DOI (if accepted to a journal)
            published_doi = raw_data.get("published_doi")

            return Paper(
                id=biorxiv_doi,
                doi=published_doi or doi,
                source=Source.BIORXIV if self.server == "biorxiv" else Source.MEDRXIV,
                title=raw_data.get("title", ""),
                abstract=raw_data.get("abstract", ""),
                authors=authors,
                categories=categories,
                publication_date=pub_date,
                year=pub_date.year if pub_date else None,
                paper_type=PaperType.PREPRINT,
                journal=raw_data.get("published_journal"),
                url=f"https://www.{self.server}.org/content/{biorxiv_doi}",
                pdf_url=f"https://www.{self.server}.org/content/{biorxiv_doi}.full.pdf",
                raw_data={
                    "server": self.server,
                    "version": raw_data.get("version"),
                    "type": raw_data.get("type"),
                    "license": raw_data.get("license"),
                },
            )

        except Exception as e:
            raise ParserError(f"Failed to parse bioRxiv paper: {e}") from e

    def _parse_authors(self, authors_str: str) -> list[Author]:
        """Parse semicolon-separated author string."""
        if not authors_str:
            return []

        authors = []
        for name in authors_str.split(";"):
            name = name.strip()
            if name:
                authors.append(Author(name=name))

        return authors


class MedrxivCrawler(BiorxivCrawler):
    """Crawler specifically for medRxiv preprint server."""

    source = Source.MEDRXIV

    def __init__(self) -> None:
        super().__init__(server="medrxiv")
