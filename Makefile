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
        dev dev-frontend dev-backend run test test-frontend test-backend clean

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

test-frontend: ## Run frontend (Karma/Jasmine) tests headlessly
	# ChromeHeadlessNoSandbox is provided by the Angular builder; --no-sandbox is
	# required when running as root (CI / web sessions).
	cd $(FRONTEND_DIR) && npm test -- --watch=false --browsers=ChromeHeadlessNoSandbox

clean: ## Remove build artifacts and caches
	rm -rf $(FRONTEND_DIR)/dist $(FRONTEND_DIR)/.angular
	find $(BACKEND_DIR) -type d -name __pycache__ -prune -exec rm -rf {} +
