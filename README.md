# Theatermaschine

**Live-Regie-System für Theaterproben und Aufführungen** — Text, Stimme und Bühnenmedien (Video, Ton, Licht) in einem durchgängigen Ablauf.

Die Maschine verbindet dramaturgische Vorbereitung mit technischer Ausführung auf der Bühne: Stücktext oder Aufführungstext wird vorbereitet, Stimmen laufen als Taktgeber, und Cues steuern Projektoren, Ableton/QLab und das Lichtpult. Ein Mensch am Operator-Pult kann jederzeit eingreifen (Autopilot, Kanal-Sperren, Emergency Stop).

**Produktname in der UI:** AutoPlay · Intro-Seite (GitHub Pages): https://henniphilo.github.io/Theater-Maschine_Platform/  
(Quelle: `docs/index.html` — in Repo-Settings → Pages → Branch `main` / Ordner `/docs` aktivieren.)

**Kein Login.** API-Keys und Venue-IPs liegen lokal in `backend/.env` — nicht committen.

Referenzproduktion: Burgtheater / *Unter Tieren* (Jelinek). Die Plattform wird schrittweise produktionsunabhängig; bestehende Show-Flows bleiben nutzbar.

---

## Inhalt

- [Für wen und wofür?](#für-wen-und-wofür)
- [Was passiert auf der Bühne?](#was-passiert-auf-der-bühne)
- [Zwei Inszenierungs-Modi](#zwei-inszenierungs-modi)
- [Signalweg (Regie → Hardware)](#signalweg-regie--hardware)
- [Architektur & Bühnen-Setup (Diagramme)](docs/architektur.md)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart](#schnellstart)
- [Technik-Probe vor der Show](#technik-probe-vor-der-show)
- [Sound & Ableton](#sound--ableton)
- [Konfiguration (Venue & Regie)](#konfiguration-venue--regie)
- [Bedienung auf Probe und Abend](#bedienung-auf-probe-und-abend)
- [Live-Regie (Operator)](#live-regie-operator)
- [Remote vom Handy](docs/remote_transport.md)
- [TouchDesigner / Pixera / QLab](#touchdesigner--pixera--qlab)
- [Projektstruktur](#projektstruktur)
- [Code-Übersicht](#code-übersicht-was-liegt-wo)
- [API-Endpunkte](#api-endpunkte)
- [Entwicklung & Tests](#entwicklung--tests)
- [Häufige Probleme (Show-Nacht)](#häufige-probleme-show-nacht)

---

## Für wen und wofür?

| Rolle | Typische Aufgabe | Oberfläche |
|-------|------------------|------------|
| **Dramaturgie / Regie** | Stück vorbereiten, Text markieren, Stimmen wählen, Cues prüfen | `/dramaturgie`, `/stueck`, `/inszenierung` |
| **Technik** | Video-, Sound-, Lichtwege einzeln prüfen, Venue-Ziele setzen | `/technik`, Einstellungen / Venue-Profile |
| **Operator** | Während der Aufführung: Autopilot, Kanäle, Emergency Stop | `/director` |
| **Bühnenseitig (Handy)** | Play / Pause / Stop, während TTS auf dem Mac läuft | `/remote` |

**Kernidee:** Dramaturgie entscheidet *was* und *warum* — Adapter und Scheduler entscheiden *wie* und *ob* es an Pixera, Ableton und Licht geht. Keine direkten Hardwarebefehle aus der Dramaturgie-Schicht.

```text
Text / Dialog  →  dramaturgische Entscheidung  →  geplanter Cue  →  OSC / MIDI / TCP
```

---

## Was passiert auf der Bühne?

1. **Stimme** — TTS (macOS `say` nativ oder edge-tts in Docker) spricht Dramaturgen- oder Aufführungstext.
2. **Video** — OSC an Pixera / TouchDesigner: Avatar-Clips, Atmosphären, Blackout; oft mehrere Projektoren (z. B. RZ21, Adam, Eva, LED).
3. **Ton** — MIDI-Noten an Ableton (IAC-Bus) oder optional OSC; die Maschine spielt keine WAV-Dateien selbst ab.
4. **Licht** — TCP (JSON) ans Lichtpult oder OSC über die Medienschnittstelle.
5. **Protokoll** — Entscheidungen und Signale in `logs/director.log`, `logs/osc.log`, `logs/signal_trace.jsonl`.

Auf der Probe: **Probebetrieb** (OSC loggen, Licht auslassen) und **Technik-Test** pro Kanal. Am Abend: Operator-Panel offen, Emergency Stop greifbar, Remote optional vom Handy.

---

## Zwei Inszenierungs-Modi

| | **Teil 1 — Stücktext-Dramaturgie** | **Teil 2 — Text-Sync Inszenierung** |
|---|------------------------------------|--------------------------------------|
| **Bühnenbild** | Workshop → markierter Stücktext → Aufführung mit Regie-Cues | Ein Aufführungstext; Avatare feuern an Textstellen |
| **Textquelle** | Stück + Dramaturgen-Gespräch (GPT ↔ Claude) | AVATAR-Aufführungstext (z. B. *Delfin bis Wolf*) |
| **Workflow** | Dramaturgie → Stück → Aufführung | Text → **Vorbereiten** → Aufführung |
| **Takt** | Sequentiell (Diskussion, dann Text + Cues) | Eine KI-Stimme als Master-Clock; Avatar-OSC am CSV-Stichwort |
| **Stimmen** | Dramaturgen + rotierend A / B / Erzähler | Eine gewählte Teil-2-Stimme (z. B. Eddy / Sandy / Helena) |
| **Video** | Pixera-Clips per Dramaturgie | Avatar-Clips aus CSV, sobald die Stimme die Textstelle erreicht |
| **Navigation** | `/dramaturgie`, `/auffuehrung` | `/inszenierung`, `/inszenierung/auffuehrung` |
| **Doku** | [unten](#teil-1--stücktext--probe-und-aufführung) | [`docs/teil2_inszenierung.md`](docs/teil2_inszenierung.md) |

Ausführliche Architektur (Signale, Kamera, Ton, Licht): [`docs/architektur.md`](docs/architektur.md)  
Plattform-Zielbild (Produktionen, Assets, Devices): [`docs/platform-prd.md`](docs/platform-prd.md)

---

## Signalweg (Regie → Hardware)

```
Browser (Next.js) — Probe / Aufführung / Operator
    │
    ├── Text & TTS ──────────────► FastAPI
    │                                  │
    │                                  ├── PostgreSQL / Redis
    │                                  ├── TTS (say / edge-tts)
    │                                  │
    │                                  └── Director-Pipeline
    │                                        │
    │                                        ├── Dramaturgie (Regeln / LLM-Proposals)
    │                                        ├── Medienkatalog (JSON / CSV)
    │                                        ├── Cue-Scheduler + Safety
    │                                        └── Adapter
    │                                              ├── OSC  → Pixera / TouchDesigner (Video)
    │                                              ├── MIDI → Ableton (Sound)
    │                                              └── TCP  → Lichtpult
    │
    └── Operator (/director) ──► Safety, Emergency, Recording
```

**Designprinzip:** Dramaturgie ≠ Technik ≠ Ausgabe

```text
DialogueEvent  →  DramaturgyDecision  →  ScheduledCue  →  OSC / MIDI / TCP / Log
```

---

## Voraussetzungen

| Was | Hinweis |
|-----|---------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | Infrastruktur (Postgres, Redis, optional voller Stack) |
| OpenAI- + Anthropic-API-Key | Dramaturgie / Debatte; Keys nur in `backend/.env` |
| macOS (Show-Rechner) | Empfohlen für natives Backend: MIDI → Ableton, `say`-TTS |
| Pixera / TouchDesigner | Video-Ausgabe per OSC |
| Ableton Live | Sound über IAC-MIDI (siehe unten) |
| Lichtpult im LAN | TCP-Ziel in `.env` / Venue-Profil |
| Python 3.11+ / Node 20+ | Lokale Entwicklung |

---

## Schnellstart

Bevorzugte Befehle über das **Makefile** (Projektroot):

| Ziel | Befehl | Typischer Show-Rechner |
|------|--------|-------------------------|
| Infra + natives Backend (MIDI, `say`) | `make run` | **Ja** — Probe und Abend mit Sound |
| Alles in Docker | `make up` | Video/Licht/TTS; **kein** MIDI aus dem Container |
| Alles stoppen | `make stop` | Nach Probe / Show |

### 1. Keys und Env

```bash
git clone <repo-url>
cd Theater-Maschine_Platform   # bzw. lokaler Ordnername
make setup                     # kopiert backend/.env.example → backend/.env
```

In `backend/.env` mindestens:

```env
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
```

Venue-IPs (Licht, OSC-Host) an die aktuelle Spielstätte anpassen — siehe [Konfiguration](#konfiguration-venue--regie).

### 2. Starten

```bash
make run    # empfohlen auf dem Mac am Pult
# oder:
make up     # voller Docker-Stack
```

### 3. Öffnen (Bühnen-UI)

| Dienst | URL |
|--------|-----|
| **Technik-Probe** | http://localhost:3004/technik |
| **Teil 1 — Dramaturgie** | http://localhost:3004/dramaturgie |
| **Teil 1 — Aufführung** | http://localhost:3004/auffuehrung |
| **Teil 2 — Inszenierung** | http://localhost:3004/inszenierung |
| **Teil 2 — Aufführung** | http://localhost:3004/inszenierung/auffuehrung |
| **Live-Regie (Operator)** | http://localhost:3004/director |
| **Remote (Handy)** | http://localhost:3004/remote — [Anleitung](docs/remote_transport.md) |
| **Backend / API-Docs** | http://localhost:8000 · http://localhost:8000/docs |

> Port **3004** ist der aktuelle Frontend-Port (Docker). Ältere Hinweise auf `3003` betreffen Legacy-Setups; CORS akzeptiert beides.

### 4. Kurz prüfen

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/director/status
```

### Ports auf der Bühne

| Port | Protokoll | Rolle |
|------|-----------|--------|
| **3004** | HTTP | Frontend (Probe, Aufführung, Operator) |
| **8000** | HTTP | Backend-API |
| **7000** | UDP | OSC → Pixera / TouchDesigner (`OSC_PORT`) |
| **3032** | TCP | Lichtpult (`LIGHT_TCP_*`) |
| 5432 / 6379 | TCP | Postgres / Redis (meist nur Docker-intern; bei `make run` auf localhost gemappt) |

---

## Technik-Probe vor der Show

Unter **http://localhost:3004/technik** Kanäle **einzeln** prüfen — vor dem Durchlauf, nicht erst im Saal:

| Kanal | Was du testest |
|-------|----------------|
| **Video** | Clip senden / halten / stoppen (Pixera OSC) |
| **Sound** | Cue senden (MIDI Note On/Off → Ableton) — Backend muss **nativ** laufen (`make run`) |
| **Licht** | TCP zum Pult, Szene senden / halten / stoppen |

Erfolg Sound im Backend-Log:

```text
[MIDI SEND] [sound] → IAC-Treiber Bus 1 note_on ch=1 note=36 vel=63
```

---

## Sound & Ableton

Die Maschine sendet **MIDI-Noten** (wie Tastendrücke), keine Audiodateien in Ableton.

```text
Dramaturgie (cue_id)  →  Sound Übersicht.csv  →  MIDI-Note  →  IAC-Bus  →  Ableton
```

Ausführlich: [`docs/ableton_setup.md`](docs/ableton_setup.md) · Mapping: [`media/sound/Sound Übersicht.csv`](media/sound/Sound%20Übersicht.csv)

### IAC-Treiber (Mac)

1. **Audio-MIDI-Setup** → MIDI-Studio → **IAC-Treiber** online, **Bus 1**
2. Portname DE: `IAC-Treiber Bus 1` / EN: `IAC Driver Bus 1`

### `.env`

```env
SOUND_OUTPUT=midi
SOUND_OSC_MIRROR=false
SOUND_MIDI_PORT="IAC-Treiber Bus 1"
SOUND_MIDI_CHANNEL=1
OSC_DRY_RUN=false
```

### Ableton

MIDI-Track: **From** IAC-Bus, Monitor **In**, Arm an → Drum Rack, Pad **C1** = Note **36** (Maschine zeigt oft „C2“ — Nummer 36 zählt).

| cue_id (Beispiel) | MIDI-Note | Ableton-Pad |
|-------------------|-----------|-------------|
| maschinen_grundader | 36 | C1 |
| kaefigecho | 37 | C#1 |

Pro Soundname typisch drei Varianten: `play`, `fade_in`, `fade_out`.

---

## Konfiguration (Venue & Regie)

Alles in `backend/.env` (nicht committen). Venue-Profile können Spielstätten-Ziele bündeln (siehe UI Einstellungen / `data/venue_profiles.json`).

### KI & Stimmen (Probe vs. Aufführung)

In Docker: **edge-tts**. Nativ auf dem Mac: **`say`**. Dramaturgen- und Aufführungsstimmen sind getrennt:

```env
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
TTS_PROVIDER="auto"

# Dramaturgen (Workshop)
TTS_VOICE_OPENAI="Petra (Premium)"
TTS_VOICE_ANTHROPIC="Viktor (Enhanced)"
TTS_EDGE_VOICE_OPENAI="de-DE-ConradNeural"
TTS_EDGE_VOICE_ANTHROPIC="de-DE-KatjaNeural"

# Aufführung Teil 1 — Stimme A / B / Erzähler
TTS_VOICE_AI_A="Anna"
TTS_VOICE_AI_B="Martin"
TTS_VOICE_NARRATOR="Alex"

# Teil 2 Inszenierung
TTS_VOICE_INSZENIERUNG_AI_A="Eddy"
TTS_VOICE_INSZENIERUNG_AI_B="Sandy"
TTS_VOICE_INSZENIERUNG_NARRATOR="Helena"
```

TTS-API optional mit `profile`: `dramaturg` | `performance` | `inszenierung`.

### Live-Regie / Ausgänge

```env
DIRECTOR_ENABLED=true
DIRECTOR_AUTOPILOT_DEFAULT=true
DIRECTOR_LOG_PATH="logs/director.log"
DIRECTOR_DATA_DIR="data"
OSC_HOST="127.0.0.1"          # Docker auf Mac: host.docker.internal
OSC_PORT=7000
OSC_DRY_RUN=false             # true = nur loggen, kein UDP an die Medienserver
LIGHT_OUTPUT=tcp
LIGHT_TCP_HOST=10.101.90.112  # Spielstätten-IP — anpassen
LIGHT_TCP_PORT=3032
LIGHT_TCP_PROTOCOL=1.0
DIRECTOR_EXECUTE_MODE=sequenced
OSC_LOG_COMMANDS=true
```

| Variable | Bedeutung auf der Bühne |
|----------|-------------------------|
| `DIRECTOR_ENABLED` | Regie-Pipeline aktiv |
| `DIRECTOR_EXECUTE_MODE` | `sequenced` = planen, Execute mit Stimme/UI; `immediate` = sofort senden |
| `OSC_DRY_RUN` | Trockenlauf ohne echte Video-OSC |
| `LIGHT_TCP_HOST` | Lichtpult im Hausnetz |
| `VISUAL_OUTPUT=pixera` | Video über Pixera-OSC |

Video-Kataloge: `media/video/Video Übersicht.csv`, Projektor-Übersicht. Sound-Cache: `data/sound_cues.json`.

---

## Bedienung auf Probe und Abend

### Teil 1 — Stücktext: Probe und Aufführung

1. **`/dramaturgie`** — Stücktext einfügen; Dramaturg A/B diskutieren Regie (begrenzt, speicherbar).
2. **`/stueck`** — Markierungen Video/Sound/Licht prüfen, Sprecher anpassen.
3. **`/auffuehrung`** — Pro Abschnitt: Phase 1 vertontes Dramaturgen-Gespräch, Phase 2 Stücktext + Cues.

**Aufführungs-Paket (`.tmshow.zip`):** Text, Regieentscheidungen und vorgerenderte Stimmen — auf dem Show-Rechner importieren und ohne erneute Dramaturgie abspielen.

Medien: Pixera-Katalog, Sound-CSV → Ableton, Licht in `data/light_scenes.json`. Regie-Modus: `DIRECTOR_DRAMATURGY_MODE=llm` (Standard) oder `rules`.

### Teil 2 — Text-Sync: Avatare am Stichwort

Für **Elfriede Jelinek — *Unter Tieren*** (AVATAR-Text): eine Stimme als **Master-Clock**; Avatar-Videos feuern, wenn die Stimme die CSV-Textstelle erreicht — nicht schon am Satzanfang davor.

```text
/inszenierung     Text / Kanon-Vorlage, Stimme wählen
      ↓
Vorbereiten       Satzliste, Avatar-Anker, Licht/Sound/Video-Dramaturgie
      ↓
Aufführung        TTS-Puffer → Play / Pause / Tempo / Probebetrieb
```

Persistenz: `data/inszenierungen/{id}.json`  
Details: [`docs/teil2_inszenierung.md`](docs/teil2_inszenierung.md)

Nach Text- oder CSV-Änderungen immer **neu vorbereiten**. Import auf dem Show-Rechner:

```bash
make avatar-import
make video-import
```

**Probebetrieb** auf der Aufführungsseite: Licht-Cues aus, OSC als Dry-Run loggen, Avatar-Unterbrechung erlaubt — ideal für Durchläufe ohne volles Haus-Licht.

### Live-Regie (Operator)

Siehe [nächster Abschnitt](#live-regie-operator).

---

## Live-Regie (Operator)

Während der Aufführung steuert `/director`:

- letzte Text- und Regieentscheidung
- Safety: Autopilot, Visuals, Sound, Licht, Blackout-Sperre
- **Emergency Stop** — alle Ausgaben stoppen
- **Record** — Aufnahme in TouchDesigner anstoßen

Ablauf im Show-Modus (`DIRECTOR_EXECUTE_MODE=sequenced`):

```text
Text / TTS-Start
    → DialogueEvent
    → Dramaturgie wählt Cues
    → Scheduler (Abstände, Safety)
    → plan() an UI
    → execute() → Video OSC · Sound MIDI · Licht TCP
    → logs/director.log
```

### Remote-Transport (Handy)

Mac-Aufführungstab offen lassen; Handy im LAN: `http://<Mac-IP>:3004/remote`. TTS bleibt auf dem Mac. → [docs/remote_transport.md](docs/remote_transport.md)

### Manueller Regie-Test (ohne Stück)

```bash
curl -X POST http://localhost:8000/api/v1/director/dialogue-event \
  -H 'Content-Type: application/json' \
  -d '{
    "speaker": "AI_A",
    "text": "Erinnerung ist vielleicht nur eine technische Störung.",
    "topic": "Erinnerung",
    "mood": "melancholisch",
    "intensity": 0.72,
    "tags": ["memory", "erinnerung"]
  }'
```

### Medien auf der Festplatte

| Datei / Ordner | Bühnenrolle |
|----------------|-------------|
| `data/media.json` | Video/Sound mit Tags, Mood, Intensität |
| `data/light_scenes.json` | Lichtstimmungen |
| `data/dramaturgy_rules.json` | Keyword-Regeln, Mindestabstände |
| `media/video/` | Clips, Avatar-CSV, OSC-Befehllisten |
| `media/sound/` | Sound-Übersicht (MIDI-Mapping) |

---

## TouchDesigner / Pixera / QLab

- **OSC** typisch Port **7000** — Adressen wie `/visual/play_clip`, `/visual/blackout`, `/sound/trigger`
- TouchDesigner: [`touchdesigner/README_touchdesigner_setup.md`](touchdesigner/README_touchdesigner_setup.md)
- QLab-Bridge / Cue-Listen: [`docs/qlab_setup.md`](docs/qlab_setup.md) · Make-Targets `qlab-*`

---

## Projektstruktur

```
Theater-Maschine_Platform/
├── backend/                 # FastAPI — Regie, TTS, Adapter
│   ├── app/director/        # Pipeline, Dramaturgie, OSC/MIDI/TCP
│   ├── app/services/        # Debatte, Teil-2-Prepare, Venue, …
│   ├── run-native.sh        # Show-Rechner: MIDI + say
│   └── tests/
├── frontend/                # Next.js — Probe, Aufführung, Operator
├── data/                    # Kataloge, Inszenierungen, Venue-Profile
├── media/                   # Video/Sound-Quellen (oft nur lokal am Venue)
├── touchdesigner/           # TD-Setup
├── logs/                    # director / osc / signal_trace (gitignored)
├── docs/                    # Architektur, Teil 2, Remote, Ableton, QLab
├── Makefile                 # make run | up | stop | test-…
└── README.md
```

---

## Code-Übersicht: Was liegt wo?

### Backend — Text, Stimme, Infrastruktur

| Pfad | Aufgabe |
|------|---------|
| `backend/app/main.py` | FastAPI-App |
| `backend/app/core/config.py` | Env (KI, TTS, Director, OSC, Licht) |
| `backend/app/api/routes/debate.py` | Debatten-SSE; Hook zur Regie |
| `backend/app/services/tts/` | `say` / edge-tts, Stimmen-Profile |
| `backend/app/db/` | PostgreSQL |

### Backend — Live-Regie

| Pfad | Aufgabe |
|------|---------|
| `backend/app/director/pipeline.py` | Orchestrator |
| `backend/app/director/dramaturgy/` | Regeln / LLM-Proposals |
| `backend/app/director/cues/` | Scheduler, Safety |
| `backend/app/director/outputs/` | Pixera/TD, Sound (MIDI), Licht (TCP) |
| `backend/app/api/routes/director.py` | Operator REST + SSE |

### Backend — Teil 2 (Bühnen-Text-Sync)

| Pfad | Aufgabe |
|------|---------|
| `backend/app/services/teil2_prepare_service.py` | Vorbereiten → `teil2_plan` |
| `backend/app/services/teil2_text_alignment.py` | CSV-Text → Zeichenoffset / Chorus |
| `frontend/features/inszenierung/teil2TextSyncPlayback.ts` | Master-Clock, Avatar-Fire |

### Frontend — Bühnenflächen

| Pfad | Aufgabe |
|------|---------|
| `frontend/app/dramaturgie/` | Teil-1-Workshop |
| `frontend/app/auffuehrung/` | Teil-1-Aufführung |
| `frontend/app/inszenierung/` | Teil 2 |
| `frontend/app/director/` | Operator-Pult |
| `frontend/app/technik/` | Kanalweise Technik-Probe |
| `frontend/app/remote/` | Handy-Transport |

Weitere Tabellen und Tests: siehe ältere Abschnitte in Git-History bzw. gezielte Pfade unter `backend/tests/` und `frontend/**/*.test.ts`.

---

## API-Endpunkte

### Gesundheit & Stimme

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `GET` | `/api/v1/health` | Health |
| `POST` | `/api/v1/tts/speak` | Text → Audio |
| `GET` | `/api/v1/tts/status` | TTS verfügbar? |

### Teil 2

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `POST` | `/api/v1/inszenierung` | Korpus anlegen |
| `POST` | `/api/v1/inszenierung/{id}/prepare` | Vorbereiten für die Aufführung |
| `GET` | `/api/v1/inszenierung/{id}` | Korpus + Plan |

### Operator / Regie

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `POST` | `/api/v1/director/dialogue-event` | Text-Event einspeisen |
| `GET` | `/api/v1/director/status` | Status + Safety |
| `PATCH` | `/api/v1/director/safety` | Kanäle / Autopilot |
| `POST` | `/api/v1/director/emergency-stop` | Not-Aus |
| `POST` | `/api/v1/director/remote-transport` | Handy Play/Pause/Stop |
| `GET` | `/api/v1/director/events` | Live-SSE |

Vollständige Debatten-/Medien-Routen: http://localhost:8000/docs

---

## Entwicklung & Tests

```bash
make test              # Backend + Frontend
make test-backend      # pytest (setzt OSC_DRY_RUN=true)
make test-frontend     # vitest
make analyze-signal-trace
make visualize-logs
make run-tryout        # Probe-Lauf + Analyse (Backend muss laufen)
```

Lokal Backend-Tests: `cd backend && ./run-tests.sh`

**Wichtig für die Bühne:** In Tests und CI immer `OSC_DRY_RUN=true` — keine echten OSC/MIDI/TCP-Befehle an Haus-Hardware.

---

## Häufige Probleme (Show-Nacht)

| Problem | Erste Maßnahme |
|---------|----------------|
| Kein Sound / `rtmidi` | `make run` (natives Backend), nicht nur Docker |
| MIDI-Port fehlt | `SOUND_MIDI_PORT="IAC-Treiber Bus 1"`; Ableton From = gleicher Bus |
| MIDI OK, kein Ton | Ableton Monitor **In**, Arm an, Pad **C1** (Note 36) |
| Kein Video-OSC | `OSC_DRY_RUN=false`; Docker: `OSC_HOST=host.docker.internal` |
| Licht tot | `LIGHT_TCP_HOST` / Venue-Profil; Technik-Seite TCP verbinden |
| Cues blockiert | `/director`: Autopilot an? Kanal-Flags? Emergency aktiv? |
| Teil 2: Avatar zu früh / falsch | Nach CSV-Import **neu vorbereiten**; Alignment-Warnungen lesen |
| Teil 2: keine Clips | `make avatar-import` auf dem Show-Rechner (`media/video/` oft lokal) |
| TTS fehlt | `curl …/tts/status` — Docker: edge-tts; Mac: `say` |
| Port belegt | `make stop` bzw. alte Container stoppen |
| CORS | `CORS_ORIGINS` inkl. `http://localhost:3004` |

Signal-Drops systematisch: [`docs/debug_signal_drop_plan.md`](docs/debug_signal_drop_plan.md) · Skill/Workflow `debug-signal-drops`.

---

## Lizenz & Hinweise

- API-Keys, Passwörter und **Spielstätten-Netzadressen** nur in `backend/.env` / lokalen Venue-Profilen — nie ins Git.
- OpenAI/Anthropic können Kosten erzeugen; TTS lokal/edge ist getrennt konfigurierbar.
- Vor Premieren: Technik-Kanäle einzeln, dann Probebetrieb, dann voller Durchlauf mit Operator-Panel.
)
