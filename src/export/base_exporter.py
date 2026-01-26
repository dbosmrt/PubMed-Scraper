"""
PubMed Scraper - Base Exporter

Abstract base class for all export formats.
Provides common functionality and interface.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Iterator

from src.crawlers.base import Paper
from src.shared.constants import ExportFormat
from src.shared.logging import LoggerMixin


class BaseExporter(ABC, LoggerMixin):
    """
    Abstract base class for paper exporters.

    Subclasses must implement:
    - export(): Export papers to a file
    - _get_extension(): Return file extension
    """

    format: ExportFormat

    def __init__(self, output_dir: str | Path = "output") -> None:
        """
        Initialize exporter.

        Args:
            output_dir: Directory for output files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_output_path(self, filename: str) -> Path:
        """Get full output path for a file."""
        ext = self._get_extension()
        if not filename.endswith(ext):
            filename = f"{filename}{ext}"
        return self.output_dir / filename

    @abstractmethod
    def _get_extension(self) -> str:
        """Get file extension for this format."""
        ...

    @abstractmethod
    def export(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        **kwargs: Any,
    ) -> Path:
        """
        Export papers to a file.

        Args:
            papers: Papers to export
            filename: Output filename (without extension)
            **kwargs: Format-specific options

        Returns:
            Path to the created file
        """
        ...

    def _papers_to_dicts(self, papers: list[Paper] | Iterator[Paper]) -> list[dict[str, Any]]:
        """Convert papers to list of dictionaries."""
        return [paper.to_dict() for paper in papers]

    def _flatten_paper(self, paper: Paper) -> dict[str, Any]:
        """
        Flatten paper to a single-level dictionary for tabular formats.

        Handles nested fields like authors and keywords.
        """
        data = paper.to_dict()

        # Flatten authors to a string
        authors = data.pop("authors", [])
        data["authors"] = "; ".join(a["name"] for a in authors if a.get("name"))
        data["author_affiliations"] = "; ".join(
            a.get("affiliation", "") for a in authors if a.get("affiliation")
        )
        data["author_countries"] = "; ".join(
            a.get("country", "") for a in authors if a.get("country")
        )

        # Flatten lists to semicolon-separated strings
        for field in ["keywords", "mesh_terms", "categories", "countries"]:
            if field in data and isinstance(data[field], list):
                data[field] = "; ".join(str(v) for v in data[field])

        return data
