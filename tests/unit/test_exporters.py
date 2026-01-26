"""
Unit tests for export functionality.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.crawlers.base import Author, Paper
from src.export import CSVExporter, ExportManager, JSONExporter, TXTExporter
from src.shared.constants import ExportFormat, PaperType, Source


@pytest.fixture
def sample_papers():
    return [
        Paper(
            id="12345",
            doi="10.1234/test",
            source=Source.PUBMED,
            title="Test Paper 1",
            abstract="This is a test abstract for paper 1.",
            authors=[
                Author(name="John Doe", affiliation="MIT", country="USA"),
                Author(name="Jane Smith", affiliation="Stanford", country="USA"),
            ],
            keywords=["cancer", "biomarkers"],
            journal="Nature",
            year=2023,
            paper_type=PaperType.RESEARCH_ARTICLE,
            url="https://example.com/paper1",
            countries=["USA"],
        ),
        Paper(
            id="67890",
            doi="10.5678/test2",
            source=Source.ARXIV,
            title="Test Paper 2",
            abstract="This is a test abstract for paper 2.",
            authors=[
                Author(name="Alice Brown", affiliation="Oxford", country="GBR"),
            ],
            keywords=["machine learning"],
            year=2024,
            paper_type=PaperType.PREPRINT,
            countries=["GBR"],
        ),
    ]


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


class TestCSVExporter:
    """Tests for CSV exporter."""

    def test_export_creates_file(self, sample_papers, temp_dir):
        exporter = CSVExporter(output_dir=temp_dir)
        path = exporter.export(sample_papers, "test_output")
        
        assert path.exists()
        assert path.suffix == ".csv"

    def test_export_contains_data(self, sample_papers, temp_dir):
        exporter = CSVExporter(output_dir=temp_dir)
        path = exporter.export(sample_papers, "test_output")
        
        content = path.read_text(encoding="utf-8-sig")
        assert "Test Paper 1" in content
        assert "Test Paper 2" in content
        assert "John Doe" in content

    def test_export_custom_columns(self, sample_papers, temp_dir):
        exporter = CSVExporter(output_dir=temp_dir)
        path = exporter.export(
            sample_papers,
            "test_output",
            columns=["id", "title", "year"],
        )
        
        content = path.read_text(encoding="utf-8-sig")
        lines = content.strip().split("\n")
        
        # Header + 2 data rows
        assert len(lines) == 3
        assert "id,title,year" in lines[0]


class TestJSONExporter:
    """Tests for JSON exporter."""

    def test_export_creates_file(self, sample_papers, temp_dir):
        exporter = JSONExporter(output_dir=temp_dir)
        path = exporter.export(sample_papers, "test_output")
        
        assert path.exists()
        assert path.suffix == ".json"

    def test_export_valid_json(self, sample_papers, temp_dir):
        exporter = JSONExporter(output_dir=temp_dir)
        path = exporter.export(sample_papers, "test_output")
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        assert "papers" in data
        assert len(data["papers"]) == 2
        assert data["metadata"]["total_papers"] == 2


class TestTXTExporter:
    """Tests for TXT exporter."""

    def test_export_creates_file(self, sample_papers, temp_dir):
        exporter = TXTExporter(output_dir=temp_dir)
        path = exporter.export(sample_papers, "test_output")
        
        assert path.exists()
        assert path.suffix == ".txt"

    def test_export_human_readable(self, sample_papers, temp_dir):
        exporter = TXTExporter(output_dir=temp_dir)
        path = exporter.export(sample_papers, "test_output")
        
        content = path.read_text(encoding="utf-8")
        
        assert "Test Paper 1" in content
        assert "John Doe, Jane Smith" in content
        assert "Year: 2023" in content


class TestExportManager:
    """Tests for ExportManager."""

    def test_get_supported_formats(self):
        formats = ExportManager.get_supported_formats()
        
        assert ExportFormat.CSV in formats
        assert ExportFormat.JSON in formats
        assert ExportFormat.TXT in formats

    def test_export_single_format(self, sample_papers, temp_dir):
        manager = ExportManager(output_dir=temp_dir)
        path = manager.export(sample_papers, "test", ExportFormat.CSV)
        
        assert path.exists()

    def test_export_all_formats(self, sample_papers, temp_dir):
        manager = ExportManager(output_dir=temp_dir)
        results = manager.export_all(
            sample_papers,
            "test",
            [ExportFormat.CSV, ExportFormat.JSON, ExportFormat.TXT],
        )
        
        assert len(results) == 3
        for path in results.values():
            assert path.exists()
