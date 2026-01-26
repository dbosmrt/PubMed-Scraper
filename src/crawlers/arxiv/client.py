"""
PubMed Scraper - arXiv API Client

Implements the arXiv crawler using the arXiv API (Atom feed).
Supports search with category and date filters.

API Documentation: https://arxiv.org/help/api/
"""

from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET

from src.crawlers.base import Author, BaseCrawler, FilterParams, Paper, rate_limiter
from src.shared.config import settings
from src.shared.constants import ARXIV_BATCH_SIZE, PaperType, Source
from src.shared.exceptions import ParserError


# Atom namespace
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}
ARXIV_NS = {"arxiv": "http://arxiv.org/schemas/atom"}


class ArxivCrawler(BaseCrawler[ET.Element]):
    """
    Crawler for arXiv using the Atom-based API.

    arXiv API returns results in Atom format.
    Rate limit: 1 request per 3 seconds (we use 1/sec with bursting).
    """

    source = Source.ARXIV
    batch_size = ARXIV_BATCH_SIZE

    def __init__(self) -> None:
        super().__init__(timeout=60.0)  # arXiv can be slow
        self.base_url = settings.external_api.arxiv_base_url

    async def search(
        self,
        query: str,
        filters: FilterParams | None = None,
    ) -> list[str]:
        """
        Search arXiv for papers matching the query.

        Args:
            query: arXiv search query (supports field prefixes like ti:, au:, abs:)
            filters: Optional filters

        Returns:
            List of arXiv IDs
        """
        await rate_limiter.acquire(self.source)

        # Build query with filters
        full_query = self._build_query(query, filters)
        max_results = filters.max_results if filters else 1000

        params = {
            "search_query": full_query,
            "start": "0",
            "max_results": str(max_results),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        self.logger.info("Searching arXiv", query=full_query, max_results=max_results)

        response = await self._request("GET", self.base_url, params=params)

        # Parse Atom feed
        root = ET.fromstring(response.text)
        entries = root.findall("atom:entry", ATOM_NS)

        arxiv_ids = []
        for entry in entries:
            id_elem = entry.find("atom:id", ATOM_NS)
            if id_elem is not None and id_elem.text:
                # Extract arXiv ID from URL (e.g., http://arxiv.org/abs/2401.12345v1)
                arxiv_id = id_elem.text.split("/abs/")[-1]
                arxiv_ids.append(arxiv_id)

        self.logger.info("arXiv search complete", found=len(arxiv_ids))
        return arxiv_ids

    def _build_query(self, query: str, filters: FilterParams | None) -> str:
        """Build arXiv query string with filters."""
        parts = [query]

        if filters:
            # Category filter (e.g., cs.AI, q-bio.BM)
            if filters.categories if hasattr(filters, "categories") else None:
                cat_query = " OR ".join(f"cat:{cat}" for cat in filters.categories)
                parts.append(f"({cat_query})")

        return " AND ".join(parts)

    async def fetch(self, paper_ids: list[str]) -> list[ET.Element]:
        """
        Fetch full metadata for given arXiv IDs.

        For arXiv, we use id_list parameter to fetch specific papers.

        Args:
            paper_ids: List of arXiv IDs

        Returns:
            List of Atom entry elements
        """
        if not paper_ids:
            return []

        await rate_limiter.acquire(self.source)

        # arXiv uses comma-separated ID list
        params = {
            "id_list": ",".join(paper_ids),
            "max_results": str(len(paper_ids)),
        }

        self.logger.debug("Fetching arXiv papers", count=len(paper_ids))

        response = await self._request("GET", self.base_url, params=params)

        root = ET.fromstring(response.text)
        entries = root.findall("atom:entry", ATOM_NS)

        self.logger.debug("Fetched papers", count=len(entries))
        return entries

    def parse(self, raw_data: ET.Element) -> Paper:
        """
        Parse arXiv Atom entry into standardized Paper format.

        Args:
            raw_data: XML Element for a single Atom entry

        Returns:
            Parsed Paper object
        """
        try:
            # Extract arXiv ID
            id_elem = raw_data.find("atom:id", ATOM_NS)
            arxiv_url = id_elem.text if id_elem is not None else ""
            arxiv_id = arxiv_url.split("/abs/")[-1] if arxiv_url else ""

            # Title
            title_elem = raw_data.find("atom:title", ATOM_NS)
            title = title_elem.text.strip().replace("\n", " ") if title_elem is not None else ""

            # Abstract (called 'summary' in Atom)
            abstract_elem = raw_data.find("atom:summary", ATOM_NS)
            abstract = abstract_elem.text.strip() if abstract_elem is not None else ""

            # Authors
            authors = self._parse_authors(raw_data)

            # Categories
            categories = []
            for cat in raw_data.findall("arxiv:primary_category", ARXIV_NS):
                term = cat.get("term")
                if term:
                    categories.append(term)
            for cat in raw_data.findall("atom:category", ATOM_NS):
                term = cat.get("term")
                if term and term not in categories:
                    categories.append(term)

            # Publication date
            published_elem = raw_data.find("atom:published", ATOM_NS)
            pub_date = self._parse_date(published_elem.text if published_elem is not None else None)

            # DOI (if available)
            doi = None
            for link in raw_data.findall("atom:link", ATOM_NS):
                if link.get("title") == "doi":
                    href = link.get("href", "")
                    if "doi.org" in href:
                        doi = href.split("doi.org/")[-1]

            # PDF URL
            pdf_url = None
            for link in raw_data.findall("atom:link", ATOM_NS):
                if link.get("type") == "application/pdf":
                    pdf_url = link.get("href")
                elif link.get("title") == "pdf":
                    pdf_url = link.get("href")

            # arXiv comment (often contains page count, conference info)
            comment_elem = raw_data.find("arxiv:comment", ARXIV_NS)
            comment = comment_elem.text if comment_elem is not None else ""

            # Journal reference (if published)
            journal_ref_elem = raw_data.find("arxiv:journal_ref", ARXIV_NS)
            journal = journal_ref_elem.text if journal_ref_elem is not None else None

            return Paper(
                id=arxiv_id,
                doi=doi,
                source=self.source,
                title=title,
                abstract=abstract,
                authors=authors,
                categories=categories,
                publication_date=pub_date,
                year=pub_date.year if pub_date else None,
                paper_type=PaperType.PREPRINT,  # All arXiv papers are preprints
                journal=journal,
                url=arxiv_url,
                pdf_url=pdf_url,
                raw_data={"arxiv_id": arxiv_id, "comment": comment},
            )

        except Exception as e:
            raise ParserError(f"Failed to parse arXiv entry: {e}") from e

    def _parse_authors(self, entry: ET.Element) -> list[Author]:
        """Parse author list from Atom entry."""
        authors = []

        for author_elem in entry.findall("atom:author", ATOM_NS):
            name_elem = author_elem.find("atom:name", ATOM_NS)
            name = name_elem.text if name_elem is not None else ""

            affiliation_elem = author_elem.find("arxiv:affiliation", ARXIV_NS)
            affiliation = affiliation_elem.text if affiliation_elem is not None else None

            if name:
                authors.append(
                    Author(
                        name=name,
                        affiliation=affiliation,
                    )
                )

        return authors

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse ISO 8601 date string."""
        if not date_str:
            return None

        try:
            # Format: 2024-01-15T12:00:00Z
            return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, TypeError):
            return None
