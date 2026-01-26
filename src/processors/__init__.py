"""
PubMed Scraper - Processors Module
"""

from src.processors.classifier import PaperClassifier
from src.processors.metadata import CountryMapper, country_mapper

__all__ = ["PaperClassifier", "CountryMapper", "country_mapper"]
