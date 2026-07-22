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
        docker-native native-deps run native qlab-relay qlab-cue-list qlab-import qlab-stages \
        qlab-sync-durations \
        qlab-light-cue-list qlab-light-import qlab-light-setup qlab-light-patch \
        test test-backend test-frontend visualize-logs analyze-signal-trace prepare-tryout \
        desktop-install

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
	cd "$(ROOT)" && $(COMPOSE) $(COMPOSE_NATIVE) up -d --build --force-recreate postgres redis frontend
	-cd "$(ROOT)" && $(COMPOSE) stop backend
	@echo ""
	@echo "Frontend:  http://localhost:3003"
	@echo "Backend:   noch nicht gestartet — als Nächstes: make native"

run: native-deps ## Docker-Infrastruktur + natives Backend (run-native.sh)
	@echo "=== Backend nativ starten ==="
	cd "$(ROOT)/backend" && ./run-native.sh

native: run ## Alias für make run

desktop-install: ## Start-/Stop-Apps auf dem macOS-Desktop installieren
	"$(ROOT)/tools/desktop/install-desktop-apps.sh"

qlab-relay: ## Pixera + Licht-OSC → QLab (:8990 + :7000 → :53000) — docs/qlab_setup.md
	@if [[ ! -x "$(ROOT)/backend/.venv/bin/python" ]]; then \
		echo "Backend-venv fehlt — zuerst: cd backend && ./run-native.sh (oder make run)" >&2; \
		exit 1; \
	fi
	cd "$(ROOT)/backend" && .venv/bin/python ../tools/pixera_qlab_relay.py -v

qlab-cue-list: ## QLab-Cue-CSV aus OSC-Listen (data/qlab_cue_list_*.csv)
	@if [[ ! -x "$(ROOT)/backend/.venv/bin/python" ]]; then \
		echo "Backend-venv fehlt — zuerst: cd backend && ./run-native.sh (oder make run)" >&2; \
		exit 1; \
	fi
	cd "$(ROOT)/backend" && .venv/bin/python scripts/export_qlab_cue_list.py

qlab-stages: ## QLab Preview-Stages setzen (RZ21→1, Adam→2, Eva→3, LED→4)
	python3 "$(ROOT)/tools/qlab_assign_video_stages.py"

qlab-sync-durations: ## QLab Video-Dauern → Avatar-CSV + video_cues.json (ms genau)
	python3 "$(ROOT)/tools/qlab_sync_durations.py"

qlab-light-cue-list: ## QLab-Licht-Cue-CSV aus light_scenes.json
	@if [[ ! -x "$(ROOT)/backend/.venv/bin/python" ]]; then \
		echo "Backend-venv fehlt — zuerst: cd backend && ./run-native.sh (oder make run)" >&2; \
		exit 1; \
	fi
	cd "$(ROOT)/backend" && .venv/bin/python scripts/export_qlab_light_cue_list.py

qlab-light-setup: ## TMPREVIEW Light-Patch in QLab anlegen (UI-Automation)
	python3 "$(ROOT)/tools/qlab_install_light_patch.py"

qlab-light-patch: qlab-light-setup ## Alias

qlab-light-import: ## Patch + Light-Cues (TMPREVIEW → qlab-light-cue-list → import)
	python3 "$(ROOT)/tools/qlab_install_light_patch.py"
	python3 "$(ROOT)/tools/qlab_import_light_cues.py" "$(ROOT)/data/qlab_light_cue_list.csv"

qlab-import: ## QLab-Cues importieren — make qlab-import VIDEO_DIR=/pfad PROJECTOR=adam SOURCE=all
	@if [[ -z "$(VIDEO_DIR)" ]]; then \
		echo "VIDEO_DIR fehlt — z. B.: make qlab-import VIDEO_DIR=/pfad/zu/videos PROJECTOR=adam" >&2; \
		exit 1; \
	fi
	@SRC="$(SOURCE)"; \
	PROJ="$(PROJECTOR)"; \
	CSV="$(ROOT)/data/qlab_cue_list_all.csv"; \
	if [[ -n "$$PROJ" && "$$PROJ" != "all" ]]; then \
		CMD="python3 \"$(ROOT)/tools/qlab_import_video_cues.py\" \"$(VIDEO_DIR)\" \"$$CSV\" --projector $$PROJ"; \
		if [[ -n "$$SRC" && "$$SRC" != "all" ]]; then CMD="$$CMD --source $$SRC"; fi; \
		$$CMD; \
	elif [[ "$$SRC" == "all" ]]; then \
		for s in avatar atmosphere database; do \
			echo "=== Import $$s (alle Projektoren) ==="; \
			python3 "$(ROOT)/tools/qlab_import_video_cues.py" "$(VIDEO_DIR)" "$$CSV" --source $$s || exit 1; \
		done; \
	else \
		CMD="python3 \"$(ROOT)/tools/qlab_import_video_cues.py\" \"$(VIDEO_DIR)\" \"$$CSV\""; \
		if [[ -n "$$SRC" ]]; then CMD="$$CMD --source $$SRC"; fi; \
		$$CMD; \
	fi

test: test-backend test-frontend ## Backend- und Frontend-Tests

visualize-logs: ## Sendereihenfolge letzter Durchlauf (signal_trace oder osc.log)
	cd "$(ROOT)/backend" && .venv/bin/pip install -q -e ".[viz]"
	cd "$(ROOT)/backend" && MPLCONFIGDIR="$(ROOT)/logs/.mplcache" MPLBACKEND=Agg .venv/bin/python scripts/visualize_show_logs.py \
		--trace "$(ROOT)/logs/signal_trace.jsonl" \
		--osc "$(ROOT)/logs/osc.log" \
		-o "$(ROOT)/logs/show_timeline.png" \
		--report "$(ROOT)/logs/show_timeline.txt"

analyze-signal-trace: ## Drop-Analyse aus logs/signal_trace.jsonl
	@if [[ -s "$(ROOT)/logs/signal_trace.jsonl" ]]; then \
		TRACE="$(ROOT)/logs/signal_trace.jsonl"; \
	elif [[ -s "$(ROOT)/backend/logs/signal_trace.jsonl" ]]; then \
		TRACE="$(ROOT)/backend/logs/signal_trace.jsonl"; \
	else \
		TRACE="$(ROOT)/logs/signal_trace.jsonl"; \
	fi; \
	cd "$(ROOT)/backend" && .venv/bin/python scripts/analyze_signal_trace.py --trace "$$TRACE"

prepare-tryout: ## Logs archivieren, Director auf Probebetrieb, Trace leeren
	cd "$(ROOT)/backend" && .venv/bin/python scripts/prepare_tryout_run.py

run-tryout: prepare-tryout ## Probebetrieb: Script-Cues via API feuern + Analyse
	cd "$(ROOT)/backend" && .venv/bin/python scripts/run_tryout_api.py --max-cues 12
	@$(MAKE) analyze-signal-trace

test-backend: ## pytest via backend/run-tests.sh (venv + deps)
	cd "$(ROOT)/backend" && ./run-tests.sh -q

test-frontend: ## vitest
	cd "$(ROOT)/frontend" && npm test -- --run

avatar-catalog: ## Avatar-Textkatalog aus CSV nach data/avatar_speech.json
	cd "$(ROOT)/backend" && .venv/bin/python -c "from app.services.avatar_speech_catalog import get_avatar_speech_catalog_service; c=get_avatar_speech_catalog_service().load(); print(f'{len(c.cues)} avatar cues cached')"

avatar-import: ## Textzuordnung.numbers → CSV, Video Übersicht, Skript.txt
	cd "$(ROOT)/backend" && .venv/bin/python scripts/import_avatar_textzuordnung.py

video-import: ## Videozuordnung.numbers → OSC ohne Avatare, Video Übersicht, video_cues.json
	cd "$(ROOT)/backend" && .venv/bin/python scripts/import_video_zuordnung.py
