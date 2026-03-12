SHELL := /bin/bash

ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
VENV_DIR := $(ROOT)/.venv
PY := $(VENV_DIR)/bin/python

HOST ?= 127.0.0.1
PORT ?= 9011
FRAMEWORK ?= flask
TOOL ?= py
DURATION ?= 20s
CONNECTIONS ?= 50
THREADS ?= 4

.PHONY: quick soak

quick:
	@PYTHONPATH="$(ROOT):$(ROOT)/src" "$(PY)" -m bench.run quick \
		--framework "$(FRAMEWORK)" \
		--host "$(HOST)" --port "$(PORT)" \
		--tool "$(TOOL)" \
		--duration "$(DURATION)" \
		--connections "$(CONNECTIONS)" \
		--threads "$(THREADS)"

soak:
	@PYTHONPATH="$(ROOT):$(ROOT)/src" "$(PY)" -m bench.run soak \
		--framework "$(FRAMEWORK)" \
		--host "$(HOST)" --port "$(PORT)" \
		--users "$${USERS:-50}" \
		--spawn-rate "$${SPAWN_RATE:-5}" \
		--time "$${TIME:-30m}"
