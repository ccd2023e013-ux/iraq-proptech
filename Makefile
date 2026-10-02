SHELL := /bin/bash
BACKEND := cd backend &&
VENV := .venv/bin
FRONTEND := cd frontend &&
COMPOSE_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml

.DEFAULT_GOAL := help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

# --- Codespaces / native ---------------------------------------------------
api: ## Run the FastAPI dev server on :8000 (auto-reload)
	$(BACKEND) $(VENV)/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

web: ## Run the Next.js dev server on :3000
	$(FRONTEND) npm run dev -- --hostname 0.0.0.0

worker: ## Run the Celery worker
	$(BACKEND) $(VENV)/celery -A app.workers.celery_app worker --loglevel=INFO

migrate: ## Apply database migrations
	$(BACKEND) $(VENV)/alembic upgrade head

migration: ## Create a migration: make migration m="describe change"
	$(BACKEND) $(VENV)/alembic revision --autogenerate -m "$(m)"

test: test-backend test-frontend ## Run all tests

test-backend: ## Backend tests (needs PostGIS for db tests)
	$(BACKEND) $(VENV)/pytest

test-frontend: ## Frontend unit/component tests
	$(FRONTEND) npm test

lint: ## Lint + type-check everything
	$(BACKEND) $(VENV)/ruff check . && $(VENV)/ruff format --check . && $(VENV)/mypy app
	$(FRONTEND) npm run lint && npm run typecheck && npm run format:check

format: ## Auto-format everything
	$(BACKEND) $(VENV)/ruff check --fix . && $(VENV)/ruff format .
	$(FRONTEND) npm run format

build: ## Production build of the frontend
	$(FRONTEND) npm run build

# --- Docker ---------------------------------------------------------------
up: ## Full stack in Docker (dev mode, hot reload)
	$(COMPOSE_DEV) up --build

down: ## Stop the Docker stack
	$(COMPOSE_DEV) down

.PHONY: help api web worker migrate migration test test-backend test-frontend lint format build up down
