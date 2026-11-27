SHELL := /bin/bash
VENV := .venv
PY := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.DEFAULT_GOAL := help

$(VENV)/bin/python:
	python3 -m venv $(VENV)

.PHONY: help setup dev test lint

help: ## Show the available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-8s %s\n", $$1, $$2}'

setup: $(VENV)/bin/python ## Create the venv and install the backend
	$(PIP) install --quiet --upgrade pip
	$(PIP) install --quiet -e "backend[dev]"

dev: $(VENV)/bin/python ## Run the API on 127.0.0.1:8000
	$(PY) -m uvicorn dabjob.main:app --reload \
		--host "$${DABJOB_HOST:-127.0.0.1}" \
		--port "$${DABJOB_PORT:-8000}"

test: $(VENV)/bin/python ## Run the test suite
	$(PY) -m pytest

lint: $(VENV)/bin/python ## Run ruff and mypy
	$(PY) -m ruff check backend
	$(PY) -m ruff format --check backend
	$(PY) -m mypy backend
