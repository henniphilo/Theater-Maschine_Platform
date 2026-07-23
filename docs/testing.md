# Testing — Theater-Maschine

**Zweck:** Vor dem Plattform-Umbau den aktuellen Zustand reproduzierbar absichern.  
**Bezug:** [platform-audit.md](platform-audit.md) · [platform-prd.md](platform-prd.md) · Meilenstein *Platform Foundation*

Alle automatisierten Tests laufen mit `OSC_DRY_RUN=true` (gesetzt durch `backend/run-tests.sh` und `backend/tests/conftest.py`). **Niemals** Live-Hardware in pytest ohne Fake-Receiver.

---

## Schnellübersicht

| Aktion | Befehl |
|--------|--------|
| Alles (Backend + Frontend) | `make test` |
| Backend (ruff + pytest) | `make test-backend` |
| Foundation-Smoke | `make test-smoke` |
| Frontend (vitest) | `make test-frontend` |
| Stack starten (Docker) | `make up` |
| Stack starten (natives Backend) | `make run` |
| Alles stoppen | `make stop` |

---

## Docker-Testablauf

Backend- und Frontend-Unit-Tests brauchen **keinen** laufenden Docker-Stack. Sie nutzen `TestClient` bzw. Vitest lokal.

Wenn du den **laufenden Stack** gegen die API prüfen willst:

```bash
make setup          # einmalig: backend/.env anlegen
make up             # Postgres, Redis, Backend, Frontend in Docker
# Health manuell: curl -s http://localhost:8000/api/v1/health
make stop           # danach alles beenden
```

Hinweise:

- Compose kann produktionsnahe Defaults setzen (`OSC_DRY_RUN=false`, Venue-Hosts). Für manuelle API-Checks lokal Dry-Run in `backend/.env` belassen bzw. prüfen.
- MIDI und macOS `say` stehen im reinen Docker-Backend **nicht** zur Verfügung.
- Automatisierte Regression: weiter `make test-backend` / `make test-frontend` (ohne `make up`).

CI-Parität (`.github/workflows/ci.yml`):

- Backend: `ruff check app tests` + `pytest` mit `OSC_DRY_RUN=true`
- Frontend: `npm run lint` + `npm test -- --run` + `npm run build`

---

## Nativer Backend-Testablauf

Empfohlen für Entwickler auf dem Mac (MIDI → Ableton, macOS `say`):

```bash
make setup
make test-backend   # venv, ruff, pytest via backend/run-tests.sh
```

`backend/run-tests.sh`:

1. legt bei Bedarf `.venv` mit Python 3.11 an  
2. installiert `.[dev]`  
3. setzt `OSC_DRY_RUN=true` und `OSC_HOST=127.0.0.1`  
4. führt `ruff check app tests` und danach `pytest` aus  

Nur Foundation-Smoke:

```bash
make test-smoke
# gleichwertig:
cd backend && ./run-tests.sh tests/test_platform_foundation_smoke.py -q
```

Laufendes natives Backend (nicht für Unit-Tests nötig):

```bash
make run            # Docker: Postgres/Redis/Frontend + natives Backend
# API: http://localhost:8000
make stop
```

Daten/Logs liegen im Repo-Root unter `data/` und `logs/` (siehe `backend/run-native.sh`).

---

## Frontend: Lint und TypeScript-Check

```bash
cd frontend
npm install         # einmalig / nach Dependency-Änderungen
npm run lint        # next lint (ESLint)
npm test -- --run   # vitest — auch: make test-frontend
npm run build       # Next.js-Build inkl. TypeScript-Prüfung (wie CI)
```

Es gibt kein separates `tsc --noEmit`-Script; der TypeScript-Check läuft über `npm run build` (CI-Schritt *Build*).

---

## Platform-Foundation-Smoke

Datei: `backend/tests/test_platform_foundation_smoke.py`

| Test | Prüft |
|------|--------|
| Health | `GET /api/v1/health` → `{"status":"ok"}` |
| Director-Status | `GET /api/v1/director/status` inkl. Safety-Felder |
| Medienkonfiguration | `GET /api/v1/media/catalog` (Videos, Projektoren, Sounds, Lights) |
| Cue Dry-Run | `POST /api/v1/director/osc-test` mit `dry_run=true` und geplanten Messages |

Diese Suite ist die minimale Baseline vor Domänen-/Pack-Umbauten. Bestehende Detailtests bleiben unverändert.

---

## Bekannte Hardwareabhängigkeiten

| Abhängigkeit | Wann nötig | Tests |
|--------------|------------|--------|
| **Pixera** (OSC, oft `PIXERA_OSC_*`) | Live-Visuals | Dry-Run / Fake-Receiver — kein echtes Pixera |
| **TouchDesigner** (`OSC_HOST`/`OSC_PORT`) | Legacy-/Mirror-Visuals | Dry-Run |
| **Ableton + MIDI** (`SOUND_MIDI_PORT`, IAC) | Sound live | nur natives Backend; Tests mocken MIDI. Volles `make test-backend` braucht ggf. Systemzugriff auf MIDI (rtmidi); in stark eingeschränkten Sandboxes kann `get_devices` abbrechen |
| **Licht-Pult** TCP/EOS (`LIGHT_TCP_*`) | Live-Licht | Dry-Run / Mocks; echte IP nie in Tests |
| **QLab** (Relay/Import-Tools) | Preview-Pfad | Makefile-Targets; nicht Kern der pytest-Suite |
| **macOS `say`** | TTS nativ | Docker nutzt edge-tts; Unit-Tests ohne Sprachausgabe |
| **Postgres** | Chat/Conversations | Director-/Medien-Smoke ohne DB-Schreiben; Stack braucht Postgres für vollen Betrieb |
| **Redis** | Compose vorhanden | in App-Code kaum genutzt; für Unit-Tests nicht erforderlich |

Sicherheitsregeln:

- Secrets nur in `backend/.env` — nie committen  
- `OSC_DRY_RUN=false` nur bewusst und mit Fake-Receivern oder isoliertem Venue-Netz  
- Venue-IPs (Licht, Pixera) gehören nicht in Test-Defaults  

Signal-Drop / Probebetrieb (optional, laufendes Backend):

```bash
make run-tryout
make analyze-signal-trace
make visualize-logs
```

---

*Ende — docs/testing.md*
