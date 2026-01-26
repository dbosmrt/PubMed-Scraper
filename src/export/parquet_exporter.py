"""
PubMed Scraper - Parquet Exporter

Exports papers to Apache Parquet format for efficient storage and analysis.
Uses PyArrow for schema enforcement and compression.
"""

from pathlib import Path
from typing import Any, Iterator

import pyarrow as pa
import pyarrow.parquet as pq

from src.crawlers.base import Paper
from src.export.base_exporter import BaseExporter
from src.shared.constants import ExportFormat


class ParquetExporter(BaseExporter):
    """
    Export papers to Parquet format.

    Features:
    - Schema enforcement with PyArrow
    - Snappy compression by default
    - Efficient columnar storage for analytics
    """

    format = ExportFormat.PARQUET

    # PyArrow schema for papers
    SCHEMA = pa.schema([
        ("id", pa.string()),
        ("doi", pa.string()),
        ("source", pa.string()),
        ("title", pa.string()),
        ("abstract", pa.string()),
        ("authors", pa.string()),  # Flattened to semicolon-separated
        ("author_affiliations", pa.string()),
        ("author_countries", pa.string()),
        ("keywords", pa.string()),
        ("journal", pa.string()),
        ("volume", pa.string()),
        ("issue", pa.string()),
        ("pages", pa.string()),
        ("publication_date", pa.string()),
        ("year", pa.int32()),
        ("paper_type", pa.string()),
        ("categories", pa.string()),
        ("mesh_terms", pa.string()),
        ("url", pa.string()),
        ("pdf_url", pa.string()),
        ("pmc_id", pa.string()),
        ("countries", pa.string()),
        ("language", pa.string()),
    ])

    def _get_extension(self) -> str:
        return ".parquet"

    def export(
        self,
        papers: list[Paper] | Iterator[Paper],
        filename: str,
        compression: str = "snappy",
        row_group_size: int = 10000,
        **kwargs: Any,
    ) -> Path:
        """
        Export papers to Parquet.

        Args:
            papers: Papers to export
            filename: Output filename
            compression: Compression codec (snappy, gzip, lz4, zstd, none)
            row_group_size: Number of rows per row group

        Returns:
            Path to created Parquet file
        """
        output_path = self._get_output_path(filename)

        self.logger.info("Exporting to Parquet", path=str(output_path), compression=compression)

        # Convert papers to flat dictionaries
        paper_list = list(papers)
        rows = [self._flatten_paper(paper) for paper in paper_list]

        # Convert to PyArrow Table
        # Handle missing/None values
        columns = {}
        for field in self.SCHEMA:
            col_name = field.name
            col_values = []
            for row in rows:
                value = row.get(col_name)
                if value is None:
                    value = None
                elif field.type == pa.int32():
                    value = int(value) if value else None
                else:
                    value = str(value) if value else None
                col_values.append(value)
            columns[col_name] = col_values

        table = pa.table(columns, schema=self.SCHEMA)

        # Write to Parquet
        pq.write_table(
            table,
            output_path,
            compression=compression,
            row_group_size=row_group_size,
        )

        self.logger.info(
            "Parquet export complete",
            count=len(paper_list),
            path=str(output_path),
            size_bytes=output_path.stat().st_size,
        )
        return output_path
