SHELL := /bin/bash

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
VENV_DIR := $(ROOT)/.venv
PY := $(VENV_DIR)/bin/python
PIP := $(PY) -m pip

.PHONY: help venv bench-flask bench-fastapi bench-sanic bench-all bench-soak

help:
	@echo "Targets:"
	@echo "  venv        Create .venv + install deps"
	@echo "  bench-flask Run quick benchmark (Flask) on/off"
	@echo "  bench-fastapi Run quick benchmark (FastAPI) on/off"
	@echo "  bench-sanic Run quick benchmark (Sanic) on/off"
	@echo "  bench-all   Run quick benchmarks for all frameworks"
	@echo "  bench-soak  Run Locust soak on/off"

venv:
	@python3 -m venv "$(VENV_DIR)"
	@$(PIP) install -U pip
	@cd "$(ROOT)" && $(PIP) install -e ".[all,dev]"
	@$(PIP) install -r "$(ROOT)/bench/requirements-bench.txt"

bench-flask: venv
	@$(MAKE) -C bench quick FRAMEWORK=flask

bench-fastapi: venv
	@$(MAKE) -C bench quick FRAMEWORK=fastapi

bench-sanic: venv
	@$(MAKE) -C bench quick FRAMEWORK=sanic

bench-all: venv
	@$(MAKE) -C bench quick FRAMEWORK=flask
	@$(MAKE) -C bench quick FRAMEWORK=fastapi
	@$(MAKE) -C bench quick FRAMEWORK=sanic

bench-soak: venv
	@$(MAKE) -C bench soak FRAMEWORK=fastapi
