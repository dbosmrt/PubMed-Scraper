"""
Test script to scrape 15 biotechnology research papers from all open-source sites
and download full papers as PDF, JSON, and TXT.
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from src.crawlers import CrawlerFactory, FilterParams
from src.download import PaperDownloader, text_extractor
from src.processors import PaperClassifier
from src.export import ExportManager
from src.shared.constants import PaperType, Source


async def scrape_full_papers():
    """
    Scrape 15 biotechnology research papers from multiple sources
    and download full paper content.
    """
    
    print("\n" + "="*70)
    print("  PUBMED SCRAPER - Full Paper Download")
    print("  Fetching 15 Biotechnology Research Papers")
    print("="*70)
    
    classifier = PaperClassifier(use_ml=False)
    output_dir = Path("output/biotech_full_papers")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Track collected papers
    all_papers = []
    target_count = 15
    
    # Sources to scrape (prioritize open-access sources)
    # Using broader queries that will return more results
    sources_queries = [
        (Source.ARXIV, "all:biotechnology OR all:bioinformatics OR all:genomics", 10),
        (Source.BIORXIV, "biotechnology", 8),
        (Source.PUBMED, "biotechnology[Title]", 10),  # PMC papers
    ]
    
    print("\n[1/4] SEARCHING FOR PAPERS")
    print("-"*70)
    
    for source, query, max_papers in sources_queries:
        if len(all_papers) >= target_count:
            break
            
        print(f"\n  Searching {source.value}...")
        
        filters = FilterParams(
            max_results=max_papers * 3,  # Fetch more to filter
            languages=[],
        )
        
        try:
            crawler = CrawlerFactory.get(source)
            papers_from_source = 0
            
            async with crawler:
                async for paper in crawler.crawl(query, filters):
                    if len(all_papers) >= target_count:
                        break
                    if papers_from_source >= max_papers:
                        break
                    
                    # Classify paper
                    paper.paper_type = classifier.classify(paper)
                    
                    # Only include research papers (skip reviews, editorials, etc.)
                    if paper.paper_type in [PaperType.RESEARCH_ARTICLE, PaperType.PREPRINT, PaperType.UNKNOWN]:
                        all_papers.append(paper)
                        papers_from_source += 1
                        print(f"    [{len(all_papers):2d}] {paper.title[:55]}...")
            
            print(f"  Found {papers_from_source} papers from {source.value}")
            
        except Exception as e:
            print(f"  Error with {source.value}: {e}")
    
    print(f"\n  Total papers collected: {len(all_papers)}")
    
    # Download PDFs
    print("\n[2/4] DOWNLOADING FULL PAPERS (PDFs)")
    print("-"*70)
    
    pdf_dir = output_dir / "pdfs"
    pdf_dir.mkdir(exist_ok=True)
    
    downloaded_papers = []
    
    async with PaperDownloader(output_dir=pdf_dir) as downloader:
        for i, paper in enumerate(all_papers, 1):
            print(f"  [{i:2d}/{len(all_papers)}] Downloading: {paper.id}...", end=" ")
            
            pdf_path = await downloader.download_pdf(paper)
            
            if pdf_path and pdf_path.exists():
                paper.raw_data["pdf_path"] = str(pdf_path)
                paper.raw_data["has_full_text"] = True
                downloaded_papers.append((paper, pdf_path))
                print(f"OK ({pdf_path.stat().st_size // 1024} KB)")
            else:
                print("SKIPPED (not available)")
    
    print(f"\n  Downloaded: {len(downloaded_papers)}/{len(all_papers)} papers")
    
    # Extract text from PDFs
    print("\n[3/4] EXTRACTING FULL TEXT FROM PDFs")
    print("-"*70)
    
    papers_with_text = []
    
    for paper, pdf_path in downloaded_papers:
        print(f"  Extracting: {paper.id}...", end=" ")
        
        try:
            full_text = text_extractor.extract_from_pdf(pdf_path)
            
            if full_text and len(full_text) > 500:
                paper.raw_data["full_text"] = full_text
                paper.raw_data["text_length"] = len(full_text)
                papers_with_text.append(paper)
                print(f"OK ({len(full_text):,} chars)")
            else:
                print("SKIPPED (insufficient text)")
                
        except Exception as e:
            print(f"ERROR: {e}")
    
    print(f"\n  Extracted text: {len(papers_with_text)}/{len(downloaded_papers)} papers")
    
    # Export results
    print("\n[4/4] EXPORTING RESULTS")
    print("-"*70)
    
    # 1. Export metadata + full text as JSON
    json_path = output_dir / "biotech_papers_full.json"
    json_data = {
        "metadata": {
            "total_papers": len(papers_with_text),
            "sources": list(set(str(p.source) for p in papers_with_text)),
            "includes_full_text": True,
        },
        "papers": []
    }
    
    for paper in papers_with_text:
        paper_dict = paper.to_dict()
        paper_dict["full_text"] = paper.raw_data.get("full_text", "")
        paper_dict["pdf_path"] = paper.raw_data.get("pdf_path", "")
        json_data["papers"].append(paper_dict)
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"  JSON (with full text): {json_path}")
    
    # 2. Export as TXT (human-readable with full abstracts)
    txt_path = output_dir / "biotech_papers_full.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("="*70 + "\n")
        f.write("  BIOTECHNOLOGY RESEARCH PAPERS - FULL COLLECTION\n")
        f.write(f"  Total Papers: {len(papers_with_text)}\n")
        f.write("="*70 + "\n\n")
        
        for i, paper in enumerate(papers_with_text, 1):
            f.write(f"\n{'='*70}\n")
            f.write(f"PAPER {i}: {paper.title}\n")
            f.write(f"{'='*70}\n\n")
            
            f.write(f"ID: {paper.id}\n")
            f.write(f"Source: {paper.source}\n")
            if paper.doi:
                f.write(f"DOI: {paper.doi}\n")
            f.write(f"Year: {paper.year}\n")
            f.write(f"Type: {paper.paper_type}\n")
            
            if paper.authors:
                authors = ", ".join(a.name for a in paper.authors[:5])
                if len(paper.authors) > 5:
                    authors += f" et al. ({len(paper.authors)} total)"
                f.write(f"Authors: {authors}\n")
            
            if paper.journal:
                f.write(f"Journal: {paper.journal}\n")
            
            f.write(f"URL: {paper.url}\n")
            f.write(f"PDF: {paper.raw_data.get('pdf_path', 'N/A')}\n")
            
            f.write(f"\n--- ABSTRACT ---\n{paper.abstract}\n")
            
            full_text = paper.raw_data.get("full_text", "")
            if full_text:
                # Include first 5000 chars of full text
                preview = full_text[:5000]
                if len(full_text) > 5000:
                    preview += f"\n\n[... truncated, full text: {len(full_text):,} characters ...]"
                f.write(f"\n--- FULL TEXT PREVIEW ---\n{preview}\n")
    
    print(f"  TXT (readable): {txt_path}")
    
    # 3. List PDF files
    pdf_files = list(pdf_dir.glob("*.pdf"))
    print(f"  PDFs: {pdf_dir}/ ({len(pdf_files)} files)")
    
    # Summary
    print("\n" + "="*70)
    print("  SUMMARY")
    print("="*70)
    print(f"  Papers scraped: {len(all_papers)}")
    print(f"  PDFs downloaded: {len(downloaded_papers)}")
    print(f"  Full text extracted: {len(papers_with_text)}")
    print(f"\n  Output directory: {output_dir.absolute()}")
    print("="*70)
    
    print("\n  Output Files:")
    print(f"    - {len(pdf_files)} PDF files in pdfs/")
    print(f"    - biotech_papers_full.json (metadata + full text)")
    print(f"    - biotech_papers_full.txt (human readable)")
    
    print("\n  DONE!\n")
    
    return papers_with_text


if __name__ == "__main__":
    papers = asyncio.run(scrape_full_papers())
