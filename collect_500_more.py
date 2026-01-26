"""
Collect 500 More Papers - Expanding Collection to 1500

Collects additional 500 papers with PDFs from all four countries.
"""

import asyncio
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, ".")

import httpx

from src.crawlers import CrawlerFactory, FilterParams
from src.processors import PaperClassifier
from src.shared.constants import PaperType, Source


# Configuration
ADDITIONAL_PAPERS = 500
PAPERS_PER_COUNTRY = ADDITIONAL_PAPERS // 4  # 125 each
OUTPUT_DIR = Path("output/biotech_1000_papers")
PDF_DIR = OUTPUT_DIR / "pdfs"

# More search terms for variety
SEARCH_QUERIES = {
    "USA": [
        '(genomics[Title/Abstract] OR proteomics[Title/Abstract]) AND (USA[Affiliation] OR "United States"[Affiliation])',
        '(molecular biology[Title/Abstract]) AND (USA[Affiliation] OR "United States"[Affiliation])',
        '(synthetic biology[Title/Abstract]) AND (USA[Affiliation])',
    ],
    "CHN": [
        '(genomics[Title/Abstract] OR proteomics[Title/Abstract]) AND (China[Affiliation])',
        '(molecular biology[Title/Abstract]) AND (China[Affiliation])',
        '(bioinformatics[Title/Abstract]) AND (China[Affiliation])',
    ],
    "IND": [
        '(genomics[Title/Abstract] OR proteomics[Title/Abstract]) AND (India[Affiliation])',
        '(molecular biology[Title/Abstract]) AND (India[Affiliation])',
        '(computational biology[Title/Abstract]) AND (India[Affiliation])',
    ],
    "JPN": [
        '(genomics[Title/Abstract] OR proteomics[Title/Abstract]) AND (Japan[Affiliation])',
        '(molecular biology[Title/Abstract]) AND (Japan[Affiliation])',
        '(systems biology[Title/Abstract]) AND (Japan[Affiliation])',
    ],
}

COUNTRY_KEYWORDS = {
    "USA": ["united states", "usa", "u.s.", "america"],
    "IND": ["india", "indian"],
    "CHN": ["china", "chinese"],
    "JPN": ["japan", "japanese"],
}


def verify_country(paper, expected: str) -> bool:
    """Verify paper is from expected country."""
    keywords = COUNTRY_KEYWORDS.get(expected, [])
    affiliation_text = " ".join(
        (a.affiliation or "") + " " + (a.country or "") 
        for a in paper.authors
    ).lower()
    if paper.countries:
        affiliation_text += " " + " ".join(paper.countries).lower()
    return any(kw in affiliation_text for kw in keywords)


async def download_pmc_pdf(client: httpx.AsyncClient, pmc_id: str, output_path: Path) -> bool:
    """Download PDF from PMC."""
    if output_path.exists():
        return True
    
    if not pmc_id.startswith("PMC"):
        pmc_id = f"PMC{pmc_id}"
    
    urls = [
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/main.pdf",
        f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/",
        f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmc_id}&blobtype=pdf",
    ]
    
    for url in urls:
        try:
            response = await client.get(url, follow_redirects=True)
            if response.status_code == 200:
                content = response.content
                if content.startswith(b"%PDF") or b"%PDF" in content[:2048]:
                    output_path.write_bytes(content)
                    return True
        except:
            continue
    return False


async def collect_more():
    """Collect 500 more papers."""
    
    print("\n" + "="*80)
    print("  COLLECTING 500 MORE PAPERS")
    print("="*80)
    
    # Load existing
    json_path = OUTPUT_DIR / "biotechnology_papers.json"
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    
    existing_papers = data["papers"]
    existing_ids = {p.get("id") for p in existing_papers}
    
    print(f"\n  Existing papers: {len(existing_papers)}")
    print(f"  Target: {len(existing_papers) + ADDITIONAL_PAPERS}")
    print(f"  Collecting {PAPERS_PER_COUNTRY} more from each country")
    
    classifier = PaperClassifier(use_ml=False)
    new_papers = []
    collected_by_country = defaultdict(int)
    
    # Collect from PubMed
    print("\n[PHASE 1] COLLECTING FROM PUBMED")
    print("-"*80)
    
    crawler = CrawlerFactory.get(Source.PUBMED)
    
    async with crawler:
        for country, queries in SEARCH_QUERIES.items():
            print(f"\n  Collecting for {country}...")
            
            for query in queries:
                if collected_by_country[country] >= PAPERS_PER_COUNTRY:
                    break
                
                print(f"    Query: {query[:50]}...")
                
                filters = FilterParams(max_results=PAPERS_PER_COUNTRY * 4, languages=[])
                
                try:
                    async for paper in crawler.crawl(query, filters):
                        if collected_by_country[country] >= PAPERS_PER_COUNTRY:
                            break
                        
                        if paper.id in existing_ids:
                            continue
                        
                        if not paper.pmc_id:
                            continue
                        
                        paper.paper_type = classifier.classify(paper)
                        if paper.paper_type in [PaperType.REVIEW, PaperType.SYSTEMATIC_REVIEW,
                                                 PaperType.META_ANALYSIS, PaperType.EDITORIAL]:
                            continue
                        
                        if not verify_country(paper, country):
                            continue
                        
                        paper.raw_data["target_country"] = country
                        new_papers.append(paper)
                        existing_ids.add(paper.id)
                        collected_by_country[country] += 1
                        
                        if collected_by_country[country] % 25 == 0:
                            print(f"      {country}: {collected_by_country[country]}/{PAPERS_PER_COUNTRY}")
                            
                except Exception as e:
                    print(f"      Error: {e}")
            
            print(f"    {country}: Collected {collected_by_country[country]}")
    
    print(f"\n  New papers collected: {len(new_papers)}")
    print(f"  By country: {dict(collected_by_country)}")
    
    # Download PDFs
    print("\n[PHASE 2] DOWNLOADING PDFS")
    print("-"*80)
    
    pdf_downloaded = 0
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    
    async with httpx.AsyncClient(
        timeout=120.0,
        follow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"}
    ) as client:
        for i, paper in enumerate(new_papers, 1):
            pmc_id = paper.pmc_id
            if not pmc_id:
                continue
            
            output_path = PDF_DIR / f"pmc_{paper.id}.pdf"
            
            if i % 50 == 0:
                print(f"  Progress: {i}/{len(new_papers)} ({pdf_downloaded} downloaded)")
            
            success = await download_pmc_pdf(client, pmc_id, output_path)
            if success:
                paper.raw_data["pdf_path"] = str(output_path)
                pdf_downloaded += 1
            
            await asyncio.sleep(0.3)
    
    print(f"\n  PDFs downloaded: {pdf_downloaded}")
    
    # Merge and save
    print("\n[PHASE 3] SAVING UPDATED DATA")
    print("-"*80)
    
    for paper in new_papers:
        paper_dict = paper.to_dict()
        paper_dict["target_country"] = paper.raw_data.get("target_country", "")
        paper_dict["pdf_path"] = paper.raw_data.get("pdf_path", "")
        paper_dict["full_text"] = ""
        existing_papers.append(paper_dict)
    
    # Update distribution
    country_dist = defaultdict(int)
    for p in existing_papers:
        country = p.get("target_country", "")
        if country:
            country_dist[country] += 1
    
    # Save JSON
    updated_data = {
        "metadata": {
            "total_papers": len(existing_papers),
            "collection_date": datetime.now().isoformat(),
            "countries": ["USA", "IND", "CHN", "JPN"],
        },
        "country_distribution": dict(country_dist),
        "papers": existing_papers,
    }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, indent=2, ensure_ascii=False, default=str)
    
    # Save CSV
    csv_path = OUTPUT_DIR / "biotechnology_papers_metadata.csv"
    csv_columns = [
        "id", "doi", "source", "title", "authors", "journal", "year",
        "paper_type", "abstract", "url", "target_country", "pdf_path"
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        
        for paper in existing_papers:
            authors = paper.get("authors", [])
            if isinstance(authors, list) and authors and isinstance(authors[0], dict):
                author_str = "; ".join(a.get("name", "") for a in authors[:10])
            else:
                author_str = str(authors)[:200]
            
            row = {
                "id": paper.get("id", ""),
                "doi": paper.get("doi", ""),
                "source": paper.get("source", ""),
                "title": paper.get("title", ""),
                "authors": author_str,
                "journal": paper.get("journal", ""),
                "year": paper.get("year", ""),
                "paper_type": paper.get("paper_type", ""),
                "abstract": (paper.get("abstract", "") or "")[:300],
                "url": paper.get("url", ""),
                "target_country": paper.get("target_country", ""),
                "pdf_path": paper.get("pdf_path", ""),
            }
            writer.writerow(row)
    
    # Count PDFs
    pdf_files = list(PDF_DIR.glob("*.pdf"))
    total_size_mb = sum(f.stat().st_size for f in pdf_files) / (1024 * 1024)
    
    print("\n" + "="*80)
    print("  COMPLETE!")
    print("="*80)
    print(f"\n  Total papers now: {len(existing_papers)}")
    print(f"  Total PDFs: {len(pdf_files)} ({total_size_mb:.1f} MB)")
    print(f"  New papers: {len(new_papers)}")
    print(f"  New PDFs: {pdf_downloaded}")
    
    print("\n  Country Distribution:")
    for c in ["USA", "IND", "CHN", "JPN"]:
        print(f"    {c}: {country_dist.get(c, 0)}")
    
    print(f"\n  Output: {OUTPUT_DIR.absolute()}")
    print("\n  DONE!\n")


if __name__ == "__main__":
    asyncio.run(collect_more())
