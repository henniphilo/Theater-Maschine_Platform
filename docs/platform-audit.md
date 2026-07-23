# Platform Audit — Theater-Maschine

**Stand:** 2026-07-23  
**Zweck:** Ist-Analyse der aus einer Burgtheater-Produktion entstandenen Codebasis und Migrationspfad zu einer produktionsunabhängigen Theater-Maschine-Plattform.  
**Scope:** Architektur, Abhängigkeiten, Abstraktionsbedarf, Risiken, Zielbild, schrittweise Migration.  
**Nicht-Ziele:** Keine Implementierung in diesem Dokument, kein Framework-Wechsel (FastAPI + Next.js bleiben).

---

## 1. Kurzfazit

Das System ist bereits eine **funktionierende Live-Regie-Maschine** mit klarer Schichtung:

```text
DialogueEvent → DramaturgyDecision → ScheduledCue → OSC / MIDI / TCP
```

Die **Laufzeit-Kernel** (Director-Pipeline, Safety, OSC-Queue, Signal-Trace, Bridges, Teil-1/Teil-2-Playback) sind wiederverwendbar. Die **Produktionsbindung** steckt vor allem in:

- hart kodierten Projektor-IDs (`adam` / `eva` / `rz21` / `led`)
- Venue-/Stück-Katalogen unter `data/` und `media/`
- Kanon-Skript und Avatar-CSV für *Unter Tieren*
- Default-Hosts (Licht-Pult, Pixera) in Config/Compose
- Legacy-Namen (`aidebatte`, Debatten-Ursprung)

Die Migration sollte **Produktion als konfigurierbares Pack** einführen, nicht die Pipeline umbauen.

---

## 2. Ist-Architektur

### 2.1 Gesamtschichten

| Ebene | Technologie | Rolle |
|-------|-------------|--------|
| UI | Next.js 14 App Router (`frontend/`) | Dramaturgie, Aufführung, Inszenierung, Operator, Remote, Technik |
| API | FastAPI (`backend/app/`) | REST + SSE, Director, TTS, Media-Kataloge |
| Persistenz Show | JSON unter `data/` | Produktionen, Inszenierungen, Cue-Kataloge |
| Persistenz Chat | PostgreSQL (SQLAlchemy) | User / Conversation / Message (Debatten-Herkunft) |
| Infra | Docker Compose + optional natives Backend | Postgres, Redis (kaum genutzt), Frontend; MIDI/`say` nur nativ |
| Ausgabe | Bridges | Pixera OSC, TouchDesigner OSC, MIDI Sound, Licht TCP/EOS OSC, QLab-Relay-Tooling |

### 2.2 Betriebsmodi (Produkt)

| Modus | Frontend-Routen | Backend | Beschreibung |
|-------|-----------------|---------|--------------|
| **Teil 1** | `/dramaturgie` → `/stueck` → `/auffuehrung` | `/api/v1/scripts/*` | Stücktext-Workshop, sequentielle Aufführung (Diskussion → Beat) |
| **Teil 2** | `/inszenierung` → vorbereiten → `/inszenierung/auffuehrung` | `/api/v1/inszenierung/*` | Text-Sync; TTS = Master-Clock; Avatar-OSC an Char-Offset |
| **Operator** | `/director` | `/api/v1/director/*` | Safety, Emergency, OSC-Test, Licht-Desk, Events SSE |
| **Remote** | `/remote` | remote-transport | Handy Play/Pause/Stop; Ausführung auf Mac-Aufführung |
| **Technik** | `/technik` | Director light/OSC | Hardware-Smoke-Tests |
| **Legacy Debate** | (über Dramaturgie/Chat-Pfade) | `/debate`, `/chat`, `/tts` | Ursprüngliche KI-Debatte als Textquelle |

Home (`/`) leitet auf `/dramaturgie` um.

### 2.3 Backend-Struktur

```text
backend/app/
  main.py                 # FastAPI App, CORS, Rate-Limit, Avatar-Done-Listener
  api/routes/             # chat, conversations, debate(+tts), director, health,
                          # inszenierung, media, script
  core/                   # config (Pydantic Settings), logging
  db/                     # session, init_db (create_all), local_user
  models/entities.py      # User, Conversation, Message
  schemas/                # API-/Domain-Schemas
  services/               # Teil1/Teil2, Kataloge, TTS, LLM-Provider, Stores
  director/               # Pipeline, Dramaturgie, Cues, Outputs, Testing
```

**API-Präfixe** (alle unter `/api/v1`):

| Router | Prefix | Wichtige Endpunkte |
|--------|--------|--------------------|
| health | `/health` | Liveness |
| chat | `/chat` | Einzel-Chat |
| conversations | `/conversations` | Verlauf (Postgres) |
| debate | `/debate` | `POST /stream`, `POST /` |
| tts | `/tts` | `/status`, `/voices`, `/speak` |
| director | `/director` | dialogue-event, execute, execute-layered, safety, emergency, technik, light/*, record, events, osc-log, remote-transport, avatar-done/wait |
| scripts | `/scripts` | CRUD, dramaturgy/stream, performance export/import |
| inszenierung | `/inszenierung` | corpus CRUD, prepare (202), compose-script, export/import, analyse/komposition (Legacy) |
| media | `/media` | sound-cues, video-cues, avatar-speech, catalog |

### 2.4 Director- / Dramaturgie- / Scheduler-Kern

```text
DialogueEvent
  → DramaturgyEngine (rules | llm)
  → CueScheduler + SafetyState
  → DirectorPipeline.execute*
  → build_osc_commands / Bridges
  → OSC-Queue (Stagger) + signal_trace
```

| Modul | Pfad | Aufgabe |
|-------|------|---------|
| Pipeline | `director/pipeline.py` | Plan/Execute, Safety-Filter, Projector-Routing |
| Engine | `director/dramaturgy/engine.py` | Entscheidung |
| Rules / LLM | `dramaturgy/rules.py`, `llm_director.py` | Regel- vs. LLM-Modus |
| Scheduler | `director/cues/scheduler.py` | Min-Gaps, Autopilot, Emergency |
| Safety | `director/cues/safety.py` | Bridge-Toggles, Tryout, Blackout-Lock |
| Cue-Modelle | `director/cues/cue_models.py` | Visual/Sound/Light, OscCommand |
| ProjectorState | `director/cues/projector_state.py` | Avatar-Locks vs. Atmosphäre |
| OSC-Queue | `director/outputs/osc_queue.py` | Serialisierung / Stagger |
| Signal-Trace | `director/outputs/signal_trace.py` | Drop-Analyse |
| Remote | `director/remote_transport.py` | Handy-Transport |

### 2.5 Frontend-Struktur

```text
frontend/
  app/                    # Seiten (App Router)
  features/
    dramaturgy/           # Workshop-Runner
    show/                 # Teil-1 Playback, Remote-Listener
    inszenierung/         # Teil-2 Text-Sync, Avatar/Anarchy
    settings/
  components/             # layout, show, technik, script, stage, chat
  lib/api|types|text|tts|midi|show/
```

**Seiten:** `/dramaturgie`, `/stueck`, `/auffuehrung`, `/inszenierung` (+ analyse/komposition/vorbereiten/auffuehrung), `/director`, `/technik`, `/remote`.

Nav (`AppShell`): Technik-Test, Teil 1, Teil 2.

### 2.6 Daten & Medien

**Runtime-Kataloge (`data/`):**

| Datei | Inhalt |
|-------|--------|
| `video_cues.json` | 4 Projektoren + ~121 Clips (Pixera) |
| `sound_cues.json` | ~41 MIDI/Ableton-Cues |
| `light_scenes.json` / `light_inventory.json` | Venue-Licht (`venue: Unter Tieren`) |
| `avatar_speech.json` | Avatar→Text→Clip (baerenklau, delphin, lamm, petya, wolf) |
| `dramaturgy_rules.json` | Keyword/Mood/Min-Intervals |
| `productions/{uuid}.json` | Teil-1 Produktionen |
| `inszenierungen/{uuid}.json` | Teil-2 Corpora + Plans |
| `performance_bundles/` | Export-Bundles |
| `qlab_*.csv` | QLab Preview/Import-Hilfen |
| `tts/` | ggf. Cache |

**Quellen (`media/`):** Video-OSC-Listen, Sound-CSV, Light-Channel-Texte/XLSX; oft lokal, nicht vollständig im Git.

**Stücktext:** `Stücktext/AVATAR Text Delfin bis Wolf.txt`, `Bärenklau.pages` — Kanon für Teil 2 / Teil 1.

### 2.7 PostgreSQL

- Modelle: `User`, `Conversation`, `Message` in `models/entities.py`
- Schema-Erzeugung: `db/init_db.py` → `Base.metadata.create_all` (kein aktives Alembic-Tree trotz Dependency)
- Show-Daten **nicht** in Postgres — JSON-Dateien
- DB-Name Default: `aidebatte`
- Redis konfiguriert (`redis_url`), in App-Code praktisch ungenutzt

### 2.8 Ausgaben

| Bridge | Datei | Protokoll | Default-Betrieb |
|--------|-------|-----------|-----------------|
| Pixera | `outputs/pixera.py` | OSC `/pixera/args/cue/apply` | `VISUAL_OUTPUT=pixera` |
| TouchDesigner | `outputs/touchdesigner.py` | `/visual/*` | optional / `both` |
| Sound | `outputs/sound.py` + `sound_midi.py` | MIDI und/oder OSC | `SOUND_OUTPUT=midi` |
| Licht | `outputs/lighting.py`, `light_tcp.py`, `eos_light.py` | TCP 1.0 + EOS OSC auf Socket; Mirror→OSC | Host `10.101.90.112:3032` |
| Art-Net | `outputs/artnet.py` | Stub (`NotImplementedError`) | — |
| Avatar-Done | `avatar_done_listener.py` | OSC Gate (QLab→Pixera geplant) | optional |

QLab: Makefile-Targets + Scripts (Relay, Cue-Listen, Light-Patch) — Preview/Test-Pfad, nicht Kern-Runtime.

### 2.9 Docker vs. Native

| | `make up` (voller Docker) | `make run` (native Backend) |
|--|---------------------------|-----------------------------|
| Postgres/Redis/Frontend | Docker | Docker (`docker-compose.native.yml`) |
| Backend | Container | Host (`run-native.sh`) |
| MIDI → Ableton | Nein | Ja |
| TTS | edge-tts | macOS `say` (+ edge) |
| OSC Host | oft `host.docker.internal` / Pixera-IP | `127.0.0.1` / lokale `.env` |

Compose setzt produktionsnahe Defaults (Licht-IP, Pixera `172.27.27.1:8990`, `OSC_DRY_RUN=false`).

### 2.10 Tests & CI

- **Backend:** ~87 `test_*.py` (Pipeline, OSC, Licht, Teil2, QLab-Import, Trace, …); `OSC_DRY_RUN=true` via `conftest` / `run-tests.sh`
- **Frontend:** ~13 Vitest-Dateien (Playback, Text-Sync, API-Types)
- **CI:** `.github/workflows/ci.yml` — ruff + pytest; lint + vitest + Next build

### 2.11 Agent-Dokumentation

| Artefakt | Rolle |
|----------|--------|
| `AGENTS.md` | Modi, Key-Paths, Make-Targets, Dangerous Actions |
| `.cursor/rules/` | Core, Security, Token, Testing, Dev-Workflow, Backend, Frontend, Director-OSC, Teil2, Data-Media |
| `.cursor/skills/` | debug-signal-drops, tryout-run, teil2-prepare-review, media-import |
| MCP | `tools/mcp-theatermaschine/` (Trace/Inszenierung, read-only) |
| Docs | `docs/architektur.md`, `teil2_inszenierung.md`, `remote_transport.md`, Setup-Docs |

---

## 3. Produktionsspezifische Abhängigkeiten

### 3.1 Explizit an *Unter Tieren* / Burgtheater gebunden

| Bereich | Nachweis |
|---------|----------|
| Venue-Name | `data/light_inventory.json` → `"venue": "Unter Tieren"` |
| Stück / Avatare | Docs + `teil2_script_service.py`: `SCRIPT_SOURCE = "avatar_delfin_wolf"`, feste TXT-Datei |
| Avatar-IDs | `baerenklau`, `delphin`, `lamm`, `petya`, `wolf` in `avatar_speech.json` |
| Projektoren | `rz21`, `adam`, `eva`, `led` + Pixera-Prefixe `KI_*` |
| Bärenklau-Sonderlogik | `services/baerenklau_beat.py`, Nutzung in `script_store` / Frontend-Tests |
| Licht-Kanäle / Fixtures | `light_scenes.json`, `media/light/*` (Sola Wash, HMI, …) |
| Netzwerk-Defaults | Licht `10.101.90.112`, Pixera `172.27.27.1` in Compose/Config |
| Stücktext-Ordner | `Stücktext/AVATAR Text Delfin bis Wolf.*`, `Bärenklau.pages` |
| QLab-Stages | Makefile: RZ21→1, Adam→2, Eva→3, LED→4 |
| Doku | `docs/teil2_inszenierung.md` nennt Jelinek / *Unter Tieren* |

### 3.2 Legacy aus „AI Debate“

- Package-Namen: `aidebatte-backend`, `aidebatte-frontend`
- DB: `aidebatte`
- `settings.app_name = "AI Debate API"`
- Chat/Conversations/Debate-Routen und Postgres-Modelle stammen aus dem Dialog-Prototyp
- Redis vorhanden, aber ohne produktive Nutzung

### 3.3 Hart kodierte Projektor-Typen

```python
# backend/app/director/cues/cue_models.py
ProjectorTarget = Literal["adam", "eva", "rz21", "led"]
# projector_state.py
PROJECTORS = ("adam", "eva", "rz21", "led")
# rz21-Sonderfall für Atmosphäre (kein Lock)
```

Spiegelung in Frontend-Types (`lib/types/visual.ts`, `part1.ts`) und vielen Tests.

### 3.4 Datenvolumen in Repo

- Viele `data/productions/*.json` und `data/inszenierungen/*.json` = **Aufführungs-/Workshop-Artefakte** der aktuellen Produktion, nicht Plattform-Kern.

---

## 4. Wiederverwendbare Komponenten (behalten)

1. **DirectorPipeline + Safety + Scheduler** — semi-autonome Regie mit Operator-Override
2. **Bridge-Pattern** (Pixera / TD / Sound / Lighting) + OSC-Queue + Signal-Trace
3. **Abstrakte Cue-Modelle** (`VisualCue` / `SoundCue` / `LightCue` / `DramaturgyDecision`) — solange Targets konfigurierbar werden
4. **Teil-1 Workshop + Aufführungs-Playback** (Diskussion → Beat → Cues)
5. **Teil-2 Prepare-Job + Text-Alignment + Frontend-Master-Clock** (Konzept: CSV-Anker + TTS)
6. **Katalog-Services** (Laden/Validieren von video/sound/avatar JSON)
7. **TTS-Provider-Schicht** (macOS say / edge-tts / Voice-Map)
8. **Remote-Transport**
9. **Technik-/Probebetrieb** (`performance_tryout`, tryout-Scripts, Fake-OSC-Receiver)
10. **Dev-Workflow** (Makefile, Cursor-Rules/Skills, CI-Grundlage)
11. **Import-Pipeline-Idee** (Numbers/CSV → Kataloge), venuespezifische Quellen austauschbar

---

## 5. Komponenten, die abstrahiert werden müssen

| # | Heute | Ziel-Abstraktion |
|---|-------|------------------|
| 1 | `ProjectorTarget` Literal + `PROJECTORS` | Venue-Config: Liste von Outputs aus Katalog/`production.yaml` |
| 2 | rz21-Sonderlogik in `ProjectorState` | Policy pro Output (z. B. `lock_policy: atmosphere_always`) |
| 3 | `teil2_script_service` fester Kanon | `script_pack` / Upload-only; Kanon optional pro Produktion |
| 4 | `avatar_speech.json` + Animal-Namen | Production Media Pack |
| 5 | `baerenklau_beat` | generische „featured beat“-Regel oder entfernen |
| 6 | Light inventory/scenes + feste TCP-IP | Venue Lighting Pack + env ohne Hardcode in Compose-Beispiel |
| 7 | Sound MIDI-Map / Ableton-Hinweise | Production Sound Pack |
| 8 | Pixera-Prefixe `KI_*` | Mapping in Projektor-Einträgen (bereits teilweise im Katalog) |
| 9 | Package/DB-Namen `aidebatte` | `theatermaschine` / produktionsneutrale Defaults |
| 10 | Postgres nur Chat | Entscheiden: Show-Metadaten in DB **oder** bewusst file-first mit `production_id` |
| 11 | Redis ungenutzt | Entfernen oder für Prepare-Jobs/Rate-Limits nutzen |
| 12 | Alembic ungenutzt | Migrations aktivieren **oder** Dependency entfernen / dokumentieren |
| 13 | Default `VISUAL_OUTPUT=pixera`, Live-IPs | Profile: `dev` / `venue` / `dry-run` |
| 14 | Frontend-Types gespiegelte Literals | aus API-Katalog (`/media/catalog`) ableiten |

---

## 6. Risiken einer Migration

| Risiko | Schwere | Erklärung |
|--------|---------|-----------|
| Projektor-Literal-Refactor | Hoch | Typen Backend+Frontend+Tests+Routing; Regression Avatar vs. Atmosphäre |
| Dual Sentence-Split | Hoch | `text_split.py` ↔ `splitSentences.ts` müssen synchron bleiben |
| Live-Hardware-Defaults | Hoch | Compose/`OSC_DRY_RUN=false` + echte IPs → unbeabsichtigte Signale |
| Katalog-Schema-Bruch | Mittel | Bestehende `inszenierungen`/`productions` JSON müssen migriert oder versioniert werden |
| Teil-2 Timing | Hoch | Char-Offsets hängen an CSV+Skript der aktuellen Show |
| Licht-Kanäle | Mittel | Falsche Kanäle an anderem Pult = gefährlich; Packs strikt trennen |
| Datenmüll im Repo | Niedrig–Mittel | Alte UUID-JSONs erschweren „leere Plattform“ |
| Unklare Persistenz-Strategie | Mittel | File vs. Postgres vs. Redis parallel → Drift |
| QLab-Tooling | Niedrig | Preview-Pfad; darf Venue-Pack werden, nicht Kernel blockieren |
| Naming Debt | Niedrig | `aidebatte` verwirrt Onboarding |

---

## 7. Empfohlene Zielarchitektur (ohne Framework-Wechsel)

### 7.1 Prinzipien

1. **Kernel vs. Pack:** Code = Maschine; `productions/<slug>/` = Inhalt + Venue-Bindings.
2. **Outputs bleiben Adapter:** Pixera/TD/MIDI/EOS/TCP austauschbar über Settings.
3. **File-first für Shows beibehalten** (schnell, git-fähig, bewährt); Postgres optional für Accounts/Audit.
4. **Eine aktive Production** zur Laufzeit (`PRODUCTION_ID` / UI-Wahl).
5. **Dry-run by default** in Dev-Templates; Venue-Profile explizit aktivieren.

### 7.2 Vorgeschlagenes Pack-Layout

```text
productions/
  _template/
    production.yaml          # id, title, outputs, features
    dramaturgy_rules.json
    video_cues.json
    sound_cues.json
    light_scenes.json
    light_inventory.json
    avatar_speech.json       # optional (Teil 2)
    scripts/                 # optional Kanon-Texte
  unter-tieren/              # erste Migration der aktuellen Show
    ...
```

`production.yaml` (Beispiel-Felder):

- `outputs.visual`: pixera|touchdesigner|both
- `outputs.projectors[]`: id, pixera_prefix, lock_policy
- `outputs.sound`: midi|osc|both
- `outputs.light`: tcp|osc|mirror + connection via env
- `features.teil1` / `features.teil2`
- `teil2.script_source`: path | upload-only

### 7.3 Laufzeit

```text
Browser → FastAPI
            ├─ ProductionContext (Kataloge, Rules, ProjectorPolicy)
            ├─ DirectorPipeline (unverändert im Kern)
            └─ Bridges (Hosts aus env, IDs aus Pack)
```

Frontend lädt Projektoren/Cues aus `/media/catalog` statt aus Literals.

### 7.4 Was bewusst nicht ändern

- FastAPI / Next.js / python-osc / mido
- Pipeline-Semantik und Signal-Trace
- Teil-2 Master-Clock im Frontend
- Make-basierter Dev-Workflow

---

## 8. Schrittweise Migrationsreihenfolge

### Schritt 0 — Inventar & Freeze (Dokumentation)

**Ziel:** Aktuelle Show als Referenz einfrieren; Plattform-Ziel kommunizieren.  
**Deliverable:** dieses Audit + Production-Pack-Spec.  
**Relevante Dateien:**

- `docs/platform-audit.md` *(dieses Dokument)*
- `AGENTS.md`, `README.md`, `docs/architektur.md`, `docs/teil2_inszenierung.md`
- `.cursor/rules/*`, `.cursor/skills/*/SKILL.md`

---

### Schritt 1 — Naming & Defaults entschärfen (risikoarm)

**Ziel:** Neutrale Identität; sichere Dev-Defaults.  
**Maßnahmen:**

- App-/Package-Namen Richtung `theatermaschine` (oder belassen + dokumentieren)
- Beispiel-`.env` / Compose: `OSC_DRY_RUN=true` in Dev-Docs; Venue-IPs nur in `*.venue.env.example`
- `app_name` anpassen

**Dateien:**

- `backend/pyproject.toml`, `frontend/package.json`
- `backend/app/core/config.py`
- `docker-compose.yml`, `docker-compose.native.yml`
- `backend/.env.example` (falls vorhanden)
- `README.md`, `AGENTS.md`

---

### Schritt 2 — Production Context + Katalog-Pfad

**Ziel:** `DIRECTOR_DATA_DIR` / Pack-Root; eine aktive Produktion wählbar.  
**Maßnahmen:**

- `ProductionContext` lädt Rules/Cues aus Pack
- Stores (`script_store`, `inszenierung_store`) unter Pack-Root
- API: `GET /media/catalog` um Production-Metadaten erweitern

**Dateien:**

- `backend/app/core/config.py`
- `backend/app/director/media/database.py`
- `backend/app/services/script_store.py`
- `backend/app/services/inszenierung_store.py`
- `backend/app/services/*_catalog.py`
- `backend/app/api/routes/media.py`
- `backend/tests/conftest.py`, `backend/tests/repo_paths.py`
- `Makefile` (DATA_DIR / PRODUCTION)

---

### Schritt 3 — Projektoren konfigurierbar machen

**Ziel:** `Literal["adam",…]` → Strings aus Katalog + Policy.  
**Maßnahmen:**

- `ProjectorTarget` → `str` mit Validierung gegen Katalog
- `ProjectorState` initialisiert aus Catalog
- rz21-Sonderfall → Policy-Feld
- Frontend-Types anpassen; Tests mit Dummy-Pack (`proj_a`…)

**Dateien:**

- `backend/app/director/cues/cue_models.py`
- `backend/app/director/cues/projector_state.py`
- `backend/app/director/cues/visual_outputs.py`
- `backend/app/services/teil2_projector_assignment.py`
- `backend/app/services/teil2_dramaturgy_routing.py`
- `backend/app/services/preview_executor.py`
- `frontend/lib/types/visual.ts`, `frontend/lib/types/part1.ts`
- `backend/tests/test_projector_lock.py`, `test_teil2_projector_assignment.py`, `test_visual_outputs.py`, …
- `frontend/features/inszenierung/*.test.ts`

---

### Schritt 4 — Venue-/Show-Pack „unter-tieren“ auslagern

**Ziel:** Aktuelle `data/*`-Show-Inhalte nach `productions/unter-tieren/`.  
**Maßnahmen:**

- Kataloge + Stücktext + Avatar-CSV-Quellen verschieben/verlinken
- Repo-Root `data/` nur noch Runtime/Cache oder Default-Template
- Import-Scripts schreiben in Pack-Pfad

**Dateien:**

- `data/video_cues.json`, `sound_cues.json`, `light_*.json`, `avatar_speech.json`, `dramaturgy_rules.json`
- `data/productions/**`, `data/inszenierungen/**` (archivieren oder dem Pack zuordnen)
- `Stücktext/**`
- `media/video/**`, `media/sound/**`, `media/light/**`
- `backend/scripts/import_*.py`, `Makefile` (`avatar-import`, `video-import`)
- `.cursor/rules/50-data-media.mdc`

---

### Schritt 5 — Teil-2 Kanon entkoppeln

**Ziel:** Kein hardcodiertes „Delfin bis Wolf“ im Kernel.  
**Maßnahmen:**

- `teil2_script_service.py`: Script aus Pack-Config oder Upload
- `baerenklau_beat` generalisieren oder Pack-Hook
- Docs produktionsneutral formulieren

**Dateien:**

- `backend/app/services/teil2_script_service.py`
- `backend/app/services/baerenklau_beat.py`
- `backend/app/api/routes/inszenierung.py`
- `frontend/lib/show/baerenklauBeat.ts` (+ Tests)
- `backend/tests/test_baerenklau_beat.py`, `test_teil2_script_service.py`
- `docs/teil2_inszenierung.md`

---

### Schritt 6 — Output-Profile & sichere Defaults

**Ziel:** Profile `dry-run` / `studio-qlab` / `venue-pixera-eos`.  
**Maßnahmen:**

- Keine Produktions-IPs in Default-Compose
- Art-Net weiter optional (Stub ok)
- QLab-Makefile als optionales Pack-Tool dokumentieren

**Dateien:**

- `docker-compose.yml`
- `backend/app/core/config.py`
- `backend/app/director/outputs/{pixera,touchdesigner,sound,lighting,artnet}.py`
- `docs/qlab_setup.md`, `docs/ableton_setup.md`, `touchdesigner/README_touchdesigner_setup.md`
- `Makefile` (qlab-*)

---

### Schritt 7 — Persistenz klären

**Ziel:** Eine klare Story. Empfehlung: **Shows file-based**; Postgres nur Auth/Chat oder später Production-Registry.  
**Maßnahmen:**

- Redis: nutzen (Prepare-Job-Status) oder aus Compose entfernen
- Alembic: aktivieren für `entities` **oder** Dependency streichen
- Optional: Index-Datei `productions/index.json`

**Dateien:**

- `backend/app/db/*`, `backend/app/models/entities.py`
- `backend/app/api/routes/conversations.py`, `chat.py`, `debate.py`
- `docker-compose.yml` (redis)
- ggf. neues `backend/alembic/`

---

### Schritt 8 — Frontend produktionsneutral

**Ziel:** UI spricht von „Produktion / Venue“, nicht von festen Beamern.  
**Maßnahmen:**

- Catalog-driven Labels
- Leeres Template onboarding
- Nav/Copy in README/AGENTS

**Dateien:**

- `frontend/components/layout/AppShell.tsx`
- `frontend/app/**/page.tsx`
- `frontend/lib/api/media.ts` (o. ä.)
- `frontend/features/**`
- `README.md`, `AGENTS.md`

---

### Schritt 9 — Test- & CI-Härtung für Multi-Production

**Ziel:** Tests laufen gegen `_template` + Fixture-Pack, nicht nur Unter-Tieren-Namen.  
**Maßnahmen:**

- Golden fixtures unter `backend/tests/fixtures/productions/minimal/`
- CI unverändert (ruff/pytest/vitest), ggf. Pack-Validierungsjob

**Dateien:**

- `backend/tests/**`
- `frontend/**/*.test.ts`
- `.github/workflows/ci.yml`
- `backend/tests/conftest.py`

---

### Schritt 10 — Zweite Produktion (Validierung)

**Ziel:** Leeres Pack + Dummy-Outputs beweist Unabhängigkeit.  
**Kein Framework-Wechsel** — nur Config + Medien.

**Dateien:** `productions/_template/**`, ggf. `productions/demo/**`

---

## 9. Priorisierte Dateiliste (Quick Reference)

### Kernel (plattformnah, vorsichtig ändern)

- `backend/app/director/pipeline.py`
- `backend/app/director/cues/{scheduler,safety,cue_models,projector_state}.py`
- `backend/app/director/outputs/{osc_queue,signal_trace,pixera,touchdesigner,sound,lighting}.py`
- `backend/app/main.py`, `backend/app/api/routes/director.py`
- `frontend/features/show/*`, `frontend/features/inszenierung/teil2TextSyncPlayback.ts`

### Pack-/Venue-Kandidaten (stark produktionsspezifisch)

- `data/{video_cues,sound_cues,light_*,avatar_speech,dramaturgy_rules}.json`
- `data/{productions,inszenierungen,performance_bundles}/**`
- `Stücktext/**`, `media/**`
- `backend/app/services/{teil2_script_service,baerenklau_beat}.py`
- `backend/scripts/{import_*,export_qlab_*}.py`

### Infrastruktur / Naming

- `docker-compose*.yml`, `Makefile`, `backend/Dockerfile`, `frontend/Dockerfile`
- `backend/pyproject.toml`, `frontend/package.json`
- `backend/app/core/config.py`, `backend/app/db/*`

### Agent / Docs

- `AGENTS.md`, `PLAN.md`, `docs/**`, `.cursor/rules/**`, `.cursor/skills/**`

---

## 10. Empfohlene Reihenfolge in einem Satz

**Zuerst absichern und Production Context einführen → Projektoren/Policies generisch machen → Unter-Tieren als Pack isolieren → Teil-2-Kanon und Bärenklau entkoppeln → Output-Profile/Defaults → Persistenz aufräumen → Frontend/Tests auf Multi-Pack → mit zweitem Dummy-Pack verifizieren.**

---

## 11. Offene Entscheidungen (vor Implementierung klären)

1. Bleibt **file-first** für Shows dauerhaft, oder soll eine Production-Registry in Postgres?
2. Ist **Teil-1 Debatten-Workshop** Kernprodukt oder Legacy-Modus?
3. Soll **QLab** offizieller Preview-Standard bleiben oder nur optionales Pack-Tool?
4. Werden alte `data/productions` / `inszenierungen` archiviert, gelöscht oder dem Pack `unter-tieren` zugeordnet?
5. Multi-Production gleichzeitig im UI oder nur eine aktive Production pro Backend-Instanz?

---

*Ende Audit.*
