"""
PubMed Scraper - TXT Exporter

Exports papers to plain text format for human-readable output.
"""

from pathlib import Path
from typing import Any, Iterator

from src.crawlers.base import Paper
from src.export.base_exporter import BaseExporter
from src.shared.constants import ExportFormat


class TXTExporter(BaseExporter):
    """
    Export papers to plain text format.

    Features:
    - Human-readable format
    - Configurable separator between papers
    - Optional field selection
    """

    format = ExportFormat.TXT

    def _get_extension(self) -> str:
        return ".txt"

    def export(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        separator: str = "\n" + "=" * 80 + "\n",
        include_abstract: bool = True,
        **kwargs: Any,
    ) -> Path:
        """
        Export papers to plain text.

        Args:
            papers: Papers to export
            filename: Output filename
            separator: Separator between papers
            include_abstract: Whether to include full abstract

        Returns:
            Path to created TXT file
        """
        output_path = self._get_output_path(filename)

        self.logger.info("Exporting to TXT", path=str(output_path))

        paper_list = list(papers)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"PubMed Scraper Export\n")
            f.write(f"Total Papers: {len(paper_list)}\n")
            f.write(separator)

            for i, paper in enumerate(paper_list, 1):
                self._write_paper(f, paper, i, include_abstract)
                if i < len(paper_list):
                    f.write(separator)

        self.logger.info("TXT export complete", count=len(paper_list), path=str(output_path))
        return output_path

    def _write_paper(
        self,
        f,
        paper: Paper,
        index: int,
        include_abstract: bool,
    ) -> None:
        """Write a single paper to the file."""
        f.write(f"\n[{index}] {paper.title}\n\n")

        # Identifiers
        f.write(f"ID: {paper.id}\n")
        if paper.doi:
            f.write(f"DOI: {paper.doi}\n")
        f.write(f"Source: {paper.source}\n")

        # Authors
        if paper.authors:
            authors_str = ", ".join(a.name for a in paper.authors[:10])
            if len(paper.authors) > 10:
                authors_str += f" ... and {len(paper.authors) - 10} more"
            f.write(f"Authors: {authors_str}\n")

        # Publication info
        if paper.journal:
            journal_info = paper.journal
            if paper.volume:
                journal_info += f" {paper.volume}"
            if paper.issue:
                journal_info += f"({paper.issue})"
            if paper.pages:
                journal_info += f": {paper.pages}"
            f.write(f"Journal: {journal_info}\n")

        if paper.year:
            f.write(f"Year: {paper.year}\n")

        f.write(f"Type: {paper.paper_type}\n")

        # Keywords
        if paper.keywords:
            f.write(f"Keywords: {', '.join(paper.keywords[:10])}\n")

        # Countries
        if paper.countries:
            f.write(f"Countries: {', '.join(paper.countries)}\n")

        # URL
        if paper.url:
            f.write(f"URL: {paper.url}\n")

        # Abstract
        if include_abstract and paper.abstract:
            f.write(f"\nAbstract:\n{paper.abstract}\n")
