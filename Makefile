SHELL := /bin/bash

UVICORN_PORT ?= 8090
COMPOSE ?= docker compose

.PHONY: install up down build migrate run test pull-ollama-models llm-up llm-pull smoke smoke-local

LOCAL_OLLAMA_DIR ?= /home/pablo/Projects/Pablo/local-infra/ollama

install:
	python -m pip install -r requirements.txt

build:
	$(COMPOSE) build

up:
	@$(MAKE) llm-up
	@$(MAKE) llm-pull
	$(COMPOSE) up -d --build
	$(MAKE) migrate

down:
	$(COMPOSE) down -v --remove-orphans

migrate:
	$(COMPOSE) run --rm ai-migrate

run:
	PYTHONPATH=. uvicorn src.main:create_app --factory --reload --port $(UVICORN_PORT)

test:
	python -m pip install -r requirements.txt
	PYTHONPATH=. python -m pytest

llm-up:
	cd $(LOCAL_OLLAMA_DIR) && docker compose up -d

llm-pull:
	cd $(LOCAL_OLLAMA_DIR) && ./scripts/pull-model.sh gemma4:e4b

pull-ollama-models: llm-pull

smoke:
	$(COMPOSE) cp scripts/smoke_endpoints.py ponti-ai:/tmp/smoke_endpoints.py
	$(COMPOSE) exec -T ponti-ai python /tmp/smoke_endpoints.py

smoke-local:
	python scripts/smoke_endpoints.py
