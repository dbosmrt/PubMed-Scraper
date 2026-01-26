"""
PubMed Scraper - PubMed E-utilities Client

Implements the PubMed crawler using NCBI E-utilities API.
Supports esearch (search) and efetch (retrieve) operations.

API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25499/
"""

from datetime import datetime
from typing import Any
from xml.etree import ElementTree as ET

from src.crawlers.base import Author, BaseCrawler, FilterParams, Paper, rate_limiter
from src.shared.config import settings
from src.shared.constants import PUBMED_BATCH_SIZE, PaperType, Source
from src.shared.exceptions import ParserError


class PubMedCrawler(BaseCrawler[ET.Element]):
    """
    Crawler for PubMed using NCBI E-utilities API.

    Implements:
    - esearch: Search for PMIDs matching a query
    - efetch: Retrieve full article metadata in XML format
    """

    source = Source.PUBMED
    batch_size = PUBMED_BATCH_SIZE

    def __init__(self) -> None:
        super().__init__()
        self.base_url = settings.external_api.pubmed_base_url
        self.api_key = settings.external_api.pubmed_api_key
        self.email = settings.external_api.ncbi_email

    def _get_base_params(self) -> dict[str, str]:
        """Get common parameters for all E-utilities requests."""
        params = {
            "email": self.email,
            "tool": "pubmed-scraper",
        }
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    async def search(
        self,
        query: str,
        filters: FilterParams | None = None,
    ) -> list[str]:
        """
        Search PubMed for articles matching the query.

        Args:
            query: PubMed search query (supports boolean operators)
            filters: Optional filters for year range, etc.

        Returns:
            List of PMIDs
        """
        await rate_limiter.acquire(self.source)

        # Build query with filters
        full_query = self._build_query(query, filters)
        max_results = filters.max_results if filters else 1000

        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "term": full_query,
            "retmax": str(max_results),
            "retmode": "json",
            "usehistory": "y",
        }

        self.logger.info("Searching PubMed", query=full_query, max_results=max_results)

        response = await self._request(
            "GET",
            f"{self.base_url}/esearch.fcgi",
            params=params,
        )

        data = response.json()
        result = data.get("esearchresult", {})
        pmids = result.get("idlist", [])

        self.logger.info("PubMed search complete", found=len(pmids))
        return pmids

    def _build_query(self, query: str, filters: FilterParams | None) -> str:
        """Build PubMed query string with filters."""
        parts = [query]

        if filters:
            # Year range filter
            if filters.year_start and filters.year_end:
                parts.append(f"({filters.year_start}:{filters.year_end}[pdat])")
            elif filters.year_start:
                parts.append(f"{filters.year_start}:3000[pdat]")
            elif filters.year_end:
                parts.append(f"1900:{filters.year_end}[pdat]")

            # Language filter
            if filters.languages:
                lang_query = " OR ".join(f"{lang}[la]" for lang in filters.languages)
                parts.append(f"({lang_query})")

            # Paper type filter
            if filters.paper_types:
                type_map = {
                    PaperType.REVIEW: "review[pt]",
                    PaperType.CLINICAL_TRIAL: "clinical trial[pt]",
                    PaperType.META_ANALYSIS: "meta-analysis[pt]",
                    PaperType.RANDOMIZED_CONTROLLED_TRIAL: "randomized controlled trial[pt]",
                    PaperType.CASE_REPORT: "case reports[pt]",
                }
                type_queries = [
                    type_map.get(pt, "") for pt in filters.paper_types if pt in type_map
                ]
                if type_queries:
                    parts.append(f"({' OR '.join(type_queries)})")

        return " AND ".join(parts)

    async def fetch(self, paper_ids: list[str]) -> list[ET.Element]:
        """
        Fetch full metadata for given PMIDs.

        Args:
            paper_ids: List of PubMed IDs

        Returns:
            List of XML Element objects for each article
        """
        if not paper_ids:
            return []

        await rate_limiter.acquire(self.source)

        params = {
            **self._get_base_params(),
            "db": "pubmed",
            "id": ",".join(paper_ids),
            "rettype": "xml",
            "retmode": "xml",
        }

        self.logger.debug("Fetching PubMed articles", count=len(paper_ids))

        response = await self._request(
            "GET",
            f"{self.base_url}/efetch.fcgi",
            params=params,
        )

        # Parse XML response
        root = ET.fromstring(response.text)
        articles = root.findall(".//PubmedArticle")

        self.logger.debug("Fetched articles", count=len(articles))
        return articles

    def parse(self, raw_data: ET.Element) -> Paper:
        """
        Parse PubMed XML into standardized Paper format.

        Args:
            raw_data: XML Element for a single PubmedArticle

        Returns:
            Parsed Paper object
        """
        try:
            medline = raw_data.find(".//MedlineCitation")
            article = medline.find(".//Article")
            pmid = medline.findtext(".//PMID", "")

            # Parse basic metadata
            title = self._get_text(article, ".//ArticleTitle")
            abstract = self._parse_abstract(article)

            # Parse authors
            authors = self._parse_authors(article)

            # Parse publication info
            journal_info = self._parse_journal_info(article)
            pub_date = self._parse_date(article)

            # Parse identifiers
            doi = self._get_article_id(raw_data, "doi")
            pmc_id = self._get_article_id(raw_data, "pmc")

            # Parse keywords and MeSH terms
            keywords = self._parse_keywords(medline)
            mesh_terms = self._parse_mesh_terms(medline)

            # Determine paper type
            paper_type = self._classify_paper_type(medline)

            # Extract countries from affiliations
            countries = list(set(a.country for a in authors if a.country))

            return Paper(
                id=pmid,
                doi=doi,
                source=self.source,
                title=title,
                abstract=abstract,
                authors=authors,
                keywords=keywords,
                mesh_terms=mesh_terms,
                journal=journal_info.get("journal"),
                volume=journal_info.get("volume"),
                issue=journal_info.get("issue"),
                pages=journal_info.get("pages"),
                publication_date=pub_date,
                year=pub_date.year if pub_date else None,
                paper_type=paper_type,
                url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                pmc_id=pmc_id,
                pdf_url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/" if pmc_id else None,
                countries=countries,
                raw_data={"pmid": pmid},
            )

        except Exception as e:
            raise ParserError(f"Failed to parse PubMed article: {e}") from e

    def _get_text(self, element: ET.Element | None, path: str, default: str = "") -> str:
        """Safely get text content from an XML element."""
        if element is None:
            return default
        found = element.find(path)
        if found is not None:
            # Handle mixed content (text with embedded tags)
            return "".join(found.itertext()).strip()
        return default

    def _parse_abstract(self, article: ET.Element) -> str:
        """Parse abstract, handling structured abstracts."""
        abstract_elem = article.find(".//Abstract")
        if abstract_elem is None:
            return ""

        parts = []
        for text in abstract_elem.findall(".//AbstractText"):
            label = text.get("Label", "")
            content = "".join(text.itertext()).strip()
            if label:
                parts.append(f"{label}: {content}")
            else:
                parts.append(content)

        return "\n\n".join(parts)

    def _parse_authors(self, article: ET.Element) -> list[Author]:
        """Parse author list with affiliations."""
        authors = []
        author_list = article.find(".//AuthorList")

        if author_list is None:
            return authors

        for author_elem in author_list.findall(".//Author"):
            last_name = self._get_text(author_elem, "LastName")
            fore_name = self._get_text(author_elem, "ForeName")

            if not last_name:
                # Might be a collective name
                collective = self._get_text(author_elem, "CollectiveName")
                if collective:
                    authors.append(Author(name=collective))
                continue

            name = f"{fore_name} {last_name}".strip()

            # Get affiliation
            affiliation = self._get_text(author_elem, ".//Affiliation")
            country = self._extract_country_from_affiliation(affiliation)

            authors.append(
                Author(
                    name=name,
                    affiliation=affiliation,
                    country=country,
                )
            )

        return authors

    def _extract_country_from_affiliation(self, affiliation: str) -> str | None:
        """Extract country from affiliation string."""
        if not affiliation:
            return None

        from src.shared.constants import COMMON_COUNTRY_ALIASES

        # Check for common country names at the end of affiliation
        affiliation_lower = affiliation.lower()
        for alias, code in COMMON_COUNTRY_ALIASES.items():
            if alias in affiliation_lower:
                return code

        return None

    def _parse_journal_info(self, article: ET.Element) -> dict[str, str | None]:
        """Parse journal metadata."""
        journal = article.find(".//Journal")
        journal_issue = journal.find(".//JournalIssue") if journal else None

        return {
            "journal": self._get_text(journal, ".//Title") if journal else None,
            "volume": self._get_text(journal_issue, "Volume") if journal_issue else None,
            "issue": self._get_text(journal_issue, "Issue") if journal_issue else None,
            "pages": self._get_text(article, ".//MedlinePgn"),
        }

    def _parse_date(self, article: ET.Element) -> datetime | None:
        """Parse publication date."""
        # Try ArticleDate first (electronic publication)
        article_date = article.find(".//ArticleDate")
        if article_date is not None:
            year = self._get_text(article_date, "Year")
            month = self._get_text(article_date, "Month") or "1"
            day = self._get_text(article_date, "Day") or "1"
            try:
                return datetime(int(year), int(month), int(day)).date()
            except (ValueError, TypeError):
                pass

        # Fall back to PubDate
        pub_date = article.find(".//Journal/JournalIssue/PubDate")
        if pub_date is not None:
            year = self._get_text(pub_date, "Year")
            if year:
                month = self._get_text(pub_date, "Month") or "Jan"
                try:
                    # Handle text months
                    month_num = datetime.strptime(month[:3], "%b").month if month.isalpha() else int(month)
                    return datetime(int(year), month_num, 1).date()
                except (ValueError, TypeError):
                    return datetime(int(year), 1, 1).date()

        return None

    def _get_article_id(self, article: ET.Element, id_type: str) -> str | None:
        """Get article ID of specified type (doi, pmc, etc.)."""
        article_ids = article.find(".//PubmedData/ArticleIdList")
        if article_ids is None:
            return None

        for aid in article_ids.findall("ArticleId"):
            if aid.get("IdType") == id_type:
                return aid.text

        return None

    def _parse_keywords(self, medline: ET.Element) -> list[str]:
        """Parse keyword list."""
        keywords = []
        keyword_list = medline.find(".//KeywordList")

        if keyword_list is not None:
            for kw in keyword_list.findall("Keyword"):
                if kw.text:
                    keywords.append(kw.text.strip())

        return keywords

    def _parse_mesh_terms(self, medline: ET.Element) -> list[str]:
        """Parse MeSH heading list."""
        mesh_terms = []
        mesh_list = medline.find(".//MeshHeadingList")

        if mesh_list is not None:
            for heading in mesh_list.findall(".//DescriptorName"):
                if heading.text:
                    mesh_terms.append(heading.text.strip())

        return mesh_terms

    def _classify_paper_type(self, medline: ET.Element) -> PaperType:
        """Classify paper type from PublicationTypeList."""
        pub_types = medline.find(".//PublicationTypeList")

        if pub_types is None:
            return PaperType.UNKNOWN

        pub_type_map = {
            "Review": PaperType.REVIEW,
            "Systematic Review": PaperType.SYSTEMATIC_REVIEW,
            "Meta-Analysis": PaperType.META_ANALYSIS,
            "Clinical Trial": PaperType.CLINICAL_TRIAL,
            "Randomized Controlled Trial": PaperType.RANDOMIZED_CONTROLLED_TRIAL,
            "Observational Study": PaperType.OBSERVATIONAL_STUDY,
            "Case Reports": PaperType.CASE_REPORT,
            "Editorial": PaperType.EDITORIAL,
            "Letter": PaperType.LETTER,
            "Comment": PaperType.COMMENTARY,
        }

        for pt in pub_types.findall("PublicationType"):
            if pt.text in pub_type_map:
                return pub_type_map[pt.text]

        # Default to research article if Journal Article
        for pt in pub_types.findall("PublicationType"):
            if pt.text == "Journal Article":
                return PaperType.RESEARCH_ARTICLE

        return PaperType.UNKNOWN
