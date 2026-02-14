SHELL := /bin/bash

UVICORN_PORT ?= 8090
COMPOSE ?= docker compose

.PHONY: install up down build migrate run test pull-ollama-models smoke smoke-local

install:
	python -m pip install -r requirements.txt

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build
	$(MAKE) migrate
	$(MAKE) pull-ollama-models

down:
	$(COMPOSE) down -v --remove-orphans

migrate:
	$(COMPOSE) run --rm ai-migrate

run:
	uvicorn app.main:app --reload --port $(UVICORN_PORT)

test:
	PYTHONPATH=. python -m pytest

pull-ollama-models:
	$(COMPOSE) exec ollama ollama pull llama3.1

smoke:
	$(COMPOSE) cp scripts/smoke_endpoints.py ai-copilot:/tmp/smoke_endpoints.py
	$(COMPOSE) exec -T ai-copilot python /tmp/smoke_endpoints.py

smoke-local:
	python scripts/smoke_endpoints.py
