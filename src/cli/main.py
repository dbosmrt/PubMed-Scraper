"""
PubMed Scraper - CLI Interface

Command-line interface using Typer for all scraper operations.
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.crawlers import CrawlerFactory, FilterParams
from src.export import ExportManager
from src.processors import PaperClassifier
from src.shared.constants import ExportFormat, PaperType, Source

app = typer.Typer(
    name="pubmed-scraper",
    help="Distributed multi-source research paper scraper",
    add_completion=False,
)
console = Console()


@app.command()
def scrape(
    query: str = typer.Argument(..., help="Search query"),
    sources: list[Source] = typer.Option(
        [Source.PUBMED],
        "--source",
        "-s",
        help="Data sources to scrape",
    ),
    max_results: int = typer.Option(100, "--max", "-m", help="Maximum results per source"),
    year_start: Optional[int] = typer.Option(None, "--from", help="Start year"),
    year_end: Optional[int] = typer.Option(None, "--to", help="End year"),
    countries: list[str] = typer.Option([], "--country", "-c", help="Filter by country (ISO codes)"),
    paper_types: list[PaperType] = typer.Option([], "--type", "-t", help="Filter by paper type"),
    output_dir: Path = typer.Option(Path("output"), "--output", "-o", help="Output directory"),
    formats: list[ExportFormat] = typer.Option(
        [ExportFormat.CSV],
        "--format",
        "-f",
        help="Export formats",
    ),
):
    """
    Scrape research papers from multiple sources.

    Example:
        pubmed-scraper scrape "cancer biomarkers" -s pubmed -s arxiv -m 500 --from 2020
    """
    console.print(f"\n[bold blue]🔍 Searching for:[/] {query}")
    console.print(f"[dim]Sources: {', '.join(str(s) for s in sources)}[/]")
    console.print(f"[dim]Max results per source: {max_results}[/]")

    if year_start or year_end:
        console.print(f"[dim]Year range: {year_start or '...'} - {year_end or '...'}[/]")
    if countries:
        console.print(f"[dim]Countries: {', '.join(countries)}[/]")

    console.print()

    # Run async scraping
    papers = asyncio.run(_scrape_async(
        query=query,
        sources=sources,
        max_results=max_results,
        year_start=year_start,
        year_end=year_end,
        countries=countries,
        paper_types=paper_types,
    ))

    if not papers:
        console.print("[yellow]No papers found matching your criteria.[/]")
        raise typer.Exit(1)

    console.print(f"\n[green]✓ Found {len(papers)} papers[/]")

    # Export
    with console.status("[bold green]Exporting results..."):
        export_manager = ExportManager(output_dir=output_dir)
        files = export_manager.export_all(papers, "papers", formats)

    console.print("\n[bold]📁 Exported files:[/]")
    for fmt, path in files.items():
        console.print(f"  • {fmt}: {path}")

    console.print()


async def _scrape_async(
    query: str,
    sources: list[Source],
    max_results: int,
    year_start: Optional[int],
    year_end: Optional[int],
    countries: list[str],
    paper_types: list[PaperType],
) -> list:
    """Async scraping implementation."""
    filters = FilterParams(
        year_start=year_start,
        year_end=year_end,
        countries=countries,
        paper_types=paper_types,
        max_results=max_results,
    )

    classifier = PaperClassifier()
    all_papers = []

    for source in sources:
        console.print(f"[cyan]→ Fetching from {source}...[/]")
        try:
            crawler = CrawlerFactory.get(source)
            async with crawler:
                async for paper in crawler.crawl(query, filters):
                    paper.paper_type = classifier.classify(paper)
                    all_papers.append(paper)

                    if len(all_papers) % 50 == 0:
                        console.print(f"  [dim]Collected {len(all_papers)} papers...[/]")

        except Exception as e:
            console.print(f"  [red]Error: {e}[/]")

    return all_papers


@app.command()
def sources():
    """List available data sources."""
    table = Table(title="Available Data Sources")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Base URL")

    source_info = {
        Source.PUBMED: ("pubmed", "PubMed", "https://pubmed.ncbi.nlm.nih.gov"),
        Source.ARXIV: ("arxiv", "arXiv", "https://arxiv.org"),
        Source.BIORXIV: ("biorxiv", "bioRxiv", "https://biorxiv.org"),
        Source.MEDRXIV: ("medrxiv", "medRxiv", "https://medrxiv.org"),
    }

    for src, (id_, name, url) in source_info.items():
        table.add_row(id_, name, url)

    console.print(table)


@app.command()
def formats():
    """List available export formats."""
    table = Table(title="Export Formats")
    table.add_column("Format", style="cyan")
    table.add_column("Extension", style="green")
    table.add_column("Description")

    format_info = {
        ExportFormat.CSV: (".csv", "Comma-separated values, Excel compatible"),
        ExportFormat.PARQUET: (".parquet", "Columnar format for analytics"),
        ExportFormat.JSON: (".json", "Full data with nested structure"),
        ExportFormat.TXT: (".txt", "Human-readable plain text"),
    }

    for fmt, (ext, desc) in format_info.items():
        table.add_row(fmt.value.upper(), ext, desc)

    console.print(table)


@app.command()
def types():
    """List paper types for filtering."""
    table = Table(title="Paper Types")
    table.add_column("Type", style="cyan")
    table.add_column("Description")

    type_info = [
        ("research_article", "Original research paper"),
        ("review", "Literature review"),
        ("systematic_review", "Systematic review"),
        ("meta_analysis", "Meta-analysis"),
        ("clinical_trial", "Clinical trial"),
        ("case_report", "Case report"),
        ("preprint", "Preprint (not peer-reviewed)"),
    ]

    for type_id, desc in type_info:
        table.add_row(type_id, desc)

    console.print(table)


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", "--host", "-h", help="Host to bind"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind"),
    reload: bool = typer.Option(False, "--reload", "-r", help="Enable auto-reload"),
):
    """Start the API server."""
    import uvicorn

    console.print(f"[bold green]🚀 Starting API server at http://{host}:{port}[/]")
    console.print("[dim]Press Ctrl+C to stop[/]\n")

    uvicorn.run(
        "src.gateway.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command()
def version():
    """Show version information."""
    console.print("[bold]PubMed Scraper[/] v1.0.0")
    console.print("[dim]Distributed multi-source research paper scraper[/]")


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
