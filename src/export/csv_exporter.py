"""
PubMed Scraper - CSV Exporter

Exports papers to CSV format with configurable columns.
"""

import csv
from pathlib import Path
from typing import Any, Iterator

from src.crawlers.base import Paper
from src.export.base_exporter import BaseExporter
from src.shared.constants import ExportFormat


class CSVExporter(BaseExporter):
    """
    Export papers to CSV format.

    Features:
    - Configurable columns
    - Handles nested fields (authors, keywords)
    - UTF-8 encoding with BOM for Excel compatibility
    """

    format = ExportFormat.CSV

    # Default columns to include
    DEFAULT_COLUMNS = [
        "id",
        "doi",
        "source",
        "title",
        "abstract",
        "authors",
        "author_affiliations",
        "keywords",
        "journal",
        "volume",
        "issue",
        "pages",
        "publication_date",
        "year",
        "paper_type",
        "categories",
        "mesh_terms",
        "url",
        "pdf_url",
        "pmc_id",
        "countries",
    ]

    def _get_extension(self) -> str:
        return ".csv"

    def export(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        columns: list[str] | None = None,
        include_header: bool = True,
        delimiter: str = ",",
        **kwargs: Any,
    ) -> Path:
        """
        Export papers to CSV.

        Args:
            papers: Papers to export
            filename: Output filename
            columns: Columns to include (default: all)
            include_header: Whether to include header row
            delimiter: Field delimiter

        Returns:
            Path to created CSV file
        """
        output_path = self._get_output_path(filename)
        columns = columns or self.DEFAULT_COLUMNS

        self.logger.info("Exporting to CSV", path=str(output_path))

        # Convert to list to get count
        paper_list = list(papers)

        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=columns,
                delimiter=delimiter,
                extrasaction="ignore",
            )

            if include_header:
                writer.writeheader()

            for paper in paper_list:
                row = self._flatten_paper(paper)
                writer.writerow(row)

        self.logger.info("CSV export complete", count=len(paper_list), path=str(output_path))
        return output_path
