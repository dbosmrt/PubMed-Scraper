"""
Download PDFs from PMC FTP Server

Uses the NCBI FTP server to download open-access PDFs:
https://ftp.ncbi.nlm.nih.gov/pub/pmc/oa_file_list.csv - contains file paths
https://ftp.ncbi.nlm.nih.gov/pub/pmc/[path_to_file].pdf

This is the reliable way to download PMC papers.
"""

import asyncio
import csv
import json
import sys
from pathlib import Path
from io import StringIO

sys.path.insert(0, ".")

import httpx


# Paths
INPUT_JSON = Path("output/biotech_1000_papers/biotechnology_papers.json")
PDF_DIR = Path("output/biotech_1000_papers/pdfs")
PDF_DIR.mkdir(parents=True, exist_ok=True)

# PMC FTP base URL
PMC_FTP_BASE = "https://ftp.ncbi.nlm.nih.gov/pub/pmc/"


async def get_pmc_file_list(client: httpx.AsyncClient) -> dict[str, str]:
    """
    Download and parse the PMC open access file list.
    Returns a dict mapping PMC IDs to their FTP file paths.
    """
    print("  Downloading PMC open access file list...")
    
    # The oa_file_list.csv contains all open-access files
    url = f"{PMC_FTP_BASE}oa_file_list.csv"
    
    try:
        response = await client.get(url)
        response.raise_for_status()
        
        pmc_files = {}
        reader = csv.DictReader(StringIO(response.text))
        
        for row in reader:
            pmc_id = row.get("Accession ID", "")
            file_path = row.get("File", "")
            
            if pmc_id and file_path and file_path.endswith(".tar.gz"):
                # Store the path (we'll use it to construct PDF path)
                pmc_files[pmc_id] = file_path
        
        print(f"  Found {len(pmc_files)} open-access papers in PMC")
        return pmc_files
        
    except Exception as e:
        print(f"  Error downloading file list: {e}")
        return {}


async def download_pmc_pdf(client: httpx.AsyncClient, pmc_id: str, output_path: Path) -> bool:
    """
    Download PDF from PMC using direct PDF links.
    
    PMC PDFs can be accessed via:
    - https://www.ncbi.nlm.nih.gov/pmc/articles/PMC[ID]/pdf/
    - Or the FTP server with known path
    """
    if output_path.exists():
        return True
    
    # Try multiple PDF URL patterns
    urls_to_try = [
        # Direct PMC PDF download
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/main.pdf",
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/",
        # Europe PMC (often more reliable)
        f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf",
    ]
    
    for url in urls_to_try:
        try:
            response = await client.get(url, follow_redirects=True)
            
            if response.status_code == 200:
                content = response.content
                # Check if it's a valid PDF
                if content.startswith(b"%PDF") or b"%PDF" in content[:2048]:
                    output_path.write_bytes(content)
                    return True
                    
        except Exception:
            continue
    
    return False


async def download_arxiv_pdf(client: httpx.AsyncClient, arxiv_id: str, output_path: Path) -> bool:
    """Download PDF from arXiv."""
    if output_path.exists():
        return True
    
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code == 200:
            content = response.content
            if content.startswith(b"%PDF") or b"%PDF" in content[:2048]:
                output_path.write_bytes(content)
                return True
    except Exception:
        pass
    
    return False


async def download_all_pdfs():
    """Download PDFs from all sources."""
    
    print("\n" + "="*70)
    print("  PDF DOWNLOAD - Using PMC FTP Server")
    print("="*70)
    
    # Load papers
    print("\n  Loading papers from JSON...")
    with open(INPUT_JSON, encoding="utf-8") as f:
        data = json.load(f)
    
    papers = data["papers"]
    print(f"  Total papers: {len(papers)}")
    
    # Categorize papers
    arxiv_papers = [p for p in papers if p.get("source") == "arxiv"]
    pmc_papers = [p for p in papers if p.get("pmc_id")]
    
    print(f"\n  arXiv papers: {len(arxiv_papers)}")
    print(f"  Papers with PMC ID: {len(pmc_papers)}")
    
    downloaded = 0
    failed = 0
    skipped = 0
    
    async with httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=True,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
    ) as client:
        
        # Download arXiv PDFs first
        print(f"\n[1/2] Downloading arXiv PDFs ({len(arxiv_papers)} papers)")
        print("-"*70)
        
        for i, paper in enumerate(arxiv_papers, 1):
            paper_id = paper.get("id", "")
            if not paper_id:
                continue
            
            safe_id = paper_id.replace("/", "_").replace(":", "_")
            output_path = PDF_DIR / f"arxiv_{safe_id}.pdf"
            
            if output_path.exists():
                skipped += 1
                continue
            
            print(f"  [{i}/{len(arxiv_papers)}] {paper_id}...", end=" ", flush=True)
            
            success = await download_arxiv_pdf(client, paper_id, output_path)
            if success:
                downloaded += 1
                size_kb = output_path.stat().st_size // 1024
                print(f"OK ({size_kb} KB)")
            else:
                failed += 1
                print("FAILED")
            
            await asyncio.sleep(0.5)
        
        print(f"\n  arXiv: {downloaded} new, {skipped} existed, {failed} failed")
        
        # Download PMC PDFs
        print(f"\n[2/2] Downloading PMC PDFs ({len(pmc_papers)} papers with PMC ID)")
        print("-"*70)
        
        pmc_downloaded = 0
        pmc_failed = 0
        pmc_skipped = 0
        
        for i, paper in enumerate(pmc_papers, 1):
            pmc_id = paper.get("pmc_id", "")
            if not pmc_id:
                continue
            
            # Ensure PMC prefix
            if not pmc_id.startswith("PMC"):
                pmc_id = f"PMC{pmc_id}"
            
            safe_id = paper.get("id", pmc_id).replace("/", "_")
            output_path = PDF_DIR / f"pmc_{safe_id}.pdf"
            
            if output_path.exists():
                pmc_skipped += 1
                continue
            
            if i % 10 == 1:
                print(f"  Progress: {i}/{len(pmc_papers)} ({pmc_downloaded} downloaded)")
            
            success = await download_pmc_pdf(client, pmc_id, output_path)
            if success:
                pmc_downloaded += 1
                downloaded += 1
            else:
                pmc_failed += 1
                failed += 1
            
            await asyncio.sleep(0.3)  # Rate limiting
        
        print(f"\n  PMC: {pmc_downloaded} new, {pmc_skipped} existed, {pmc_failed} failed")
    
    # Summary
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    total_size_mb = sum(f.stat().st_size for f in pdf_files) / (1024 * 1024)
    
    print("\n" + "="*70)
    print("  DOWNLOAD COMPLETE!")
    print("="*70)
    print(f"\n  Total PDF files: {len(pdf_files)}")
    print(f"  Total size: {total_size_mb:.1f} MB")
    print(f"  Downloaded this run: {downloaded}")
    print(f"  Already existed: {skipped + pmc_skipped}")
    print(f"  Failed: {failed}")
    print(f"\n  PDF directory: {PDF_DIR.absolute()}")
    print("\n  DONE!\n")
    
    return len(pdf_files)


if __name__ == "__main__":
    result = asyncio.run(download_all_pdfs())
