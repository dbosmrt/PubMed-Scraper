# PubMed Scraper

A distributed microservice-based web crawler for fetching open-source research papers from PubMed, arXiv, bioRxiv, and medRxiv. Includes a modern web interface for easy paper collection.

![PubMed Scraper](PubMed%20Scraper.png)

## Features

- Multi-source scraping from PubMed, arXiv, bioRxiv, and medRxiv
- Web-based user interface with real-time progress tracking
- Intelligent paper classification (Research, Review, Clinical Trial, etc.)
- Advanced filtering by year, country, paper type, and language
- Multiple export formats: CSV, JSON, Parquet, TXT
- RESTful API with async background jobs
- Command-line interface for scripting

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/PubMed-Scraper.git
cd PubMed-Scraper

# Install dependencies
pip install -r requirements.txt

# Install Flask for web interface
pip install flask
```

### Web Interface

The easiest way to use PubMed Scraper is through the web interface:

```bash
python web_app.py
```

Open http://localhost:5000 in your browser. The interface allows you to:
- Enter search queries
- Select data sources (PubMed, arXiv, bioRxiv, or all)
- Filter by country (USA, India, China, Japan)
- Set maximum number of papers
- Download results as JSON or CSV

### Python SDK

```python
import asyncio
from src.crawlers import CrawlerFactory, FilterParams

async def main():
    # Configure filters
    filters = FilterParams(
        year_start=2020,
        year_end=2024,
        max_results=100,
    )

    # Scrape from PubMed
    crawler = CrawlerFactory.get("pubmed")
    papers = []
    
    async with crawler:
        async for paper in crawler.crawl("cancer biomarkers", filters):
            papers.append(paper)
    
    print(f"Found {len(papers)} papers")

asyncio.run(main())
```

### CLI Usage

```bash
# Basic search
python -m src.cli scrape "cancer biomarkers" --max 100

# Multi-source with filters
python -m src.cli scrape "machine learning" \
  --source pubmed \
  --source arxiv \
  --from 2020 \
  --to 2024 \
  --format csv
```

## Architecture

```
+------------------------------------------------------------------+
|                        Client Layer                               |
|              Web UI  |  REST API  |  Python SDK  |  CLI          |
+------------------------------------------------------------------+
                              |
+------------------------------------------------------------------+
|                      API Gateway (Flask/FastAPI)                  |
+------------------------------------------------------------------+
                              |
+------------------------------------------------------------------+
|                    Worker Microservices                           |
|  +-----------+  +-----------+  +-----------+  +-----------+      |
|  |  PubMed   |  |  arXiv    |  | bioRxiv   |  | Classifier|      |
|  |  Crawler  |  |  Crawler  |  |  Crawler  |  |           |      |
|  +-----------+  +-----------+  +-----------+  +-----------+      |
+------------------------------------------------------------------+
```

## Project Structure

```
PubMed-Scraper/
|-- src/
|   |-- crawlers/          # Source-specific crawlers
|   |   |-- base/          # Abstract crawler and rate limiter
|   |   |-- pubmed/        # PubMed E-utilities client
|   |   |-- arxiv/         # arXiv API client
|   |   +-- biorxiv/       # bioRxiv/medRxiv client
|   |-- processors/        # Data processing and classification
|   |-- export/            # Multi-format exporters
|   |-- gateway/           # FastAPI REST API
|   +-- shared/            # Config, constants, exceptions
|-- templates/             # HTML templates for web UI
|-- static/                # CSS and JavaScript for web UI
|-- web_app.py             # Flask web application
|-- requirements.txt       # Python dependencies
+-- tests/                 # Test suite
```

## Supported Paper Types

| Type | Description |
|------|-------------|
| research_article | Original research paper |
| review | Literature review |
| systematic_review | Systematic review |
| meta_analysis | Meta-analysis |
| clinical_trial | Clinical trial |
| randomized_controlled_trial | RCT |
| case_report | Case report |
| preprint | Preprint (not peer-reviewed) |

## Export Formats

| Format | Extension | Best For |
|--------|-----------|----------|
| CSV | .csv | Excel, spreadsheets |
| JSON | .json | APIs, full data structure |
| Parquet | .parquet | Big data analytics |
| TXT | .txt | Human reading |

## Configuration

Create a `.env` file from `.env.example`:

```env
# PubMed API (optional, for higher rate limits)
PUBMED_API_KEY=your-api-key
NCBI_EMAIL=your-email@example.com
```

## Docker Deployment

```bash
# Start all services
docker-compose up -d

# Scale workers
docker-compose up -d --scale worker=4

# Stop services
docker-compose down
```

## Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Web interface |
| `/api/scrape` | POST | Start scraping job |
| `/api/status/<job_id>` | GET | Get job status |
| `/api/papers/<job_id>` | GET | Get scraped papers |
| `/api/download/<job_id>/<format>` | GET | Download results |

## Requirements

- Python 3.10+
- Flask (for web interface)
- httpx (for async HTTP)
- See requirements.txt for full list

## License

LGPL-3.0 - see LICENSE for details.
