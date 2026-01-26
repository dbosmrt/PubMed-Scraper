"""
PubMed Scraper - Web Application

A modern Flask web application providing a user-friendly interface
for the PubMed research paper scraper.
"""

import asyncio
import json
import sys
import uuid
import threading
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, send_file

sys.path.insert(0, ".")

from src.crawlers import CrawlerFactory, FilterParams
from src.processors import PaperClassifier
from src.shared.constants import PaperType, Source

app = Flask(__name__)

# Store active jobs and their progress
jobs = {}

# Country keywords for filtering
COUNTRY_KEYWORDS = {
    "USA": ["united states", "usa", "u.s.", "america", "california", "new york", 
            "texas", "massachusetts", "maryland", "illinois", "harvard", "mit", 
            "stanford", "yale", "princeton", "nih", "berkeley", "ucla"],
    "IND": ["india", "indian", "mumbai", "delhi", "bangalore", "bengaluru", "chennai", 
            "hyderabad", "kolkata", "pune", "iit ", "iisc", "aiims", "csir"],
    "CHN": ["china", "chinese", "beijing", "shanghai", "guangzhou", "shenzhen", 
            "wuhan", "nanjing", "peking university", "tsinghua", "fudan"],
    "JPN": ["japan", "japanese", "tokyo", "osaka", "kyoto", "nagoya", 
            "university of tokyo", "riken", "keio", "waseda"],
}


def detect_country(paper) -> str:
    """Detect country from paper affiliations."""
    affiliation_text = " ".join(
        (a.affiliation or "") + " " + (a.country or "") 
        for a in paper.authors
    ).lower()
    
    if paper.countries:
        affiliation_text += " " + " ".join(paper.countries).lower()
    
    for country, keywords in COUNTRY_KEYWORDS.items():
        if any(kw in affiliation_text for kw in keywords):
            return country
    
    return "OTHER"


async def run_scraper(job_id: str, query: str, source: str, country: str, max_papers: int):
    """Run the scraper asynchronously."""
    job = jobs[job_id]
    job["status"] = "running"
    job["message"] = "Initializing scraper..."
    
    classifier = PaperClassifier(use_ml=False)
    papers = []
    
    try:
        # Determine which sources to use
        if source == "all":
            sources = [Source.PUBMED, Source.ARXIV, Source.BIORXIV]
        else:
            sources = [Source(source.lower())]
        
        job["message"] = f"Searching {len(sources)} source(s)..."
        
        for src in sources:
            if len(papers) >= max_papers:
                break
                
            job["message"] = f"Crawling {src.value}..."
            crawler = CrawlerFactory.get(src)
            
            async with crawler:
                # Build query based on source
                if src == Source.PUBMED:
                    search_query = f"{query}[Title/Abstract]"
                elif src == Source.ARXIV:
                    search_query = f"all:{query}"
                else:
                    search_query = query
                
                filters = FilterParams(max_results=max_papers * 2, languages=[])
                
                try:
                    async for paper in crawler.crawl(search_query, filters):
                        if len(papers) >= max_papers:
                            break
                        
                        # Classify paper
                        paper.paper_type = classifier.classify(paper)
                        if paper.paper_type in [PaperType.REVIEW, PaperType.EDITORIAL]:
                            continue
                        
                        # Detect country
                        paper_country = detect_country(paper)
                        
                        # Filter by country if specified
                        if country != "all" and paper_country != country.upper():
                            continue
                        
                        # Convert to dict
                        paper_dict = {
                            "id": paper.id,
                            "title": paper.title,
                            "authors": "; ".join(a.name for a in paper.authors[:5]),
                            "journal": paper.journal or "",
                            "year": paper.year or "",
                            "abstract": paper.abstract[:300] + "..." if len(paper.abstract) > 300 else paper.abstract,
                            "url": paper.url or "",
                            "doi": paper.doi or "",
                            "source": str(src.value),
                            "country": paper_country,
                            "paper_type": str(paper.paper_type.value) if paper.paper_type else "",
                        }
                        
                        papers.append(paper_dict)
                        job["papers"] = papers
                        job["progress"] = len(papers)
                        job["message"] = f"Found {len(papers)} papers from {src.value}..."
                        
                except Exception as e:
                    job["message"] = f"Error with {src.value}: {str(e)[:50]}"
        
        # Save results
        output_dir = Path("output/web_scraper")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save JSON
        json_path = output_dir / f"papers_{job_id}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "metadata": {
                    "query": query,
                    "source": source,
                    "country": country,
                    "total": len(papers),
                    "date": datetime.now().isoformat(),
                },
                "papers": papers
            }, f, indent=2, ensure_ascii=False)
        
        # Save CSV
        csv_path = output_dir / f"papers_{job_id}.csv"
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            if papers:
                writer = csv.DictWriter(f, fieldnames=papers[0].keys())
                writer.writeheader()
                writer.writerows(papers)
        
        job["status"] = "completed"
        job["message"] = f"Completed! Found {len(papers)} papers."
        job["json_path"] = str(json_path)
        job["csv_path"] = str(csv_path)
        
    except Exception as e:
        job["status"] = "error"
        job["message"] = f"Error: {str(e)}"


def run_async_scraper(job_id: str, query: str, source: str, country: str, max_papers: int):
    """Wrapper to run async scraper in a thread."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_scraper(job_id, query, source, country, max_papers))
    finally:
        loop.close()


@app.route("/")
def index():
    """Serve the main page."""
    return render_template("index.html")


@app.route("/api/scrape", methods=["POST"])
def start_scrape():
    """Start a new scraping job."""
    data = request.json
    
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id": job_id,
        "status": "starting",
        "progress": 0,
        "max_papers": data.get("max_papers", 100),
        "message": "Starting scraper...",
        "papers": [],
        "query": data.get("query", "biotechnology"),
        "source": data.get("source", "pubmed"),
        "country": data.get("country", "all"),
    }
    
    # Start scraper in background thread
    thread = threading.Thread(
        target=run_async_scraper,
        args=(job_id, data.get("query", "biotechnology"), 
              data.get("source", "pubmed"),
              data.get("country", "all"),
              data.get("max_papers", 100))
    )
    thread.daemon = True
    thread.start()
    
    return jsonify({"job_id": job_id})


@app.route("/api/status/<job_id>")
def get_status(job_id):
    """Get job status."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    return jsonify({
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "max_papers": job["max_papers"],
        "message": job["message"],
        "paper_count": len(job.get("papers", [])),
    })


@app.route("/api/papers/<job_id>")
def get_papers(job_id):
    """Get scraped papers."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    return jsonify({
        "papers": job.get("papers", []),
        "total": len(job.get("papers", [])),
    })


@app.route("/api/download/<job_id>/<format>")
def download_results(job_id, format):
    """Download results as JSON or CSV."""
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job not found"}), 404
    
    if format == "json":
        path = job.get("json_path")
        if path and Path(path).exists():
            return send_file(path, as_attachment=True, download_name=f"papers_{job_id}.json")
    elif format == "csv":
        path = job.get("csv_path")
        if path and Path(path).exists():
            return send_file(path, as_attachment=True, download_name=f"papers_{job_id}.csv")
    
    return jsonify({"error": "File not ready"}), 400


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  PubMed Scraper - Web Application")
    print("="*60)
    print("\n  Starting server at http://localhost:5000")
    print("  Press Ctrl+C to stop\n")
    app.run(debug=True, port=5000)
