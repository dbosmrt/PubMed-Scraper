"""
PubMed Scraper - Custom Exceptions

Defines the exception hierarchy for the application.
All exceptions inherit from BaseScraperError for unified error handling.
"""

from typing import Any


class BaseScraperError(Exception):
    """Base exception for all scraper errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# -----------------------------------------------------------------------------
# Crawler Exceptions
# -----------------------------------------------------------------------------


class CrawlerError(BaseScraperError):
    """Base exception for crawler-related errors."""


class RateLimitError(CrawlerError):
    """Raised when rate limit is exceeded for an API."""

    def __init__(
        self,
        source: str,
        retry_after: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            f"Rate limit exceeded for {source}",
            details={"source": source, "retry_after": retry_after},
            **kwargs,
        )
        self.source = source
        self.retry_after = retry_after


class SourceUnavailableError(CrawlerError):
    """Raised when a data source is temporarily unavailable."""

    def __init__(self, source: str, status_code: int | None = None, **kwargs: Any) -> None:
        super().__init__(
            f"Source {source} is unavailable",
            details={"source": source, "status_code": status_code},
            **kwargs,
        )


class InvalidQueryError(CrawlerError):
    """Raised when a search query is malformed."""


# -----------------------------------------------------------------------------
# Parser Exceptions
# -----------------------------------------------------------------------------


class ParserError(BaseScraperError):
    """Base exception for parsing-related errors."""


class XMLParseError(ParserError):
    """Raised when XML parsing fails."""


class JSONParseError(ParserError):
    """Raised when JSON parsing fails."""


class MissingFieldError(ParserError):
    """Raised when a required field is missing from parsed data."""

    def __init__(self, field: str, source: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            f"Missing required field: {field}",
            details={"field": field, "source": source},
            **kwargs,
        )


# -----------------------------------------------------------------------------
# Storage Exceptions
# -----------------------------------------------------------------------------


class StorageError(BaseScraperError):
    """Base exception for storage-related errors."""


class DatabaseConnectionError(StorageError):
    """Raised when database connection fails."""


class FileStorageError(StorageError):
    """Raised when file storage operation fails."""


class DuplicateEntryError(StorageError):
    """Raised when attempting to insert a duplicate record."""

    def __init__(self, identifier: str, **kwargs: Any) -> None:
        super().__init__(
            f"Duplicate entry: {identifier}",
            details={"identifier": identifier},
            **kwargs,
        )


# -----------------------------------------------------------------------------
# Export Exceptions
# -----------------------------------------------------------------------------


class ExportError(BaseScraperError):
    """Base exception for export-related errors."""


class UnsupportedFormatError(ExportError):
    """Raised when an unsupported export format is requested."""

    def __init__(self, format: str, supported: list[str], **kwargs: Any) -> None:
        super().__init__(
            f"Unsupported format: {format}. Supported: {', '.join(supported)}",
            details={"format": format, "supported": supported},
            **kwargs,
        )


class ExportSizeLimitError(ExportError):
    """Raised when export exceeds size limits."""


# -----------------------------------------------------------------------------
# Orchestration Exceptions
# -----------------------------------------------------------------------------


class OrchestrationError(BaseScraperError):
    """Base exception for job orchestration errors."""


class JobNotFoundError(OrchestrationError):
    """Raised when a job cannot be found."""

    def __init__(self, job_id: str, **kwargs: Any) -> None:
        super().__init__(
            f"Job not found: {job_id}",
            details={"job_id": job_id},
            **kwargs,
        )


class JobCancelledError(OrchestrationError):
    """Raised when a job has been cancelled."""


class QueueFullError(OrchestrationError):
    """Raised when the task queue is at capacity."""


# -----------------------------------------------------------------------------
# Classification Exceptions
# -----------------------------------------------------------------------------


class ClassificationError(BaseScraperError):
    """Base exception for paper classification errors."""


class ModelNotLoadedError(ClassificationError):
    """Raised when ML model is not properly loaded."""
