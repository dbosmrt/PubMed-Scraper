# PubMed Scraper - Celery Worker Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry

# Copy dependency files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY src/ ./src/
COPY .env.example .env

# Create output directory
RUN mkdir -p output

# Run Celery worker
CMD ["celery", "-A", "src.orchestration.scheduler", "worker", "--loglevel=info", "--concurrency=4"]
