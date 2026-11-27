SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
NPM := npm --prefix frontend
CONCURRENTLY := frontend/node_modules/.bin/concurrently
ALEMBIC := $(VENV)/bin/alembic

.DEFAULT_GOAL := help

$(VENV)/bin/python:
	python3 -m venv $(VENV)

frontend/node_modules: frontend/package.json
	$(NPM) install

.PHONY: help setup dev test lint check-private migrate demo import-csv

help: ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-14s %s\n", $$1, $$2}'

setup: $(VENV)/bin/python frontend/node_modules ## Create the venv and install both sides
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e "backend[dev]"

dev: $(VENV)/bin/python frontend/node_modules ## Run the API and the Vite dev server together
	$(CONCURRENTLY) -k -n api,web -c blue,green \
		"$(PY) -m uvicorn dabjob.main:app --reload --host $${DABJOB_HOST:-127.0.0.1} --port $${DABJOB_PORT:-8000}" \
		"$(NPM) run dev"

test: $(VENV)/bin/python ## Run the backend test suite
	$(PY) -m pytest backend/tests

migrate: $(VENV)/bin/python ## Apply database migrations
	$(ALEMBIC) -c backend/alembic.ini upgrade head

demo: migrate ## Seed the invented demo dataset
	$(PY) -m dabjob.demo

import-csv: migrate ## Import a CSV or JSON export (FILE=path/to/file.csv)
	$(PY) -m dabjob.tabular "$(FILE)"

check-private: ## Fail if private data looks committed
	$(PY) scripts/check_private_data.py

lint: $(VENV)/bin/python frontend/node_modules check-private ## Run ruff, mypy, tsc and the private-data guard
	$(PY) -m ruff check backend
	$(PY) -m ruff format --check backend
	$(PY) -m mypy backend
	$(NPM) run typecheck
