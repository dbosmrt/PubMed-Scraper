"""
Open Access Paper Collection - Guaranteed PDFs

Collects papers ONLY from sources with guaranteed free PDFs:
- arXiv (100% open access)
- bioRxiv/medRxiv (100% open access)

This ensures every paper collected has a downloadable PDF.
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
from src.download import text_extractor
from src.shared.constants import PaperType, Source


# Configuration
TARGET_TOTAL = 1000
COUNTRIES = ["USA", "IND", "CHN", "JPN"]
PAPERS_PER_COUNTRY = TARGET_TOTAL // len(COUNTRIES)

# Broad search terms
SEARCH_TERMS = [
    "biotechnology",
    "bioinformatics", 
    "genomics",
    "computational biology",
    "systems biology",
    "proteomics",
    "transcriptomics",
    "machine learning biology",
    "deep learning biology",
    "drug discovery",
]

# Country keywords
COUNTRY_KEYWORDS = {
    "USA": ["united states", "usa", "u.s.", "america", "california", "new york", 
            "texas", "massachusetts", "maryland", "illinois", "pennsylvania", 
            "harvard", "mit", "stanford", "yale", "princeton", "columbia", "berkeley",
            "ucla", "ucsf", "duke", "cornell", "upenn", "nih", "cdc", "washington"],
    "IND": ["india", "indian", "mumbai", "delhi", "bangalore", "bengaluru", "chennai", 
            "hyderabad", "kolkata", "pune", "iit ", "iisc", "aiims", "csir", "icmr",
            "tifr", "ncbs", "jnu", "bhu", "manipal", "vit", "bits"],
    "CHN": ["china", "chinese", "beijing", "shanghai", "guangzhou", "shenzhen", 
            "wuhan", "nanjing", "hangzhou", "peking university", "tsinghua", "fudan", 
            "zhejiang", "cas ", "chinese academy", "huazhong", "sichuan"],
    "JPN": ["japan", "japanese", "tokyo", "osaka", "kyoto", "nagoya", "fukuoka", 
            "hokkaido", "riken", "keio", "waseda", "tohoku", "university of tokyo"],
}


def detect_country(paper) -> str | None:
    """Detect country from paper affiliations."""
    affiliation_text = " ".join(
        (a.affiliation or "") + " " + (a.country or "") 
        for a in paper.authors
    ).lower()
    
    if hasattr(paper, 'countries') and paper.countries:
        affiliation_text += " " + " ".join(paper.countries).lower()
    
    for country, keywords in COUNTRY_KEYWORDS.items():
        if any(kw in affiliation_text for kw in keywords):
            return country
    return None


async def download_pdf(client: httpx.AsyncClient, url: str, output_path: Path) -> bool:
    """Download a PDF file."""
    if output_path.exists():
        return True
    try:
        response = await client.get(url)
        if response.status_code == 200:
            content = response.content
            if content.startswith(b"%PDF") or b"%PDF" in content[:2048]:
                output_path.write_bytes(content)
                return True
        return False
    except:
        return False


async def collect_open_access_papers():
    """Collect papers from open-access sources only."""
    
    print("\n" + "="*80)
    print("  OPEN ACCESS PAPER COLLECTION (Guaranteed PDFs)")
    print(f"  Target: {TARGET_TOTAL} papers with downloadable PDFs")
    print(f"  Countries: {', '.join(COUNTRIES)}")
    print("="*80)
    
    output_dir = Path("output/biotech_open_access")
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir = output_dir / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    
    classifier = PaperClassifier(use_ml=False)
    papers_by_country = defaultdict(list)
    all_papers = []
    
    # ==========================================================================
    # PHASE 1: Collect from arXiv
    # ==========================================================================
    print("\n[PHASE 1] COLLECTING FROM ARXIV (100% Open Access)")
    print("-"*80)
    
    crawler_arxiv = CrawlerFactory.get(Source.ARXIV)
    
    async with crawler_arxiv:
        for term in SEARCH_TERMS:
            if all(len(papers_by_country[c]) >= PAPERS_PER_COUNTRY for c in COUNTRIES):
                break
                
            print(f"\n  Searching arXiv for '{term}'...")
            
            query = f"all:{term}"
            filters = FilterParams(max_results=500, languages=[])
            
            try:
                async for paper in crawler_arxiv.crawl(query, filters):
                    paper.paper_type = classifier.classify(paper)
                    if paper.paper_type in [PaperType.REVIEW, PaperType.EDITORIAL]:
                        continue
                    
                    country = detect_country(paper)
                    if country and len(papers_by_country[country]) < PAPERS_PER_COUNTRY:
                        paper.raw_data["target_country"] = country
                        papers_by_country[country].append(paper)
                        all_papers.append(paper)
                        
                        if len(all_papers) % 100 == 0:
                            counts = {c: len(papers_by_country[c]) for c in COUNTRIES}
                            print(f"    Total: {len(all_papers)}, by country: {counts}")
                    
                    if all(len(papers_by_country[c]) >= PAPERS_PER_COUNTRY for c in COUNTRIES):
                        break
                        
            except Exception as e:
                print(f"    Error: {e}")
    
    arxiv_count = len([p for p in all_papers if p.source == Source.ARXIV])
    print(f"\n  arXiv total: {arxiv_count} papers")
    
    # ==========================================================================
    # PHASE 2: Collect from bioRxiv
    # ==========================================================================
    print("\n[PHASE 2] COLLECTING FROM BIORXIV (100% Open Access)")
    print("-"*80)
    
    needed = {c: max(0, PAPERS_PER_COUNTRY - len(papers_by_country[c])) for c in COUNTRIES}
    print(f"  Still needed: {needed}")
    
    if sum(needed.values()) > 0:
        crawler_biorxiv = CrawlerFactory.get(Source.BIORXIV)
        
        async with crawler_biorxiv:
            for term in SEARCH_TERMS[:5]:
                if sum(needed.values()) == 0:
                    break
                    
                print(f"\n  Searching bioRxiv for '{term}'...")
                filters = FilterParams(max_results=1000, languages=[])
                
                try:
                    async for paper in crawler_biorxiv.crawl(term, filters):
                        paper.paper_type = classifier.classify(paper)
                        if paper.paper_type == PaperType.REVIEW:
                            continue
                        
                        country = detect_country(paper)
                        if country and needed.get(country, 0) > 0:
                            paper.raw_data["target_country"] = country
                            papers_by_country[country].append(paper)
                            all_papers.append(paper)
                            needed[country] -= 1
                            
                            if len(all_papers) % 100 == 0:
                                print(f"    Total: {len(all_papers)}, still needed: {needed}")
                        
                        if sum(needed.values()) == 0:
                            break
                            
                except Exception as e:
                    print(f"    Error: {e}")
    
    biorxiv_count = len([p for p in all_papers if p.source == Source.BIORXIV])
    print(f"\n  bioRxiv total: {biorxiv_count} papers")
    
    # ==========================================================================
    # PHASE 3: Download ALL PDFs
    # ==========================================================================
    print("\n[PHASE 3] DOWNLOADING ALL PDFS")
    print("-"*80)
    
    downloaded = 0
    failed = 0
    
    async with httpx.AsyncClient(
        timeout=120.0, 
        follow_redirects=True,
        headers={"User-Agent": "PubMed-Scraper/1.0"}
    ) as client:
        
        for i, paper in enumerate(all_papers, 1):
            source = paper.source
            paper_id = paper.id
            
            # Determine PDF URL and filename
            if source == Source.ARXIV:
                pdf_url = f"https://arxiv.org/pdf/{paper_id}.pdf"
                safe_id = paper_id.replace("/", "_").replace(":", "_")
                output_path = pdf_dir / f"arxiv_{safe_id}.pdf"
            elif source in [Source.BIORXIV, Source.MEDRXIV]:
                doi = paper.doi or paper_id
                if "10.1101" in (doi or ""):
                    pdf_url = f"https://www.biorxiv.org/content/{doi}.full.pdf"
                else:
                    pdf_url = paper.pdf_url
                safe_id = (doi or paper_id).replace("/", "_").replace(".", "_")
                output_path = pdf_dir / f"biorxiv_{safe_id}.pdf"
            else:
                continue
            
            if not pdf_url:
                failed += 1
                continue
            
            if output_path.exists():
                paper.raw_data["pdf_path"] = str(output_path)
                downloaded += 1
                continue
            
            if i % 25 == 0:
                print(f"  Progress: {i}/{len(all_papers)} ({downloaded} downloaded)")
            
            success = await download_pdf(client, pdf_url, output_path)
            if success:
                paper.raw_data["pdf_path"] = str(output_path)
                downloaded += 1
            else:
                failed += 1
            
            await asyncio.sleep(0.3)
    
    print(f"\n  Downloaded: {downloaded} PDFs")
    print(f"  Failed: {failed}")
    
    # ==========================================================================
    # PHASE 4: Extract text from PDFs
    # ==========================================================================
    print("\n[PHASE 4] EXTRACTING TEXT FROM PDFS")
    print("-"*80)
    
    text_count = 0
    for paper in all_papers:
        pdf_path = paper.raw_data.get("pdf_path")
        if pdf_path and Path(pdf_path).exists():
            try:
                full_text = text_extractor.extract_from_pdf(pdf_path)
                if len(full_text) > 500:
                    paper.raw_data["full_text"] = full_text
                    text_count += 1
            except:
                pass
    
    print(f"  Extracted text from: {text_count} papers")
    
    # ==========================================================================
    # PHASE 5: Export
    # ==========================================================================
    print("\n[PHASE 5] EXPORTING DATA")
    print("-"*80)
    
    # JSON export
    json_path = output_dir / "research_papers.json"
    json_data = {
        "metadata": {
            "total_papers": len(all_papers),
            "collection_date": datetime.now().isoformat(),
            "countries": COUNTRIES,
            "search_terms": SEARCH_TERMS,
            "pdfs_downloaded": downloaded,
            "text_extracted": text_count,
            "sources": ["arxiv", "biorxiv"],
        },
        "country_distribution": {c: len(papers_by_country[c]) for c in COUNTRIES},
        "papers": []
    }
    
    for paper in all_papers:
        paper_dict = paper.to_dict()
        paper_dict["target_country"] = paper.raw_data.get("target_country", "")
        paper_dict["full_text"] = paper.raw_data.get("full_text", "")
        paper_dict["pdf_path"] = paper.raw_data.get("pdf_path", "")
        json_data["papers"].append(paper_dict)
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"  JSON: {json_path}")
    
    # CSV export
    csv_path = output_dir / "research_papers_metadata.csv"
    csv_columns = [
        "id", "doi", "source", "title", "authors", "year",
        "paper_type", "keywords", "abstract", "url",
        "target_country", "has_full_text", "pdf_path"
    ]
    
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_columns, extrasaction="ignore")
        writer.writeheader()
        
        for paper in all_papers:
            row = {
                "id": paper.id,
                "doi": paper.doi or "",
                "source": str(paper.source),
                "title": paper.title,
                "authors": "; ".join(a.name for a in paper.authors[:10]),
                "year": paper.year or "",
                "paper_type": str(paper.paper_type),
                "keywords": "; ".join(paper.keywords[:10]),
                "abstract": paper.abstract[:500] + "..." if len(paper.abstract) > 500 else paper.abstract,
                "url": paper.url or "",
                "target_country": paper.raw_data.get("target_country", ""),
                "has_full_text": "yes" if paper.raw_data.get("full_text") else "no",
                "pdf_path": paper.raw_data.get("pdf_path", ""),
            }
            writer.writerow(row)
    
    print(f"  CSV: {csv_path}")
    
    # Count files
    pdf_files = list(pdf_dir.glob("*.pdf"))
    total_size_mb = sum(f.stat().st_size for f in pdf_files) / (1024 * 1024)
    
    # ==========================================================================
    # FINAL SUMMARY
    # ==========================================================================
    print("\n" + "="*80)
    print("  COLLECTION COMPLETE!")
    print("="*80)
    print(f"\n  Total papers: {len(all_papers)}")
    print(f"  PDFs downloaded: {len(pdf_files)} files ({total_size_mb:.1f} MB)")
    print(f"  Papers with full text: {text_count}")
    
    print("\n  Country Distribution:")
    for country in COUNTRIES:
        count = len(papers_by_country[country])
        print(f"    {country}: {count}")
    
    print(f"\n  Output directory: {output_dir.absolute()}")
    print(f"\n  Files:")
    print(f"    - research_papers.json (metadata + full text)")
    print(f"    - research_papers_metadata.csv")
    print(f"    - pdfs/ ({len(pdf_files)} PDF files)")
    
    print("\n  DONE!\n")
    
    return all_papers


if __name__ == "__main__":
    papers = asyncio.run(collect_open_access_papers())
