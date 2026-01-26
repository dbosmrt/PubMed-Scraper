"""
PubMed Scraper - API Gateway

FastAPI-based REST API for the PubMed Scraper.
Provides endpoints for scraping, job management, and exports.
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.crawlers import CrawlerFactory, FilterParams
from src.export import ExportManager
from src.gateway.schemas import (
    ErrorResponse,
    ExportRequest,
    ExportResponse,
    HealthResponse,
    JobResponse,
    JobStatusResponse,
    ScrapeRequest,
)
from src.processors import PaperClassifier
from src.shared.config import settings
from src.shared.constants import ExportFormat, JobStatus, Source
from src.shared.logging import get_logger

logger = get_logger(__name__)

# In-memory job storage (replace with Redis/MongoDB in production)
jobs: dict[str, dict[str, Any]] = {}
papers_cache: dict[str, list] = {}

# Startup time for uptime calculation
start_time = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting PubMed Scraper API", version="1.0.0")
    yield
    logger.info("Shutting down PubMed Scraper API")


# Create FastAPI app
app = FastAPI(
    title="PubMed Scraper API",
    description="Distributed multi-source research paper scraper",
    version="1.0.0",
    lifespan=lifespan,
    responses={
        500: {"model": ErrorResponse},
    },
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        uptime_seconds=time.time() - start_time,
        services={
            "api": True,
            "database": True,  # TODO: Check actual DB connection
            "redis": True,  # TODO: Check actual Redis connection
        },
    )


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint."""
    return {
        "name": "PubMed Scraper API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# -----------------------------------------------------------------------------
# Scraping Endpoints
# -----------------------------------------------------------------------------


@app.post(
    "/scrape",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Scraping"],
)
async def start_scrape(request: ScrapeRequest) -> JobResponse:
    """
    Start a new scraping job.

    The job runs asynchronously. Use /jobs/{job_id} to check status.
    """
    job_id = str(uuid4())

    jobs[job_id] = {
        "status": JobStatus.PENDING,
        "progress": 0,
        "papers_found": 0,
        "papers_processed": 0,
        "errors": [],
        "request": request.model_dump(),
        "created_at": datetime.now(),
        "started_at": None,
        "completed_at": None,
    }

    logger.info("Scrape job created", job_id=job_id, query=request.query)

    # In production, this would dispatch to Celery worker
    # For now, run synchronously in background
    import asyncio

    asyncio.create_task(_run_scrape_job(job_id, request))

    return JobResponse(
        job_id=job_id,
        status=JobStatus.PENDING,
        message="Scraping job created. Use /jobs/{job_id} to check status.",
        created_at=jobs[job_id]["created_at"],
    )


async def _run_scrape_job(job_id: str, request: ScrapeRequest) -> None:
    """Run scraping job (background task)."""
    job = jobs[job_id]
    job["status"] = JobStatus.RUNNING
    job["started_at"] = datetime.now()

    all_papers = []
    classifier = PaperClassifier()

    try:
        filters = FilterParams(
            year_start=request.year_start,
            year_end=request.year_end,
            countries=request.countries,
            paper_types=request.paper_types,
            exclude_preprints=request.exclude_preprints,
            max_results=request.max_results,
        )

        for source in request.sources:
            try:
                crawler = CrawlerFactory.get(source)
                async with crawler:
                    async for paper in crawler.crawl(request.query, filters):
                        # Classify paper
                        paper.paper_type = classifier.classify(paper)
                        all_papers.append(paper)
                        job["papers_found"] = len(all_papers)
                        job["papers_processed"] = len(all_papers)

            except Exception as e:
                logger.error("Crawler error", source=str(source), error=str(e))
                job["errors"].append(f"{source}: {str(e)}")

        # Store papers
        papers_cache[job_id] = all_papers

        # Export results
        if all_papers and request.export_formats:
            export_manager = ExportManager(output_dir=f"output/{job_id}")
            export_manager.export_all(
                all_papers,
                f"papers_{job_id[:8]}",
                request.export_formats,
            )

        job["status"] = JobStatus.COMPLETED if not job["errors"] else JobStatus.PARTIAL
        job["completed_at"] = datetime.now()
        job["progress"] = 100

        logger.info(
            "Scrape job completed",
            job_id=job_id,
            papers=len(all_papers),
            errors=len(job["errors"]),
        )

    except Exception as e:
        logger.exception("Job failed", job_id=job_id)
        job["status"] = JobStatus.FAILED
        job["errors"].append(str(e))
        job["completed_at"] = datetime.now()


# -----------------------------------------------------------------------------
# Job Management
# -----------------------------------------------------------------------------


@app.get("/jobs/{job_id}", response_model=JobStatusResponse, tags=["Jobs"])
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get status of a scraping job."""
    if job_id not in jobs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job not found: {job_id}",
        )

    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        papers_found=job["papers_found"],
        papers_processed=job["papers_processed"],
        errors=job["errors"],
        started_at=job["started_at"],
        completed_at=job["completed_at"],
    )


@app.get("/jobs", tags=["Jobs"])
async def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    status_filter: JobStatus | None = None,
):
    """List all jobs."""
    result = []
    for job_id, job in list(jobs.items())[-limit:]:
        if status_filter and job["status"] != status_filter:
            continue
        result.append({
            "job_id": job_id,
            "status": job["status"],
            "created_at": job["created_at"],
            "papers_found": job["papers_found"],
        })
    return {"jobs": result, "total": len(result)}


@app.delete("/jobs/{job_id}", tags=["Jobs"])
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    job = jobs[job_id]
    if job["status"] in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
        raise HTTPException(status_code=400, detail="Job already finished")

    job["status"] = JobStatus.CANCELLED
    job["completed_at"] = datetime.now()

    return {"message": f"Job {job_id} cancelled"}


# -----------------------------------------------------------------------------
# Export Endpoints
# -----------------------------------------------------------------------------


@app.post("/export", response_model=ExportResponse, tags=["Export"])
async def export_results(request: ExportRequest) -> ExportResponse:
    """Export job results to specified formats."""
    if request.job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    if request.job_id not in papers_cache:
        raise HTTPException(status_code=400, detail="No papers available for export")

    papers = papers_cache[request.job_id]
    export_manager = ExportManager(output_dir=f"output/{request.job_id}")

    files = {}
    for fmt in request.formats:
        path = export_manager.export(papers, f"export_{request.job_id[:8]}", fmt)
        files[str(fmt)] = str(path)

    return ExportResponse(
        job_id=request.job_id,
        files=files,
        total_papers=len(papers),
    )


@app.get("/export/{job_id}/download/{format}", tags=["Export"])
async def download_export(job_id: str, format: ExportFormat):
    """Download exported file."""
    from pathlib import Path

    output_dir = Path(f"output/{job_id}")
    ext = {
        ExportFormat.CSV: ".csv",
        ExportFormat.PARQUET: ".parquet",
        ExportFormat.JSON: ".json",
        ExportFormat.TXT: ".txt",
    }.get(format, ".csv")

    # Find file
    files = list(output_dir.glob(f"*{ext}"))
    if not files:
        raise HTTPException(status_code=404, detail=f"Export file not found for format: {format}")

    return FileResponse(
        files[0],
        filename=files[0].name,
        media_type="application/octet-stream",
    )


# -----------------------------------------------------------------------------
# Source Information
# -----------------------------------------------------------------------------


@app.get("/sources", tags=["Info"])
async def list_sources():
    """List available data sources."""
    return {
        "sources": [
            {
                "id": str(s),
                "name": s.name,
                "description": f"{s.name} data source",
            }
            for s in Source
        ]
    }


@app.get("/formats", tags=["Info"])
async def list_formats():
    """List available export formats."""
    return {
        "formats": [
            {"id": str(f), "name": f.name, "extension": f".{f.value}"}
            for f in ExportFormat
        ]
    }


# Entry point for running with uvicorn
def run():
    """Run the API server."""
    import uvicorn

    uvicorn.run(
        "src.gateway.main:app",
        host=settings.app.api_host,
        port=settings.app.api_port,
        reload=settings.app.api_reload,
    )


if __name__ == "__main__":
    run()
