"""
PubMed Scraper - Full Text Extractor

Extracts full text content from downloaded PDFs.
Supports extraction to plain text for analysis and TXT export.
"""

import re
from pathlib import Path
from typing import Any

from src.shared.logging import LoggerMixin


class TextExtractor(LoggerMixin):
    """
    Extracts text content from PDF files.
    
    Uses PyMuPDF (fitz) for PDF text extraction.
    Falls back to basic extraction if advanced tools unavailable.
    """
    
    def __init__(self) -> None:
        self._fitz_available = False
        try:
            import fitz  # PyMuPDF
            self._fitz_available = True
        except ImportError:
            self.logger.warning("PyMuPDF not installed. PDF text extraction limited.")
    
    def extract_from_pdf(self, pdf_path: Path | str) -> str:
        """
        Extract text from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            
        Returns:
            Extracted text content
        """
        pdf_path = Path(pdf_path)
        
        if not pdf_path.exists():
            self.logger.error("PDF file not found", path=str(pdf_path))
            return ""
        
        if self._fitz_available:
            return self._extract_with_fitz(pdf_path)
        else:
            return self._basic_extract(pdf_path)
    
    def _extract_with_fitz(self, pdf_path: Path) -> str:
        """Extract text using PyMuPDF (fitz)."""
        import fitz
        
        try:
            text_parts = []
            
            with fitz.open(pdf_path) as doc:
                for page_num, page in enumerate(doc):
                    text = page.get_text()
                    if text.strip():
                        text_parts.append(f"--- Page {page_num + 1} ---\n{text}")
            
            full_text = "\n\n".join(text_parts)
            
            # Clean up the text
            full_text = self._clean_text(full_text)
            
            self.logger.info("Text extracted", path=str(pdf_path), chars=len(full_text))
            return full_text
            
        except Exception as e:
            self.logger.error("PDF extraction failed", error=str(e))
            return ""
    
    def _basic_extract(self, pdf_path: Path) -> str:
        """Basic text extraction (limited)."""
        # Try reading raw bytes for any embedded text
        try:
            content = pdf_path.read_bytes()
            # Find text between stream markers (very basic)
            text_parts = []
            
            # Look for text objects
            for match in re.finditer(rb'\((.*?)\)', content):
                try:
                    decoded = match.group(1).decode('latin-1')
                    if len(decoded) > 3 and decoded.isprintable():
                        text_parts.append(decoded)
                except:
                    continue
            
            return " ".join(text_parts[:1000])  # Limit output
            
        except Exception as e:
            self.logger.error("Basic extraction failed", error=str(e))
            return ""
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove page headers/footers (common patterns)
        text = re.sub(r'\n\d+\s*\n', '\n', text)  # Page numbers
        
        # Fix hyphenation at line breaks
        text = re.sub(r'-\n(\w)', r'\1', text)
        
        return text.strip()
    
    def extract_sections(self, text: str) -> dict[str, str]:
        """
        Try to extract common paper sections.
        
        Args:
            text: Full text content
            
        Returns:
            Dictionary with section names and content
        """
        sections = {}
        
        # Common section headers
        section_patterns = [
            (r'(?:^|\n)(Abstract)\s*\n', 'abstract'),
            (r'(?:^|\n)(Introduction)\s*\n', 'introduction'),
            (r'(?:^|\n)(Methods?|Materials? and Methods?)\s*\n', 'methods'),
            (r'(?:^|\n)(Results?)\s*\n', 'results'),
            (r'(?:^|\n)(Discussion)\s*\n', 'discussion'),
            (r'(?:^|\n)(Conclusions?)\s*\n', 'conclusion'),
            (r'(?:^|\n)(References?)\s*\n', 'references'),
        ]
        
        # Find section positions
        positions = []
        for pattern, name in section_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                positions.append((match.start(), match.end(), name))
        
        # Sort by position
        positions.sort()
        
        # Extract section content
        for i, (start, end, name) in enumerate(positions):
            if i + 1 < len(positions):
                next_start = positions[i + 1][0]
                sections[name] = text[end:next_start].strip()
            else:
                sections[name] = text[end:end+5000].strip()  # Last section, limit length
        
        return sections


# Singleton instance
text_extractor = TextExtractor()
