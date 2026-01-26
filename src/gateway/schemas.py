"""
PubMed Scraper - API Request/Response Schemas

Pydantic models for API request validation and response serialization.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from src.shared.constants import ExportFormat, JobStatus, PaperType, Source


# -----------------------------------------------------------------------------
# Request Schemas
# -----------------------------------------------------------------------------


class ScrapeRequest(BaseModel):
    """Request to start a scraping job."""

    query: str = Field(..., description="Search query string", min_length=1, max_length=1000)
    sources: list[Source] = Field(
        default=[Source.PUBMED],
        description="Data sources to scrape",
    )
    max_results: int = Field(
        default=100,
        ge=1,
        le=10000,
        description="Maximum papers to retrieve per source",
    )
    year_start: int | None = Field(default=None, ge=1900, le=2100, description="Start year filter")
    year_end: int | None = Field(default=None, ge=1900, le=2100, description="End year filter")
    countries: list[str] = Field(default=[], description="ISO country codes to filter by")
    paper_types: list[PaperType] = Field(default=[], description="Paper types to include")
    exclude_preprints: bool = Field(default=False, description="Exclude preprints")
    export_formats: list[ExportFormat] = Field(
        default=[ExportFormat.CSV],
        description="Export formats",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "cancer biomarkers",
                "sources": ["pubmed", "arxiv"],
                "max_results": 500,
                "year_start": 2020,
                "year_end": 2024,
                "countries": ["USA", "GBR"],
                "paper_types": ["research_article", "review"],
                "export_formats": ["csv", "parquet"],
            }
        }


class ExportRequest(BaseModel):
    """Request to export job results."""

    job_id: str = Field(..., description="Job ID to export")
    formats: list[ExportFormat] = Field(
        default=[ExportFormat.CSV],
        description="Export formats",
    )


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------


class AuthorSchema(BaseModel):
    """Author information."""

    name: str
    affiliation: str | None = None
    country: str | None = None


class PaperSchema(BaseModel):
    """Paper metadata."""

    id: str
    doi: str | None = None
    source: Source
    title: str
    abstract: str
    authors: list[AuthorSchema]
    keywords: list[str]
    journal: str | None = None
    publication_date: date | None = None
    year: int | None = None
    paper_type: PaperType
    url: str | None = None
    pdf_url: str | None = None
    countries: list[str]


class JobResponse(BaseModel):
    """Response after creating a scraping job."""

    job_id: str
    status: JobStatus
    message: str
    created_at: datetime


class JobStatusResponse(BaseModel):
    """Response for job status query."""

    job_id: str
    status: JobStatus
    progress: float = Field(ge=0, le=100, description="Progress percentage")
    papers_found: int = 0
    papers_processed: int = 0
    errors: list[str] = []
    started_at: datetime | None = None
    completed_at: datetime | None = None


class ExportResponse(BaseModel):
    """Response after exporting results."""

    job_id: str
    files: dict[str, str] = Field(description="Mapping of format to file path")
    total_papers: int


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime_seconds: float
    services: dict[str, bool]


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    message: str
    details: dict[str, Any] = {}
