"""
PubMed Scraper - Download Module

Provides full paper download and text extraction capabilities.
"""

from src.download.paper_downloader import PaperDownloader
from src.download.text_extractor import TextExtractor, text_extractor

__all__ = ["PaperDownloader", "TextExtractor", "text_extractor"]
