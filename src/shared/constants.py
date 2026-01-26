"""
PubMed Scraper - Constants and Enumerations

Defines all constants, enums, and type definitions used across the application.
"""

from enum import Enum, auto


class Source(str, Enum):
    """Supported data sources for paper scraping."""

    PUBMED = "pubmed"
    ARXIV = "arxiv"
    BIORXIV = "biorxiv"
    MEDRXIV = "medrxiv"

    def __str__(self) -> str:
        return self.value


class PaperType(str, Enum):
    """Classification of research paper types."""

    RESEARCH_ARTICLE = "research_article"
    REVIEW = "review"
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    CASE_REPORT = "case_report"
    CASE_SERIES = "case_series"
    CLINICAL_TRIAL = "clinical_trial"
    RANDOMIZED_CONTROLLED_TRIAL = "randomized_controlled_trial"
    OBSERVATIONAL_STUDY = "observational_study"
    COHORT_STUDY = "cohort_study"
    EDITORIAL = "editorial"
    LETTER = "letter"
    COMMENTARY = "commentary"
    PREPRINT = "preprint"
    CONFERENCE_PAPER = "conference_paper"
    BOOK_CHAPTER = "book_chapter"
    THESIS = "thesis"
    UNKNOWN = "unknown"

    def __str__(self) -> str:
        return self.value


class ExportFormat(str, Enum):
    """Supported export file formats."""

    CSV = "csv"
    PARQUET = "parquet"
    JSON = "json"
    TXT = "txt"
    PDF = "pdf"
    EXCEL = "xlsx"

    def __str__(self) -> str:
        return self.value


class JobStatus(str, Enum):
    """Status of a scraping job."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Completed with some errors

    def __str__(self) -> str:
        return self.value


class TaskPriority(int, Enum):
    """Task priority levels for the queue."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


# -----------------------------------------------------------------------------
# API Rate Limits (requests per second)
# -----------------------------------------------------------------------------
DEFAULT_RATE_LIMITS = {
    Source.PUBMED: 3,  # NCBI allows 3/sec with API key, 1/sec without
    Source.ARXIV: 1,  # arXiv recommends 1 request per 3 seconds
    Source.BIORXIV: 2,
    Source.MEDRXIV: 2,
}

# -----------------------------------------------------------------------------
# Batch Sizes
# -----------------------------------------------------------------------------
PUBMED_BATCH_SIZE = 200  # Max PMIDs per efetch request
ARXIV_BATCH_SIZE = 100
BIORXIV_BATCH_SIZE = 100
DEFAULT_PAGE_SIZE = 50

# -----------------------------------------------------------------------------
# Retry Configuration
# -----------------------------------------------------------------------------
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 2
INITIAL_RETRY_DELAY = 1  # seconds

# -----------------------------------------------------------------------------
# HTTP Headers
# -----------------------------------------------------------------------------
DEFAULT_USER_AGENT = (
    "PubMed-Scraper/1.0 (Research Paper Collection Tool; "
    "https://github.com/example/pubmed-scraper)"
)

# -----------------------------------------------------------------------------
# Country Code Mapping (ISO 3166-1 alpha-3)
# -----------------------------------------------------------------------------
COMMON_COUNTRY_ALIASES = {
    "usa": "USA",
    "united states": "USA",
    "u.s.a.": "USA",
    "uk": "GBR",
    "united kingdom": "GBR",
    "england": "GBR",
    "germany": "DEU",
    "deutschland": "DEU",
    "china": "CHN",
    "prc": "CHN",
    "japan": "JPN",
    "india": "IND",
    "france": "FRA",
    "italy": "ITA",
    "spain": "ESP",
    "canada": "CAN",
    "australia": "AUS",
    "brazil": "BRA",
    "south korea": "KOR",
    "korea": "KOR",
    "netherlands": "NLD",
    "sweden": "SWE",
    "switzerland": "CHE",
}
