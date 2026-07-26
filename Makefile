# Scrum Board — developer entrypoints
#
# Two ways to run locally:
#   make dev    Live-reload dev servers (Angular :4200 proxies /api -> FastAPI :8000)
#   make run    Production-like: build the SPA, then FastAPI serves it on :8000
#
# `make dev` is for day-to-day work. `make run` mirrors the single-App-Service
# co-hosting used in production (one origin, no CORS).

FRONTEND_DIR := frontend
BACKEND_DIR  := backend
PORT         ?= 8000

.PHONY: help install install-frontend install-backend build build-frontend \
        dev dev-frontend dev-backend run test test-frontend test-backend \
        lint lint-frontend lint-backend typecheck typecheck-frontend \
        typecheck-backend coverage coverage-frontend coverage-backend clean

help:
	@grep -E '^[a-zA-Z_-]+:.*?##' $(MAKEFILE_LIST) | \
		awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

## ---- install ----------------------------------------------------------------

install: install-frontend install-backend ## Install all dependencies

install-frontend: ## Install frontend (npm) dependencies
	cd $(FRONTEND_DIR) && npm install

install-backend: ## Install backend (uv) dependencies into a local venv
	cd $(BACKEND_DIR) && uv sync --extra dev

## ---- build ------------------------------------------------------------------

build: build-frontend ## Build the production SPA bundle

build-frontend: ## Build the Angular SPA into frontend/dist
	cd $(FRONTEND_DIR) && npm run build

## ---- run --------------------------------------------------------------------

run: build-frontend ## Production-like: FastAPI serves the built SPA on $(PORT)
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

dev: ## Live-reload: run frontend and backend together (Ctrl-C stops both)
	@echo "Starting FastAPI (:$(PORT)) and Angular (:4200, proxies /api)…"
	@$(MAKE) -j2 dev-backend dev-frontend

dev-backend: ## Run FastAPI with autoreload
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --port $(PORT)

dev-frontend: ## Run the Angular dev server with the /api proxy
	cd $(FRONTEND_DIR) && npm start

## ---- test -------------------------------------------------------------------

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend (pytest) tests
	cd $(BACKEND_DIR) && uv run pytest

test-frontend: ## Run frontend (Vitest, jsdom) tests headlessly
	# Vitest runs on jsdom (no real browser), so nothing browser-specific is needed
	# and CI stays stable. See D-19; Karma/Jasmine was retired in B-11.
	cd $(FRONTEND_DIR) && npm test

## ---- lint / typecheck -------------------------------------------------------

lint: lint-backend lint-frontend ## Run all linters

lint-backend: ## Lint backend (ruff check + format check)
	cd $(BACKEND_DIR) && uv run ruff check . && uv run ruff format --check .

lint-frontend: ## Lint frontend (ESLint)
	cd $(FRONTEND_DIR) && npm run lint

typecheck: typecheck-backend typecheck-frontend ## Run all type checks

typecheck-backend: ## Type-check backend (mypy)
	cd $(BACKEND_DIR) && uv run mypy

typecheck-frontend: ## Type-check frontend (tsc --noEmit)
	cd $(FRONTEND_DIR) && npm run typecheck

## ---- coverage ---------------------------------------------------------------

coverage: coverage-backend coverage-frontend ## Run all tests with coverage reports

coverage-backend: ## Backend coverage (term + HTML in backend/htmlcov)
	cd $(BACKEND_DIR) && uv run pytest --cov-report=html

coverage-frontend: ## Frontend coverage (text-summary + HTML in frontend/coverage)
	cd $(FRONTEND_DIR) && npm run coverage

## ---- clean ------------------------------------------------------------------

clean: ## Remove build artifacts and caches
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.angular $(FRONTEND_DIR)/coverage
	rm -rf $(BACKEND_DIR)/htmlcov $(BACKEND_DIR)/coverage.xml $(BACKEND_DIR)/.coverage
	find $(BACKEND_DIR) -type d -name __pycache__ -prune -exec rm -rf {} +
