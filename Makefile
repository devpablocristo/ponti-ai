SHELL := /bin/bash

UVICORN_PORT ?= 8090
COMPOSE ?= docker compose

.PHONY: install up up-ai down build migrate run test train-ml pull-ollama-models smoke smoke-local eval-ml eval-ml-local

install:
	python -m pip install -r requirements.txt

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build
	$(MAKE) migrate

up-ai: up
	$(MAKE) pull-ollama-models

down:
	$(COMPOSE) down

migrate:
	$(COMPOSE) run --rm ai-migrate

run:
	uvicorn app.main:app --reload --port $(UVICORN_PORT)

test:
	python -m pytest

train-ml:
	$(COMPOSE) run --rm ai-copilot python -m ml.scripts.train --activate

pull-ollama-models:
	$(COMPOSE) exec ollama ollama pull llama3.1
	$(COMPOSE) exec ollama ollama pull nomic-embed-text

smoke:
	$(COMPOSE) cp scripts/smoke_endpoints.py ai-copilot:/tmp/smoke_endpoints.py
	$(COMPOSE) exec -T ai-copilot python /tmp/smoke_endpoints.py

smoke-local:
	python scripts/smoke_endpoints.py

eval-ml:
	$(COMPOSE) cp scripts/eval_ml_mvp.py ai-copilot:/tmp/eval_ml_mvp.py
	$(COMPOSE) exec -T ai-copilot python /tmp/eval_ml_mvp.py $(EVAL_ML_ARGS)

eval-ml-local:
	python scripts/eval_ml_mvp.py $(EVAL_ML_ARGS)
