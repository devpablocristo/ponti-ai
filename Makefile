SHELL := /bin/bash

UVICORN_PORT ?= 8090
COMPOSE ?= docker compose

.PHONY: install up down build migrate run test

install:
	python -m pip install -r requirements.txt

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

migrate:
	$(COMPOSE) run --rm ai-migrate

run:
	uvicorn app.main:app --reload --port $(UVICORN_PORT)

test:
	python -m pytest
