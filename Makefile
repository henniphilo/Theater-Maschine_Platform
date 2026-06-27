# Theatermaschine — lokale Entwicklung
#
# Typischer Workflow (Backend nativ für MIDI / macOS say-TTS):
#   make run
#
# Alles in Docker:
#   make up

SHELL := /bin/bash
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
COMPOSE := docker compose
COMPOSE_BASE := -f docker-compose.yml
COMPOSE_NATIVE := $(COMPOSE_BASE) -f docker-compose.native.yml

.DEFAULT_GOAL := help

.PHONY: help setup build up down stop ps logs \
        docker-native native-deps run native \
        test test-backend test-frontend

help: ## Ziele anzeigen
	@echo "Theatermaschine — make targets"
	@echo ""
	@grep -E '^[a-zA-Z0-9_.-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Schnellstart (nativ):  make run"
	@echo "Schnellstart (Docker): make up"

setup: ## backend/.env aus .env.example anlegen (falls fehlend)
	@if [[ ! -f "$(ROOT)/backend/.env" ]]; then \
		cp "$(ROOT)/backend/.env.example" "$(ROOT)/backend/.env"; \
		echo "backend/.env angelegt — bitte API-Keys eintragen."; \
	else \
		echo "backend/.env existiert bereits."; \
	fi

build: ## Docker-Images bauen
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_BASE) build

up: build ## Vollständiger Stack in Docker (Postgres, Redis, Backend, Frontend)
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_BASE) up -d

down: ## Docker-Stack stoppen (ohne natives Backend)
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_NATIVE) down --remove-orphans 2>/dev/null || \
		$(COMPOSE) $(COMPOSE_BASE) down --remove-orphans

stop: ## Alles stoppen (Director, Ports 8000/3003, Docker) — siehe stop.sh
	"$(ROOT)/stop.sh"

ps: ## Laufende Compose-Services
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_NATIVE) ps

logs: ## Docker-Logs (folgen)
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_NATIVE) logs -f

docker-native: native-deps ## Nur Infrastruktur für natives Backend (Postgres, Redis, Frontend)

native-deps: ## Postgres/Redis/Frontend in Docker, Backend-Container aus
	@echo "=== Docker: Postgres, Redis, Frontend (native-Modus) ==="
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_NATIVE) up -d --build postgres redis frontend
	-cd "$(ROOT)" && $(COMPOSE) stop backend
	@echo ""
	@echo "Frontend:  http://localhost:3003"
	@echo "Backend:   noch nicht gestartet — als Nächstes: make native"

run: native-deps ## Docker-Infrastruktur + natives Backend (run-native.sh)
	@echo "=== Backend nativ starten ==="
	cd "$(ROOT)/backend" && ./run-native.sh

native: run ## Alias für make run

test: test-backend test-frontend ## Backend- und Frontend-Tests

test-backend: ## pytest (nutzt Repo data/ via conftest)
	cd "$(ROOT)/backend" && python -m pytest -q

test-frontend: ## vitest
	cd "$(ROOT)/frontend" && npm test -- --run

avatar-catalog: ## Avatar-Textkatalog aus CSV nach data/avatar_speech.json
	cd "$(ROOT)/backend" && .venv/bin/python -c "from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service; c=get_avatar_speech_catalog_service().load(); print(f'{len(c.cues)} avatar cues cached')"

avatar-import: ## Textzuordnung.numbers → CSV, Video Übersicht, Skript.txt
	cd "$(ROOT)/backend" && .venv/bin/python scripts/import_avatar_textzuordnung.py
