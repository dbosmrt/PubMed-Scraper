"""
PubMed Scraper - Full Paper Downloader

Downloads complete research papers (PDFs) from open-access sources:
- PubMed Central (PMC) - free full-text articles
- arXiv - all papers are open access
- bioRxiv/medRxiv - all preprints are open access
"""

import asyncio
from pathlib import Path
from typing import Any

import httpx

from src.crawlers.base import Paper
from src.shared.constants import Source
from src.shared.logging import LoggerMixin


class PaperDownloader(LoggerMixin):
    """
    Downloads full paper content (PDFs) from open-access sources.
    
    Supports:
    - PubMed Central (PMC) PDFs
    - arXiv PDFs
    - bioRxiv/medRxiv PDFs
    """
    
    def __init__(self, output_dir: str | Path = "output/papers") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._client: httpx.AsyncClient | None = None
        
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                follow_redirects=True,
                headers={
                    "User-Agent": "PubMed-Scraper/1.0 (Research Paper Downloader)",
                    "Accept": "application/pdf, text/html, */*",
                },
            )
        return self._client
    
    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    def _get_pdf_url(self, paper: Paper) -> str | None:
        """Get the PDF URL for a paper based on its source."""
        
        # If paper already has a PDF URL, use it
        if paper.pdf_url:
            return paper.pdf_url
        
        # Source-specific PDF URL generation
        if paper.source == Source.PUBMED:
            # Try PMC first
            if paper.pmc_id:
                return f"https://www.ncbi.nlm.nih.gov/pmc/articles/{paper.pmc_id}/pdf/"
            # Try Europe PMC
            if paper.doi:
                return f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={paper.pmc_id}&blobtype=pdf"
            return None
            
        elif paper.source == Source.ARXIV:
            # arXiv PDF URL format
            arxiv_id = paper.id.replace("v", "").split("v")[0] if "v" in paper.id else paper.id
            return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            
        elif paper.source in [Source.BIORXIV, Source.MEDRXIV]:
            # bioRxiv/medRxiv PDF URL
            server = "biorxiv" if paper.source == Source.BIORXIV else "medrxiv"
            doi = paper.id or paper.doi
            if doi:
                return f"https://www.{server}.org/content/{doi}.full.pdf"
            return None
            
        return None
    
    async def download_pdf(self, paper: Paper, filename: str | None = None) -> Path | None:
        """
        Download PDF for a paper.
        
        Args:
            paper: Paper object with source and identifiers
            filename: Optional custom filename (without extension)
            
        Returns:
            Path to downloaded PDF or None if download failed
        """
        pdf_url = self._get_pdf_url(paper)
        
        if not pdf_url:
            self.logger.warning("No PDF URL available", paper_id=paper.id, source=str(paper.source))
            return None
        
        # Generate filename
        if not filename:
            safe_id = paper.id.replace("/", "_").replace(":", "_")
            filename = f"{paper.source.value}_{safe_id}"
        
        output_path = self.output_dir / f"{filename}.pdf"
        
        # Skip if already downloaded
        if output_path.exists():
            self.logger.info("PDF already exists", path=str(output_path))
            return output_path
        
        try:
            self.logger.info("Downloading PDF", url=pdf_url[:80], paper_id=paper.id)
            
            response = await self.client.get(pdf_url)
            response.raise_for_status()
            
            # Check if we got a PDF
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
                self.logger.warning("Response is not a PDF", content_type=content_type)
                return None
            
            # Save PDF
            output_path.write_bytes(response.content)
            self.logger.info("PDF downloaded", path=str(output_path), size_kb=len(response.content) // 1024)
            
            return output_path
            
        except httpx.HTTPStatusError as e:
            self.logger.warning("PDF download failed", status=e.response.status_code, url=pdf_url[:60])
            return None
        except Exception as e:
            self.logger.error("PDF download error", error=str(e))
            return None
    
    async def download_batch(
        self, 
        papers: list[Paper], 
        max_concurrent: int = 5
    ) -> dict[str, Path]:
        """
        Download PDFs for multiple papers.
        
        Args:
            papers: List of papers to download
            max_concurrent: Maximum concurrent downloads
            
        Returns:
            Dictionary mapping paper ID to downloaded file path
        """
        results = {}
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def download_with_limit(paper: Paper) -> tuple[str, Path | None]:
            async with semaphore:
                path = await self.download_pdf(paper)
                return paper.id, path
        
        tasks = [download_with_limit(paper) for paper in papers]
        completed = await asyncio.gather(*tasks)
        
        for paper_id, path in completed:
            if path:
                results[paper_id] = path
        
        self.logger.info("Batch download complete", total=len(papers), downloaded=len(results))
        return results
    
    async def __aenter__(self) -> "PaperDownloader":
        return self
    
    async def __aexit__(self, *args: Any) -> None:
        await self.close()
