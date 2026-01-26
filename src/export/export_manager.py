"""
PubMed Scraper - Export Manager

Unified interface for exporting papers to multiple formats.
Provides factory pattern and batch export capabilities.
"""

from pathlib import Path
from typing import Any, Iterator, Type

from src.crawlers.base import Paper
from src.export.base_exporter import BaseExporter
from src.export.csv_exporter import CSVExporter
from src.export.json_exporter import JSONExporter
from src.export.parquet_exporter import ParquetExporter
from src.export.txt_exporter import TXTExporter
from src.shared.constants import ExportFormat
from src.shared.exceptions import UnsupportedFormatError
from src.shared.logging import LoggerMixin


class ExportManager(LoggerMixin):
    """
    Manages paper exports across multiple formats.

    Usage:
        manager = ExportManager(output_dir="exports")

        # Export to specific format
        manager.export(papers, "results", ExportFormat.CSV)

        # Export to multiple formats
        manager.export_all(papers, "results", [ExportFormat.CSV, ExportFormat.PARQUET])
    """

    _exporters: dict[ExportFormat, Type[BaseExporter]] = {
        ExportFormat.CSV: CSVExporter,
        ExportFormat.PARQUET: ParquetExporter,
        ExportFormat.JSON: JSONExporter,
        ExportFormat.TXT: TXTExporter,
    }

    def __init__(self, output_dir: str | Path = "output") -> None:
        """
        Initialize export manager.

        Args:
            output_dir: Base directory for exports
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._exporter_instances: dict[ExportFormat, BaseExporter] = {}

    def _get_exporter(self, format: ExportFormat) -> BaseExporter:
        """Get or create exporter instance for format."""
        if format not in self._exporter_instances:
            if format not in self._exporters:
                raise UnsupportedFormatError(
                    str(format),
                    [str(f) for f in self._exporters.keys()],
                )
            self._exporter_instances[format] = self._exporters[format](self.output_dir)
        return self._exporter_instances[format]

    def export(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        format: ExportFormat | str,
        **kwargs: Any,
    ) -> Path:
        """
        Export papers to a single format.

        Args:
            papers: Papers to export
            filename: Base filename (without extension)
            format: Export format
            **kwargs: Format-specific options

        Returns:
            Path to created file
        """
        if isinstance(format, str):
            format = ExportFormat(format.lower())

        exporter = self._get_exporter(format)

        self.logger.info("Starting export", format=str(format), filename=filename)

        # Convert iterator to list for multiple format export
        paper_list = list(papers)

        return exporter.export(paper_list, filename, **kwargs)

    def export_all(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        formats: list[ExportFormat | str] | None = None,
        **kwargs: Any,
    ) -> dict[ExportFormat, Path]:
        """
        Export papers to multiple formats.

        Args:
            papers: Papers to export
            filename: Base filename (without extension)
            formats: List of formats (default: all except PARQUET if pyarrow missing)
            **kwargs: Format-specific options

        Returns:
            Dictionary mapping format to created file path
        """
        if formats is None:
            formats = [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.TXT]
            try:
                import pyarrow
                formats.append(ExportFormat.PARQUET)
            except ImportError:
                self.logger.warning("PyArrow not installed, skipping Parquet export")

        # Convert iterator to list for multiple exports
        paper_list = list(papers)

        results = {}
        for fmt in formats:
            if isinstance(fmt, str):
                fmt = ExportFormat(fmt.lower())
            try:
                path = self.export(paper_list, filename, fmt, **kwargs)
                results[fmt] = path
            except Exception as e:
                self.logger.error("Export failed", format=str(fmt), error=str(e))

        return results

    @classmethod
    def get_supported_formats(cls) -> list[ExportFormat]:
        """Get list of supported export formats."""
        return list(cls._exporters.keys())

    @classmethod
    def register_exporter(cls, format: ExportFormat, exporter_class: Type[BaseExporter]) -> None:
        """Register a custom exporter for a format."""
        cls._exporters[format] = exporter_class
