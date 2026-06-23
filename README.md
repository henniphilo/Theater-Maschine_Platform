# Theatermaschine

**KI-Debatte als dramaturgische Textquelle** — plus **semi-autonome Live-Regie** für Video, Ton und Licht.

Zwei KIs (GPT und Claude) diskutieren live über ein Thema. Während sie sprechen, entscheidet ein Regie-System, welche Videoclips, Sound-Cues und Lichtstimmungen ausgelöst werden. Ein Operator kann jederzeit eingreifen (Autopilot, Overrides, Emergency Stop).

**Kein Login.** API-Keys liegen lokal in `backend/.env`.

---

## Inhalt

- [Was macht das Projekt?](#was-macht-das-projekt)
- [Architektur](#architektur)
- [Architektur & Bühnen-Setup (Diagramme)](docs/architektur.md)
- [Voraussetzungen](#voraussetzungen)
- [Schnellstart (Docker)](#schnellstart-docker)
- [Start mit Sound / Ableton (Backend nativ)](#start-mit-sound--ableton-backend-nativ)
- [Technik-Test](#technik-test)
- [Sound & Ableton einrichten](#sound--ableton-einrichten)
- [Konfiguration](#konfiguration)
- [Bedienung](#bedienung)
- [Teil 1 — Stücktext-Dramaturgie](#teil-1--stücktext-dramaturgie)
- [Teil 2 — Anarchische Inszenierung](#teil-2--anarchische-inszenierung)
- [Live-Regie (Director)](#live-regie-director)
- [TouchDesigner](#touchdesigner)
- [Projektstruktur](#projektstruktur)
- [Code-Übersicht: Was liegt wo?](#code-übersicht-was-liegt-wo)
- [API-Endpunkte](#api-endpunkte)
- [Entwicklung & Tests](#entwicklung--tests)
- [Häufige Probleme](#häufige-probleme)

---

## Was macht das Projekt?

### KI-Debatte (Textquelle)

1. Du gibst ein **Diskussionsthema** ein.
2. **GPT** und **Claude** diskutieren abwechselnd — kurze, natürliche Antworten.
3. Optional: **Vertonung** per TTS (Siri auf Mac oder edge-tts in Docker).

### Live-Regie (Director)

Bei jedem Debatten-Beitrag (wenn `DIRECTOR_ENABLED=true`):

1. Text wird analysiert (Tags, Stimmung, Intensität).
2. Die **Dramaturgie-Engine** wählt passende Video-, Sound- und Licht-Cues aus der Medien-Datenbank.
3. Der **Cue-Scheduler** prüft Safety-Regeln (Abstände, Overrides).
4. Befehle gehen per **OSC** an TouchDesigner (Video/Sound). **Licht** geht direkt per **TCP** ans Pult (`10.101.90.112:3032`, Protokoll 1.0).
5. Entscheidungen werden in `logs/director.log` protokolliert.

Der Operator steuert alles über **http://localhost:3003/director** (Autopilot, Visuals/Sound/Licht, Aufnahme, Emergency Stop).

### Zwei Inszenierungs-Modi

| | **Teil 1** — Stücktext | **Teil 2** — Anarchische Inszenierung |
|---|------------------------|----------------------------------------|
| Textquelle | Ein Stücktext, Beats | Mehrere Tier-Szenen (Korpus), z. B. Jelinek *Unter Tieren* / Geld |
| Workflow | Dramaturgie → Stücktext → Aufführung | Import → Analyse → Komposition → Aufführung |
| Wiedergabe | Sequentiell: Diskussion, dann Stücktext | Eskalierende Überlagerung, parallele Stimmen & Beamer |
| Stimmen | Dramaturgen + Stimme A/B/Erzähler | Avatar-Video (kein TTS) + eigene KI-Stimmen (Teil 2) |
| Doku | unten [Teil 1](#teil-1--stücktext-dramaturgie) | [`docs/teil2_inszenierung.md`](docs/teil2_inszenierung.md) |

Ausführlicher Entwicklungsplan: [`PLAN.md`](PLAN.md)  
Architektur, Signale, Kamera/Ton/Licht-Setup: [`docs/architektur.md`](docs/architektur.md)

---

## Architektur

```
Browser (Next.js)
    │
    ├── Debatte (SSE) ──────────► FastAPI ──► OpenAI / Anthropic
    │                                  │
    │                                  ├── PostgreSQL (Verlauf)
    │                                  ├── Redis
    │                                  ├── TTS (say / edge-tts)
    │                                  │
    │                                  └── Director Pipeline
    │                                        │
    │                                        ├── DramaturgyEngine (Regeln)
    │                                        ├── MediaDatabase (JSON)
    │                                        ├── CueScheduler + SafetyState
    │                                        └── OSC ──► TouchDesigner
    │
    └── Operator-UI (/director) ──► Director REST + SSE
```

**Designprinzip:** Dramaturgie ≠ Technik ≠ Ausgabe

```text
DialogueEvent  →  DramaturgyDecision  →  ScheduledCue  →  OSC / Log
```

---

## Voraussetzungen

| Was | Hinweis |
|-----|---------|
| [Docker Desktop](https://www.docker.com/products/docker-desktop/) | empfohlen für den Schnellstart |
| OpenAI API-Key | [platform.openai.com](https://platform.openai.com/) |
| Anthropic API-Key | [console.anthropic.com](https://console.anthropic.com/) |
| TouchDesigner | optional, für echte Video-Ausgabe per OSC |
| Python 3.11+ / Node 20+ | nur für lokale Entwicklung ohne Docker |

---

## Schnellstart (Docker)

### 1. Keys eintragen

```bash
git clone <repo-url>
cd Theatermaschine
cp backend/.env.example backend/.env
```

`backend/.env` — mindestens:

```env
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
```

### 2. Alte Container stoppen (falls Port-Konflikt)

Falls noch ein alter `aidebatte-*`-Stack läuft:

```bash
docker stop aidebatte-backend-1 aidebatte-frontend-1 aidebatte-postgres-1 aidebatte-redis-1
```

### 3. Starten

**Im Projektroot** (nicht in `backend/`):

```bash
cd Theatermaschine
docker compose up -d --build
```

Läuft im Hintergrund — Terminal bleibt frei. Logs nur bei Bedarf:

```bash
docker compose logs -f backend    # live mitverfolgen (Ctrl+C beendet nur die Anzeige)
docker compose logs -f frontend
docker compose logs --tail 50   # letzte Zeilen aller Services
```

Stoppen: `docker compose down`

**Alternativ** mit Logs im Vordergrund: `docker compose up --build` — mit `d` abkoppeln (Container laufen weiter) oder Ctrl+C zum Stoppen.

Nach Änderungen an `pyproject.toml` / `package.json` oder wenn etwas „hängen bleibt“:

```bash
docker compose down
docker compose build --no-cache
docker compose up
```

Nur `.env` geändert → Container neu starten (kein Rebuild nötig):

```bash
docker compose up --force-recreate backend
```

### 4. Öffnen

| Dienst | URL |
|--------|-----|
| **Dramaturgie** (Teil 1) | http://localhost:3003/dramaturgie |
| **Stücktext** (Teil 1) | http://localhost:3003/stueck |
| **Aufführung** (Teil 1) | http://localhost:3003/auffuehrung |
| **Inszenierung** (Teil 2) | http://localhost:3003/inszenierung |
| **Analyse** (Teil 2) | http://localhost:3003/inszenierung/analyse |
| **Komposition** (Teil 2) | http://localhost:3003/inszenierung/komposition |
| **Aufführung** (Teil 2) | http://localhost:3003/inszenierung/auffuehrung |
| **Live-Regie (Operator)** | http://localhost:3003/director |
| **Technik-Test** (Video/Sound/Licht einzeln) | http://localhost:3003/technik |
| **Backend (API)** | http://localhost:8000 |
| **API-Docs** | http://localhost:8000/docs |

### 5. Prüfen

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/director/status
```

### Stoppen

```bash
docker compose down
```

### Ports (einheitlich)

| Port | Protokoll | Dienst | Nach außen (Docker) |
|------|-----------|--------|---------------------|
| **3003** | HTTP | Frontend (Debatte + `/director`) | ja |
| **8000** | HTTP | Backend API | ja |
| **7000** | UDP | OSC → TouchDesigner (Video/Sound) | nein (Host/Mac, `OSC_PORT` in `.env`) |
| **3032** | TCP | Licht-Pult (JSON Protokoll 1.0) | nein (LAN, `LIGHT_TCP_*` in `.env`) |
| 5432 | TCP | PostgreSQL | nein (nur Docker-intern) |
| 6379 | TCP | Redis | nein (nur Docker-intern) |

Docker: Frontend **3003**, Backend **8000**. Postgres/Redis nur intern in Docker — **außer** beim nativen Backend für Sound (siehe unten).

---

## Start mit Sound / Ableton (Backend nativ)

**Wichtig:** Sound geht per **MIDI** an Ableton (IAC-Bus). Das funktioniert **nicht** aus dem Docker-Container — das Backend muss **nativ auf dem Mac** laufen (Python **3.11+**, nicht das System-`python3` 3.9).

### Wann welcher Modus?

| Modus | Wofür | Befehl |
|-------|--------|--------|
| **Docker (Standard)** | Debatte, Dramaturgie, Video (Pixera), Licht, TTS | `docker compose up -d --build` |
| **Backend nativ** | Sound → Ableton (MIDI), optional macOS `say`-TTS | `./backend/run-native.sh` (siehe unten) |

Beides parallel: Postgres, Redis und Frontend in Docker — nur der **Backend-Container** bleibt aus.

### 1. Infrastruktur in Docker (ohne Backend)

Im **Projektroot**:

```bash
cd Theatermaschine
docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis frontend
docker compose stop backend
```

`docker-compose.native.yml` mappt Postgres (`5432`) und Redis (`6379`) auf `localhost`, damit das native Backend die DB erreicht.

### 2. Backend nativ starten

```bash
cd backend
./run-native.sh
```

Das Skript:

- legt eine venv mit **`python3.11`** an (falls nötig: `brew install python@3.11`)
- installiert Abhängigkeiten (`pip install -e .`)
- setzt `OSC_HOST=127.0.0.1` (für nativen Betrieb; in Docker bleibt `host.docker.internal` in `.env`)
- startet Uvicorn auf **http://localhost:8000**

**Nicht** `python3` (3.9) und **nicht** globales `uvicorn` aus Homebrew verwenden.

### 3. Prüfen

```bash
curl http://localhost:8000/api/v1/health
```

Sound-Test: http://localhost:3003/technik → Bereich **Sound** → Cue wählen → **Signal senden**.

Erfolg im Backend-Log:

```text
[MIDI SEND] [sound] → IAC-Treiber Bus 1 note_on ch=1 note=36 vel=63
```

Ohne `FEHLER` oder `rtmidi`-Traceback danach.

### 4. Zurück zu vollem Docker

```bash
# natives Backend beenden (Ctrl+C im Terminal)
docker compose up -d --build
```

---

## Technik-Test

Unter **http://localhost:3003/technik** kannst du **Video**, **Sound** und **Licht** jeweils **einzeln** testen (nicht kombiniert):

| Bereich | Aktionen |
|---------|----------|
| **Video** | Clip wählen → Signal senden / halten / stoppen (Pixera OSC) |
| **Sound** | Cue wählen → Signal senden / halten / stoppen (MIDI Note On/Off) |
| **Licht** | 1. TCP-Verbindung zum Pult → 2. Szene wählen → senden / halten / stoppen |

Sound-Tests setzen voraus, dass das Backend **nativ** läuft (siehe oben).

---

## Sound & Ableton einrichten

Die Maschine spielt **keine WAV/MP3-Dateien** in Ableton ab. Sie sendet **MIDI-Noten** — wie ein Keyboard-Tastendruck. Ableton muss wissen, welcher Sound bei welcher Note läuft.

```text
Dramaturgie (cue_id)  →  Sound Übersicht.csv  →  MIDI Note  →  Ableton  →  Ton
  maschinen_grundader         Note 36, Kanal 1      IAC-Bus      Drum Rack Pad C1
```

Ausführlich: [`docs/ableton_setup.md`](docs/ableton_setup.md) · Mapping: [`media/sound/Sound Übersicht.csv`](media/sound/Sound%20Übersicht.csv)

### Schritt 1: IAC-Treiber (Mac)

1. **Audio-MIDI-Setup** öffnen (Spotlight)
2. **Fenster → MIDI-Studio** → Doppelklick **IAC-Treiber**
3. **Gerät ist online** aktivieren
4. Mindestens **Bus 1** anlegen

Portname auf deutschen Macs: **`IAC-Treiber Bus 1`** (englisch: `IAC Driver Bus 1`). Beides wird vom Backend erkannt.

### Schritt 2: `backend/.env`

```env
SOUND_OUTPUT=midi
SOUND_OSC_MIRROR=false
SOUND_MIDI_PORT="IAC-Treiber Bus 1"
SOUND_MIDI_CHANNEL=1
OSC_DRY_RUN=false
```

`SOUND_MIDI_PORT` leer lassen = erster verfügbarer IAC-Port.

### Schritt 3: Ableton Live

1. **MIDI-Track** anlegen (`Cmd+Shift+T`)
2. Rechts **`I-O`** aktivieren (sonst siehst du MIDI From / Arm nicht)
3. **MIDI From:** `IAC-Treiber Bus 1` · **Monitor:** `In` · **Arm:** an (roter Kreis unten am Track)
4. **Drum Rack** auf den Track ziehen (Browser → Drums)
5. Pad **C1** (= MIDI-Note **36**) mit Sample belegen — z. B. für `maschinen_grundader`

**Hinweis Oktav-Namen:** Die Maschine zeigt Note 36 als **C2**, Ableton nennt dieselbe Note **C1** — das ist normal, die Nummer **36** zählt.

| cue_id | MIDI-Note | Ableton-Pad |
|--------|-----------|-------------|
| maschinen_grundader | 36 | C1 |
| kaefigecho | 37 | C#1 |
| maschinen_grundader_fade_in | 52 | E2 |

Pro Soundname gibt es in der CSV drei Zeilen: `play`, `fade_in`, `fade_out` — jeweils eigene Note.

### Schritt 4: Test

1. Backend nativ: `cd backend && ./run-native.sh`
2. Browser: http://localhost:3003/technik → **Sound** → `Maschinen-Grundader` → **Signal senden**
3. In Ableton: Pad **C1** blinkt, Sample spielt

---

## Konfiguration

Alle Einstellungen in `backend/.env` (nicht committen).

### KI & TTS

In **Docker** nutzt das Backend automatisch **edge-tts** (kein macOS `say`). Dramaturgen- und Aufführungsstimmen sind getrennt konfigurierbar:

```env
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
TTS_PROVIDER="auto"

# Dramaturgen (Workshop / Phase 1) — macOS: Petra (Premium) / Viktor (Enhanced)
TTS_VOICE_OPENAI="Petra (Premium)"
TTS_VOICE_ANTHROPIC="Viktor (Enhanced)"
TTS_EDGE_VOICE_OPENAI="de-DE-ConradNeural"
TTS_EDGE_VOICE_ANTHROPIC="de-DE-KatjaNeural"

# Aufführung Teil 1 — rotiert satzweise AI_A / AI_B / narrator
TTS_VOICE_AI_A="Anna"
TTS_VOICE_AI_B="Martin"
TTS_VOICE_NARRATOR="Alex"
TTS_EDGE_VOICE_AI_A="de-DE-KillianNeural"
TTS_EDGE_VOICE_AI_B="de-DE-SeraphinaMultilingualNeural"
TTS_EDGE_VOICE_NARRATOR="de-DE-AmalaNeural"

# Teil 2 Inszenierung — eigene KI-Stimmen (getrennt von Teil 1)
TTS_VOICE_INSZENIERUNG_AI_A="Eddy"
TTS_VOICE_INSZENIERUNG_AI_B="Sandy"
TTS_VOICE_INSZENIERUNG_NARRATOR="Helena"
TTS_EDGE_VOICE_INSZENIERUNG_AI_A="de-DE-FlorianMultilingualNeural"
TTS_EDGE_VOICE_INSZENIERUNG_AI_B="de-DE-SeraphinaMultilingualNeural"
TTS_EDGE_VOICE_INSZENIERUNG_NARRATOR="de-DE-KatjaNeural"
```

TTS-API optional mit `profile`: `dramaturg` | `performance` | `inszenierung` (siehe `POST /api/v1/tts/speak`).

Nach Änderungen an Code oder `.env`: `docker compose up --build`

Stimmenliste: `docker compose exec backend edge-tts --list-voices | grep de-DE`

### Live-Regie / Director

```env
DIRECTOR_ENABLED=true
DIRECTOR_AUTOPILOT_DEFAULT=true
DIRECTOR_LOG_PATH="logs/director.log"
DIRECTOR_DATA_DIR="data"
OSC_HOST="127.0.0.1"
OSC_PORT=7000
OSC_DRY_RUN=false
LIGHT_OUTPUT=tcp
LIGHT_TCP_HOST=10.101.90.112
LIGHT_TCP_PORT=3032
LIGHT_TCP_PROTOCOL=1.0
DIRECTOR_EXECUTE_MODE=sequenced
OSC_LOG_COMMANDS=true
```

| Variable | Standard | Beschreibung |
|----------|----------|--------------|
| `DIRECTOR_ENABLED` | `true` | Regie bei Debatten-Turns aktivieren |
| `DIRECTOR_EXECUTE_MODE` | `sequenced` | `sequenced` = nur planen bei Debatte, Execute per UI; `immediate` = sofort OSC |
| `OSC_DRY_RUN` | `false` | `true` = nur loggen, kein UDP an TouchDesigner |
| `OSC_LOG_COMMANDS` | `true` | Lesbare `[OSC …]`-Zeilen im Backend-Log |
| `OSC_HOST` | `127.0.0.1` | In Docker auf Mac: `host.docker.internal` |
| `LIGHT_OUTPUT` | `tcp` | `tcp` = direkt ans Licht-Pult; `osc` = über TouchDesigner |
| `LIGHT_TCP_HOST` | `10.101.90.112` | IP des Licht-Pults |
| `LIGHT_TCP_PORT` | `3032` | TCP-Port |
| `LIGHT_TCP_PROTOCOL` | `1.0` | JSON-Protokollversion in jeder Nachricht |
| `DIRECTOR_DATA_DIR` | `data` | Pfad zu `media.json`, `light_scenes.json`, … |

In `docker-compose.yml` ist `OSC_DRY_RUN=false` gesetzt, damit OSC an TouchDesigner/Pixera gesendet wird. Licht nutzt `LIGHT_TCP_*` (Standard: `10.101.90.112:3032`).

### Sound (MIDI → Ableton)

```env
SOUND_OUTPUT=midi
SOUND_OSC_MIRROR=false
SOUND_MIDI_PORT="IAC-Treiber Bus 1"
SOUND_MIDI_CHANNEL=1
```

| Variable | Beschreibung |
|----------|--------------|
| `SOUND_OUTPUT` | `midi` (Ableton) · `osc` · `both` |
| `SOUND_MIDI_PORT` | IAC-Bus — DE: `IAC-Treiber Bus 1`, EN: `IAC Driver Bus 1`; leer = Auto |
| `SOUND_MIDI_CHANNEL` | MIDI-Kanal 1–16 (Standard: 1) |

Mapping: `media/sound/Sound Übersicht.csv` → Cache `data/sound_cues.json`.  
**Backend für Sound nativ auf dem Mac** — siehe [Start mit Sound / Ableton](#start-mit-sound--ableton-backend-nativ).

### Video (Pixera)

```env
VISUAL_OUTPUT=pixera
OSC_HOST=host.docker.internal   # Docker auf Mac
# Nativ: OSC_HOST=127.0.0.1 (setzt run-native.sh automatisch)
```

Clips/Projektoren: `media/video/Video Übersicht.csv`, `media/video/Projektor Übersicht.csv`.

---

## Bedienung

### Teil 1 — Stücktext-Dramaturgie

#### 3-Phasen-Workflow

1. **`/dramaturgie`** — Stücktext einfügen; Dramaturg A (GPT) und Dramaturg B (Claude) diskutieren abwechselnd die Regie (max. 2 Beiträge je Dramaturg). Das Gespräch wird gespeichert und in der Aufführung vertont.
2. **`/stueck`** — Stücktext mit Dramaturgen-Gespräch, Video/Sound/Licht-Markierungen prüfen, Sprecher anpassen
3. **`/auffuehrung`** — Pro Abschnitt: **Phase 1** vertontes Dramaturgen-Gespräch, **Phase 2** Stücktext mit TTS + OSC-Cues. **Export** als `.tmshow.zip` (Text, Cues, vorgerenderte Stimmen); **Import** startet die Maschine ohne erneute Dramaturgie.

**Aufführungs-Paket (`.tmshow.zip`):** `manifest.json` + `audio/` — enthält Stücktext, `discussion_turns`, Regieentscheidungen und alle Stimmen. Auf einem anderen Rechner importieren und direkt abspielen.

**Stimmen (Teil 1):** Dramaturgen = GPT / Claude — **Petra (Premium)** / **Viktor (Enhanced)** auf macOS (`TTS_VOICE_OPENAI` / `TTS_VOICE_ANTHROPIC`). Stücktext = **Stimme A / B / Erzähler** (`TTS_VOICE_AI_A` / `AI_B` / `NARRATOR`); Sätze rotieren zwischen diesen drei Stimmen, nie die Dramaturgen-Stimmen.

**Konfiguration:** `DRAMATURGY_STATEMENTS_PER_DRAMATURG=2` (Default) begrenzt Beiträge pro Dramaturg im Workshop.

**Medien-Datenbank:** Videos/Recordings aus Pixera-Katalog (`media/video/Video Übersicht.csv`, OSC `/pixera/args/cue/apply`). **Sound:** `media/sound/Sound Übersicht.csv` (MIDI-Cues → Ableton). Licht: `data/light_scenes.json`. API: `GET /api/v1/media/catalog`.

`DIRECTOR_DRAMATURGY_MODE=llm` (Standard) oder `rules` für regelbasierte Cues.

### Teil 2 — Anarchische Inszenierung

Separater Modus für mehrere Tier-Szenen zum Thema **Geld** (z. B. Elfriede Jelinek — *Unter Tieren*). Persistenz: `data/inszenierungen/{id}.json`.

```text
/inszenierung          Szenen importieren (TXT/JSON, Batch-Upload)
        ↓
/inszenierung/analyse  KI: Gesamtkonzept, Geld-Achsen, Anarchie-Kurve
        ↓
/inszenierung/komposition  KI wählt Textausschnitte + Regie pro Moment
        ↓
/inszenierung/auffuehrung  Anarchie-Player (parallele Stimmen, Layer-Cues)
```

**Sprache pro Moment (`speech_mode`):**

| Modus | Bedeutung |
|-------|-----------|
| `avatar_video` | Gesprochener Text steckt im Pixera-Avatar-Clip — kein TTS |
| `tts` | KI vertont den Jelinek-Ausschnitt (Teil-2-Stimmen: Eddy / Sandy / Helena) |
| `silent` | Nur Video/Sound/Licht-Cues |

Die KI matcht Ausschnitte an den **Avatar-Textkatalog** ([`media/video/Avatar Textzuordnung.csv`](media/video/Avatar%20Textzuordnung.csv), API `GET /api/v1/media/avatar-speech`). Frühe Momente bevorzugen Avatar-Videos; mit steigendem `anarchy_level` überlagern sich Stimmen, Clips auf mehreren Beamern (`layer`-Modus) und Sounds.

**Schnellstart Teil 2:**

```bash
make run
# Browser: http://localhost:3003/inszenierung
```

1. Korpus anlegen → Szenen hochladen  
2. Analyse → Gesamtkonzept prüfen  
3. Komposition → Momente reviewen (Badge: `Avatar BK3`, `KI Stimme B`, …)  
4. Aufführung → TTS-Puffer (nur `tts`-Momente) → Play  

Vollständige Anleitung: [`docs/teil2_inszenierung.md`](docs/teil2_inszenierung.md)

### Debatte (Legacy) — Show-Modus

Mit **Show-Modus AN** (Standard) läuft pro Beitrag eine sichtbare Sequenz:

1. Text erscheint mit **Regie-Karte** (Stimmung, geplante Cues, OSC-Vorschau)
2. **TTS** startet automatisch
3. Beim Start der Stimme: `POST /director/execute` — Cues gehen parallel zur Stimme (Licht → Sound → Video, ~150 ms Staffelung)
4. Regie-Karte zeigt Status und gesendete OSC-Befehle
5. Nächster Turn erst, wenn die Queue frei ist

**Show-Modus AUS:** wie bisher — Text sofort, Vertonung manuell per Klick.

**Maschine starten** (nach der Debatte): spielt den gesamten Stücktext nacheinander ab — mit Satz-für-Satz-Highlight im aktuellen Beitrag, sichtbaren Cues/OSC und Fortschrittsanzeige oben.

1. **Thema** eingeben → **Diskussion starten**
2. Beiträge erscheinen live mit Denk-Indikator
3. **Weiter diskutieren** — weitere Runden anhängen
4. **Vertonung** (nur ohne Show-Modus) — einzelne Beiträge oder ganzes Gespräch abspielen
5. Link **Live-Regie →** führt zur Operator-Oberfläche

OSC-Befehle sind sichtbar in der Regie-Karte unter jedem Beitrag und im Operator-Panel unter **Letzte OSC-Befehle**. Im Terminal: `docker compose logs backend` (bei `OSC_LOG_COMMANDS=true`).

### Live-Regie (`/director`)

Siehe [Live-Regie (Director)](#live-regie-director).

---

## Live-Regie (Director)

### Ablauf

Im **Show-Modus** (`DIRECTOR_EXECUTE_MODE=sequenced`): Planung bei jedem Turn, OSC-Ausführung erst wenn die Debatten-UI TTS startet (`POST /director/execute`).

```text
KI spricht Text
    ↓
DialogueEvent (Speaker, Text, Tags, Mood, Intensity)
    ↓
DramaturgyEngine wählt Cues aus data/media.json
    ↓
CueScheduler prüft Safety + Mindestabstände
    ↓
plan() → geplante OSC-Befehle an UI
    ↓
execute() (Show-Modus) → OSC → TouchDesigner + Sound/Light
    ↓
Entscheidung in logs/director.log + last_osc_commands im Status
```

### Operator-UI

- Letzter Text-Event und letzte Regieentscheidung
- Safety-Flags: Autopilot, Visuals, Sound, Licht, Blackout-Sperre
- **Emergency Stop** — stoppt alle Ausgaben
- **Record Start/Stop** — Live-Aufnahme in TouchDesigner anstoßen

### Manueller Test (ohne Debatte)

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

### Medien-Datenbank

| Datei | Inhalt |
|-------|--------|
| [`data/media.json`](data/media.json) | Videoclips und Sounds mit Tags, Moods, Intensität |
| [`data/light_scenes.json`](data/light_scenes.json) | Lichtstimmungen mit DMX-Werten |
| [`data/dramaturgy_rules.json`](data/dramaturgy_rules.json) | Keyword-Regeln, Mindestabstände zwischen Cues |

Echte Mediendateien unter `media/video/` und `media/audio/` ablegen (Platzhalter-Ordner sind vorhanden).

---

## TouchDesigner

OSC-Empfänger auf Port **7000** einrichten. Adressen wie `/visual/play_clip`, `/visual/blackout`, `/sound/trigger`.

Vollständige Anleitung: [`touchdesigner/README_touchdesigner_setup.md`](touchdesigner/README_touchdesigner_setup.md)

---

## Projektstruktur

```
Theatermaschine/
├── backend/                    # FastAPI Backend (Debatte + Director)
│   ├── app/
│   │   ├── api/routes/         # HTTP-Endpunkte
│   │   ├── director/           # Live-Regie (Kernmodul)
│   │   ├── services/           # KI-Debatte, TTS
│   │   ├── db/                 # PostgreSQL
│   │   ├── schemas/            # Pydantic Request/Response
│   │   └── core/               # Config, Logging
│   ├── tests/
│   ├── Dockerfile
│   ├── run-native.sh           # Backend nativ (MIDI/Ableton, Python 3.11)
│   └── .env.example
├── frontend/                   # Next.js UI
│   ├── app/
│   │   ├── page.tsx            # Debatten-Oberfläche
│   │   ├── dramaturgie/        # Teil 1: Dramaturgie-Workshop
│   │   ├── inszenierung/       # Teil 2: Korpus, Analyse, Komposition, Aufführung
│   │   └── director/page.tsx   # Operator-UI
│   ├── components/chat/
│   └── lib/api/
├── data/                       # Medien-Katalog (JSON)
├── media/                      # Echte Video/Audio-Dateien
├── touchdesigner/              # TD-Setup-Dokumentation
├── logs/                       # Director-Log (generiert, gitignored)
├── docker-compose.yml
├── docker-compose.native.yml   # Postgres/Redis auf localhost (Backend nativ für MIDI)
├── PLAN.md                     # Entwicklungsplan Live-Regie
└── README.md
```

---

## Code-Übersicht: Was liegt wo?

### Backend — Debatte & Infrastruktur

| Pfad | Aufgabe |
|------|---------|
| [`backend/app/main.py`](backend/app/main.py) | FastAPI-App, Router-Registrierung |
| [`backend/app/core/config.py`](backend/app/core/config.py) | Alle Env-Variablen (KI, TTS, Director, OSC) |
| [`backend/app/api/routes/debate.py`](backend/app/api/routes/debate.py) | Debatten-SSE, TTS; **Hook zur Regie** nach jedem Turn |
| [`backend/app/api/routes/health.py`](backend/app/api/routes/health.py) | Health-Check |
| [`backend/app/services/debate_service.py`](backend/app/services/debate_service.py) | GPT ↔ Claude Wechsel, Streaming-Events |
| [`backend/app/services/ai_service.py`](backend/app/services/ai_service.py) | OpenAI/Anthropic Provider-Aufrufe |
| [`backend/app/services/tts_service.py`](backend/app/services/tts_service.py) | TTS-Orchestrierung |
| [`backend/app/services/tts/`](backend/app/services/tts/) | `mac_say.py` (Siri), `edge_provider.py` (Docker) |
| [`backend/app/services/tts/voice_map.py`](backend/app/services/tts/voice_map.py) | Stimmen-Profile: `dramaturg`, `performance`, `inszenierung` |
| [`backend/app/db/`](backend/app/db/) | SQLAlchemy Session, Conversation/Message speichern |
| [`backend/app/models/entities.py`](backend/app/models/entities.py) | DB-Entitäten |
| [`backend/app/schemas/debate.py`](backend/app/schemas/debate.py) | Debatten Request/Response-Modelle |

### Backend — Live-Regie (`backend/app/director/`)

| Pfad | Aufgabe |
|------|---------|
| [`pipeline.py`](backend/app/director/pipeline.py) | **Zentraler Orchestrator** — verbindet alle Schritte |
| [`dialogue/models.py`](backend/app/director/dialogue/models.py) | `DialogueEvent` (Text, Speaker, Mood, Tags, …) |
| [`dialogue/builder.py`](backend/app/director/dialogue/builder.py) | Baut `DialogueEvent` aus Debatten-Turn |
| [`dramaturgy/rules.py`](backend/app/director/dramaturgy/rules.py) | Keyword-/Mood-Analyse, Intensitäts-Heuristik |
| [`dramaturgy/engine.py`](backend/app/director/dramaturgy/engine.py) | **Regelbasierte Regie** — wählt Cues aus Media-DB |
| [`dramaturgy/llm_director.py`](backend/app/director/dramaturgy/llm_director.py) | Stub für KI-Regie (Phase 5) |
| [`media/database.py`](backend/app/director/media/database.py) | Lädt `data/*.json`, sucht passende Clips/Sounds/Licht |
| [`media/selector.py`](backend/app/director/media/selector.py) | Auswahl mit Wiederholungsvermeidung |
| [`cues/cue_models.py`](backend/app/director/cues/cue_models.py) | `VisualCue`, `SoundCue`, `LightCue`, `DramaturgyDecision` |
| [`cues/scheduler.py`](backend/app/director/cues/scheduler.py) | Mindestabstände, Cue-Kollisionen verhindern |
| [`cues/safety.py`](backend/app/director/cues/safety.py) | `SafetyState` — Autopilot, Overrides, Emergency |
| [`outputs/touchdesigner.py`](backend/app/director/outputs/touchdesigner.py) | **OSC-Bridge** zu TouchDesigner |
| [`outputs/sound.py`](backend/app/director/outputs/sound.py) | Sound per MIDI (Ableton) oder OSC |
| [`outputs/lighting.py`](backend/app/director/outputs/lighting.py) | Licht per TCP ans Pult (`light_tcp.py`) oder optional OSC |
| [`outputs/logger.py`](backend/app/director/outputs/logger.py) | Schreibt Entscheidungen nach `logs/director.log` |
| [`recording.py`](backend/app/director/recording.py) | Live-Aufnahme Start/Stop (Phase 4) |
| [`api/routes/director.py`](backend/app/api/routes/director.py) | REST + SSE für Operator-UI |

### Backend — Teil 2 Inszenierung

| Pfad | Aufgabe |
|------|---------|
| [`backend/app/api/routes/inszenierung.py`](backend/app/api/routes/inszenierung.py) | CRUD Korpus, SSE Analyse & Komposition |
| [`backend/app/services/inszenierung_analyse_service.py`](backend/app/services/inszenierung_analyse_service.py) | Gesamtkonzept aus Tier-Szenen |
| [`backend/app/services/inszenierung_komposition_service.py`](backend/app/services/inszenierung_komposition_service.py) | Momente, `speech_mode`, Avatar-Matching |
| [`backend/app/services/avatar_speech_catalog.py`](backend/app/services/avatar_speech_catalog.py) | Avatar-Textkatalog (DEL/BK/LG/PET/WO) |
| [`backend/app/services/inszenierung_import.py`](backend/app/services/inszenierung_import.py) | Szenen-Import aus TXT/JSON |
| [`data/inszenierungen/`](data/inszenierungen/) | Persistierte Korpora & Kompositionen |
| [`data/avatar_speech.json`](data/avatar_speech.json) | Cache des Avatar-Katalogs |

### Frontend

| Pfad | Aufgabe |
|------|---------|
| [`frontend/app/page.tsx`](frontend/app/page.tsx) | Debatten-UI, SSE-Stream, TTS-Wiedergabe |
| [`frontend/app/director/page.tsx`](frontend/app/director/page.tsx) | **Operator-Panel** — Safety, Status, Recording |
| [`frontend/app/inszenierung/`](frontend/app/inszenierung/) | **Teil 2** — Import, Analyse, Komposition, Anarchie-Player |
| [`frontend/features/inszenierung/anarchyPlayback.ts`](frontend/features/inszenierung/anarchyPlayback.ts) | Parallele Stimmen + Layer-Cues |
| [`frontend/lib/api/client.ts`](frontend/lib/api/client.ts) | Debatten-API + SSE-Parser |
| [`frontend/lib/api/director.ts`](frontend/lib/api/director.ts) | Director-API + Event-Stream |
| [`frontend/components/chat/`](frontend/components/chat/) | Nachrichten, Denk-Bubble, Composer |

### Daten & Medien

| Pfad | Aufgabe |
|------|---------|
| [`data/media.json`](data/media.json) | Katalog: Videos + Sounds mit dramaturgischen Metadaten |
| [`data/light_scenes.json`](data/light_scenes.json) | Lichtstimmungen (DMX-Kanäle) |
| [`data/dramaturgy_rules.json`](data/dramaturgy_rules.json) | Keyword-Mapping, Cue-Mindestabstände |
| [`media/video/`](media/video/) | Echte Videodateien (`.mp4`), `Video Übersicht.csv`, `Avatar Textzuordnung.csv` |
| [`media/audio/`](media/audio/) | Echte Audiodateien (`.wav`) |
| [`media/recordings/`](media/recordings/) | Live-Aufnahmen aus TouchDesigner |

### Tests

| Pfad | Prüft |
|------|-------|
| [`backend/tests/test_dramaturgy.py`](backend/tests/test_dramaturgy.py) | Textanalyse, Cue-Auswahl |
| [`backend/tests/test_media_selector.py`](backend/tests/test_media_selector.py) | Media-Matching, Wiederholung |
| [`backend/tests/test_cue_scheduler.py`](backend/tests/test_cue_scheduler.py) | Safety, Scheduler |
| [`backend/tests/test_touchdesigner_bridge.py`](backend/tests/test_touchdesigner_bridge.py) | OSC-Payload |
| [`backend/tests/test_director_api.py`](backend/tests/test_director_api.py) | Director REST-Endpunkte |
| [`backend/tests/test_inszenierung_*.py`](backend/tests/) | Teil 2: Import, Validierung, Komposition, Avatar-Katalog |
| [`frontend/features/inszenierung/anarchyPlayback.test.ts`](frontend/features/inszenierung/anarchyPlayback.test.ts) | Anarchie-Scheduling & Speech-Labels |

---

## API-Endpunkte

### Debatte & TTS

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `POST` | `/api/v1/debate/stream` | Debatte starten/fortsetzen (SSE, enthält optional `director`) |
| `POST` | `/api/v1/tts/speak` | Text zu Audio (`profile` optional) |
| `GET` | `/api/v1/tts/status` | TTS-Verfügbarkeit |
| `GET` | `/api/v1/health` | Health-Check |

### Teil 2 Inszenierung

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `POST` | `/api/v1/inszenierung` | Korpus anlegen |
| `GET` | `/api/v1/inszenierung/{id}` | Korpus laden |
| `POST` | `/api/v1/inszenierung/{id}/scenes/upload` | Szenen-Dateien importieren |
| `POST` | `/api/v1/inszenierung/{id}/analyse/stream` | Analyse-Workshop (SSE) |
| `POST` | `/api/v1/inszenierung/{id}/komposition/stream` | Komposition (SSE) |
| `GET` | `/api/v1/media/avatar-speech` | Avatar-Textkatalog |
| `POST` | `/api/v1/director/execute-layered` | Layer-Cues für Anarchie-Player |

### Live-Regie (Director)

| Methode | Pfad | Beschreibung |
|---------|------|--------------|
| `POST` | `/api/v1/director/dialogue-event` | Text-Event manuell einspeisen |
| `GET` | `/api/v1/director/status` | Status, letzte Entscheidung, Safety-Flags |
| `PATCH` | `/api/v1/director/safety` | Flags umschalten |
| `POST` | `/api/v1/director/emergency-stop` | Alles stoppen |
| `POST` | `/api/v1/director/emergency-clear` | Emergency aufheben |
| `POST` | `/api/v1/director/record/start` | Aufnahme starten |
| `POST` | `/api/v1/director/record/stop` | Aufnahme stoppen |
| `GET` | `/api/v1/director/events` | Live-Updates (SSE) |

---

## Entwicklung & Tests

### Backend-Tests (Docker — empfohlen)

```bash
docker compose run --rm --no-deps backend sh -c \
  "pip install pytest pytest-asyncio -q && PYTHONPATH=/app pytest -q"
```

Einzelne Tests, z. B. Stimmen:

```bash
docker compose run --rm --no-deps backend sh -c \
  "pip install pytest pytest-asyncio -q && PYTHONPATH=/app pytest tests/test_voice_map.py -q"
```

### Frontend-Tests (Docker)

```bash
docker compose run --rm --no-deps frontend npm test -- --run
```

### Backend-Tests (lokal, Python 3.11+)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

### Backend nativ (Sound / Ableton / Siri-TTS)

Für MIDI und macOS `say` — **nicht** mit `python3` 3.9:

```bash
# Projektroot: Postgres/Redis/Frontend in Docker, Ports für localhost
docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis frontend
docker compose stop backend

# Backend nativ (Python 3.11)
cd backend && ./run-native.sh
```

Frontend bleibt unter http://localhost:3003 (Docker). Sound-Test: http://localhost:3003/technik

### Lokal ohne Docker (alles nativ, optional)

```bash
docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis
cd backend && ./run-native.sh
# zweites Terminal:
cd frontend && npm install && npm run dev   # → http://localhost:3000
```

---

## Häufige Probleme

| Problem | Lösung |
|---------|--------|
| Änderungen wirken nicht | Im **Projektroot** starten (`cd Theatermaschine`), nicht in `backend/`. Dann `docker compose up --build`. Bei hartnäckigem Cache: `docker compose build --no-cache` |
| Stücke / Exporte weg nach Rebuild | `data/` ist jetzt gemountet — alte Container ohne Volume hatten Daten nur im Image |
| Port 8000 belegt | Alten Stack stoppen: `docker stop aidebatte-backend-1 …` oder `docker compose down` im anderen Projekt |
| Port 3003 oder 8000 belegt | Alten Docker-Stack stoppen: `docker ps` → `docker stop …` |
| Postgres/Redis-Konflikt | Standard-Docker: Ports nur intern. Für natives Backend: `docker-compose.native.yml` verwenden |
| TTS nicht verfügbar | `curl localhost:8000/api/v1/tts/status`; in Docker edge-tts, auf Mac `say` |
| Director sendet kein OSC | `OSC_DRY_RUN=false` setzen; `OSC_HOST=host.docker.internal` in Docker auf Mac |
| **Sound: kein MIDI / rtmidi-Fehler** | Backend **nicht** in Docker — `cd backend && ./run-native.sh`. Log: `grep -i midi` |
| **Sound: Port not found** | Deutscher Mac: `SOUND_MIDI_PORT="IAC-Treiber Bus 1"`; Ableton MIDI From gleich setzen |
| **Sound: Log OK, kein Ton in Ableton** | Monitor `In`, Arm an, Drum Rack auf **C1** (Note 36), nicht C5 |
| **python3 / pip Fehler 3.9** | `brew install python@3.11`, dann `./run-native.sh` (nicht System-`python3`) |
| **OSC_HOST nodename** | Nativ: `OSC_HOST=127.0.0.1` — `run-native.sh` setzt das automatisch |
| Keine Videoclips | Dateien in `media/video/` ablegen; IDs müssen zur CSV passen |
| Cues werden blockiert | Operator-UI: Autopilot an? Mindestabstand abgewartet? `/director/status` prüfen |
| CORS-Fehler | `CORS_ORIGINS='["http://localhost:3003"]'` in `backend/.env` (Docker) |

---

## Lizenz & Hinweise

- API-Keys nur in `backend/.env`, nie ins Git.
- OpenAI/Anthropic-Nutzung kann Kosten verursachen (TTS ist kostenlos).
- Für Produktion: Rate-Limits, HTTPS, Secrets-Management ergänzen.
