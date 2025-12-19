.PHONY: help install dev test lint format clean build up down logs shell-app

help:
	@echo "IncidentFox Development Commands"
	@echo ""
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Run in development mode (hot reload)"
	@echo "  make test       - Run tests"
	@echo "  make lint       - Run linters (ruff, mypy)"
	@echo "  make format     - Format code (black, ruff)"
	@echo "  make clean      - Clean temporary files"
	@echo "  make build      - Build Docker image"
	@echo "  make up         - Start with docker-compose"
	@echo "  make down       - Stop docker-compose"
	@echo "  make logs       - View docker-compose logs"
	@echo "  make shell-app  - Shell into app container"
	@echo "  make db-shell   - PostgreSQL shell (if using postgres)"
	@echo ""

install:
	pip install -r requirements.txt

dev:
	uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=src --cov-report=html --cov-report=term

lint:
	ruff check src/
	mypy src/

format:
	black src/ tests/
	ruff check --fix src/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf htmlcov/ .coverage

build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f incidentfox

shell-app:
	docker-compose exec incidentfox /bin/bash

db-shell:
	@echo "Connecting to database..."
	@echo "If using PostgreSQL in docker-compose, add postgres service first"
	# docker-compose exec postgres psql -U postgres -d incidentfox

ngrok:
	@echo "Starting ngrok tunnel on port 8000..."
	@echo "Update GitHub App webhook URL to the ngrok URL"
	ngrok http 8000

setup-dev:
	@echo "Setting up development environment..."
	@if [ ! -f .env ]; then cp .env.example .env; echo "Created .env file - please edit with your credentials"; fi
	@if [ ! -f private-key.pem ]; then echo "⚠️  Please add your GitHub App private key as private-key.pem"; fi
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit .env with your credentials"
	@echo "  2. Add private-key.pem (GitHub App private key)"
	@echo "  3. Run: make install"
	@echo "  4. Run: make dev"
	@echo "  5. Run: make ngrok (in another terminal)"
	@echo ""
