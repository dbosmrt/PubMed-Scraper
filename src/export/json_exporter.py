"""
PubMed Scraper - JSON Exporter

Exports papers to JSON format with optional pretty-printing.
"""

import json
from pathlib import Path
from typing import Any, Iterator

from src.crawlers.base import Paper
from src.export.base_exporter import BaseExporter
from src.shared.constants import ExportFormat


class JSONExporter(BaseExporter):
    """
    Export papers to JSON format.

    Features:
    - Pretty-printed or compact output
    - Full data preservation (no flattening)
    - UTF-8 encoding
    """

    format = ExportFormat.JSON

    def _get_extension(self) -> str:
        return ".json"

    def export(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        pretty: bool = True,
        **kwargs: Any,
    ) -> Path:
        """
        Export papers to JSON.

        Args:
            papers: Papers to export
            filename: Output filename
            pretty: Whether to pretty-print (indent)

        Returns:
            Path to created JSON file
        """
        output_path = self._get_output_path(filename)

        self.logger.info("Exporting to JSON", path=str(output_path))

        paper_list = list(papers)
        data = {
            "metadata": {
                "total_papers": len(paper_list),
                "export_format": "json",
            },
            "papers": [paper.to_dict() for paper in paper_list],
        }

        with open(output_path, "w", encoding="utf-8") as f:
            if pretty:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            else:
                json.dump(data, f, ensure_ascii=False, default=str)

        self.logger.info("JSON export complete", count=len(paper_list), path=str(output_path))
        return output_path
