.PHONY: help install dev test lint format run serve docker-up docker-down clean

# Default target
help:
	@echo "PubMed Scraper - Available Commands"
	@echo "===================================="
	@echo "install     - Install production dependencies"
	@echo "dev         - Install development dependencies"
	@echo "test        - Run test suite"
	@echo "lint        - Run linters (ruff, mypy)"
	@echo "format      - Format code (black, ruff)"
	@echo "run         - Run a quick scrape test"
	@echo "serve       - Start API server"
	@echo "docker-up   - Start Docker services"
	@echo "docker-down - Stop Docker services"
	@echo "clean       - Clean build artifacts"

# Installation
install:
	poetry install --no-dev

dev:
	poetry install
	poetry run pre-commit install

# Testing
test:
	poetry run pytest -v --cov=src --cov-report=term-missing

test-unit:
	poetry run pytest tests/unit -v

test-integration:
	poetry run pytest tests/integration -v

# Linting & Formatting
lint:
	poetry run ruff check src tests
	poetry run mypy src

format:
	poetry run black src tests
	poetry run ruff check --fix src tests

# Running
run:
	poetry run python -m src.cli.main scrape "cancer biomarkers" --max 10

serve:
	poetry run uvicorn src.gateway.main:app --reload --host 0.0.0.0 --port 8000

# Docker
docker-up:
	docker-compose up -d
	@echo "Services started. API available at http://localhost:8000"

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-build:
	docker-compose build

# Cleanup
clean:
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf htmlcov
	rm -rf dist
	rm -rf *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
