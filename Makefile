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

.PHONY: help install install-frontend install-backend build build-frontend build-frontend-e2e \
        dev dev-frontend dev-backend dev-fake run run-e2e test test-frontend test-backend test-cosmos \
        test-e2e e2e-seed e2e-teardown test-scripts \
        lint lint-frontend lint-backend typecheck typecheck-frontend \
        typecheck-backend gen-types coverage coverage-frontend coverage-backend clean

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

build-frontend-e2e: ## Build the SPA with the e2e configuration (MSAL disabled — EX-1/D-22)
	cd $(FRONTEND_DIR) && npm run build -- --configuration e2e

## ---- run --------------------------------------------------------------------

run: build-frontend ## Production-like: FastAPI serves the built SPA on $(PORT)
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

run-e2e: build-frontend-e2e ## E2E-mode run: e2e SPA + FastAPI with the env-gated auth bypass
	# Playwright の webServer / CI から呼ぶ導線（EX-1・D-22）。COSMOS_* と
	# E2E_AUTH_BYPASS / E2E_AUTH_OID は呼び出し側が環境変数で渡す。ここで既定値を
	# 埋めない（バイパスの誤有効化を避けるため、旗は明示的に渡させる）。
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --host 0.0.0.0 --port $(PORT)

dev: ## Live-reload: run frontend and backend together (Ctrl-C stops both)
	@echo "Starting FastAPI (:$(PORT)) and Angular (:4200, proxies /api)…"
	@$(MAKE) -j2 dev-backend dev-frontend

dev-backend: ## Run FastAPI with autoreload
	cd $(BACKEND_DIR) && uv run uvicorn app.main:app --reload --port $(PORT)

dev-frontend: ## Run the Angular dev server with the /api proxy
	cd $(FRONTEND_DIR) && npm start

dev-fake: ## Dev-only smoke harness: API on $(PORT) with an in-memory store + stub auth
	# サインイン・Cosmos なしで API を叩くための使い捨てサーバー（非永続）。本番の入口は
	# main.py（make run/dev）。dev-fake はスモーク確認専用で B-14 ゲスト経路とは別物。
	PORT=$(PORT) uv run --project $(BACKEND_DIR) python scripts/dev_server.py

## ---- test -------------------------------------------------------------------

test: test-backend test-frontend test-scripts ## Run all tests

test-backend: ## Run backend (pytest) tests
	cd $(BACKEND_DIR) && uv run pytest

test-scripts: ## Run repo tooling tests (coverage report script; stdlib only, no deps)
	# PR コメントの「事実」を組み立てる scripts/coverage/ の純粋関数を検証する（EX-2/D-23）。
	# stdlib のみなので uv/npm 不要。ここが壊れると Δ・patch coverage の表示が静かに誤る。
	python3 -m unittest discover -s scripts/coverage/tests -t scripts/coverage/tests

test-cosmos: ## Run layer-3 Cosmos contract tests (needs a running emulator; see conftest)
	# Point COSMOS_ENDPOINT / COSMOS_KEY / COSMOS_DATABASE at an emulator first.
	# Without them the suite skips (so plain `make test-backend` stays Cosmos-free).
	cd $(BACKEND_DIR) && uv run pytest -m cosmos --no-cov

test-e2e: ## Run Playwright E2E flows (layer 4). Boots the app via webServer; needs a Cosmos emulator.
	# Set COSMOS_ENDPOINT/KEY/DATABASE (emulator) first. The Playwright globalSetup seeds
	# prd_test_<E2E_RUN_ID> and globalTeardown purges it (EX-1/D-22). Auth is bypassed via
	# the env-gated resolver (webServer sets E2E_AUTH_BYPASS=1).
	cd $(FRONTEND_DIR) && npm run e2e

e2e-seed: ## Seed the E2E isolated partition (needs COSMOS_* + E2E_RUN_ID + E2E_AUTH_OID — EX-1/D-22)
	uv run --project $(BACKEND_DIR) python scripts/e2e_seed.py

e2e-teardown: ## Physically delete the E2E isolated partition (needs COSMOS_* + E2E_RUN_ID — EX-1/D-22)
	uv run --project $(BACKEND_DIR) python scripts/e2e_teardown.py

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

## ---- type generation --------------------------------------------------------

gen-types: ## Generate frontend TS types from the backend OpenAPI schema (D-20)
	# OpenAPI（FastAPI が出力）を単一の真実とし、フロントの型を生成する。手書きに
	# しないのは Python と TS で 2 つの真実が生まれるため。生成物 schema.d.ts はコミット
	# し、CI が再生成して差分を検出する（生成し忘れを弾く）。
	uv run --project $(BACKEND_DIR) python scripts/gen_openapi.py $(FRONTEND_DIR)/openapi.json
	cd $(FRONTEND_DIR) && npm run gen:types

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
