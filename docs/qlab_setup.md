# QLab lokal für Video- und Licht-OSC testen

Theatermaschine sendet Video als **Pixera-OSC** (`/pixera/args/cue/apply`) und Licht optional als **Mirror-OSC** (`/light/set_scene`). QLab versteht das nicht direkt — ein kleiner Relay auf dem Mac übersetzt die Befehle.

```
Theatermaschine  →  127.0.0.1:8990  →  pixera_qlab_relay  →  QLab :53000
                 →  127.0.0.1:7000  →       (Licht)
QLab cue/stop    →  Relay  →  /avatar/done  →  Theatermaschine :8991  (optional, Avatar-Gate)
```

Avatar-Videos können nach Clip-Ende zurückmelden, damit Erzähler und nächster Avatar bei Drift synchron bleiben (sonst parallel) — siehe [avatar_done_gate.md](avatar_done_gate.md).

Auf der Bühne entfällt der Relay; Pixera und EOS empfangen die Befehle direkt.

---

## 1. Backend (.env)

Lokal in `backend/.env`:

```env
OSC_DRY_RUN=false
VISUAL_OUTPUT=pixera
PIXERA_OSC_HOST=127.0.0.1
PIXERA_OSC_PORT=8990

# Licht-Simulation via QLab (Relay auf Port 7000 — kein EOS-Pult)
LIGHT_OUTPUT=mirror
OSC_HOST=127.0.0.1
OSC_PORT=7000
```

`LIGHT_OUTPUT=mirror` sendet nur `/light/set_scene` an den Relay — **kein TCP** zu `10.101.90.112:3032`. Auf der Bühne: `LIGHT_OUTPUT=tcp`.

TouchDesigner nicht parallel auf Port 7000 starten.

Backend **nativ** starten (`make run`), nicht Docker-Backend.

---

## 2. QLab-Workspace

### OSC Access

1. QLab-Workspace öffnen
2. **Workspace Settings** → **Network** → **OSC Access**
3. Haken bei **View** und **Control**
4. OSC Listening Port: **53000** (Standard)

Ohne **Control** kommen OSC-Nachrichten an, aber Cues starten nicht.

### Video-Cues

Pro Videodatei einen **Video Cue** mit **Cue-Nummer = exakter Pixera-Name** (Spalte `qlab_cue_number`).

**Fertige Listen** (aus OSC-Dateien generiert):

| Datei | Inhalt |
|-------|--------|
| [`data/qlab_cue_list_all.csv`](../data/qlab_cue_list_all.csv) | alle 404 Cues (4 Projektoren) |
| [`data/qlab_cue_list_rz21.csv`](../data/qlab_cue_list_rz21.csv) | nur RZ21 (101 Cues) — empfohlen für lokalen Test |

Neu erzeugen:

```bash
make qlab-cue-list
```

Quellen: `OSCBefehlliste.txt` (Datenbank-Clips), `OSCBefehllisteAvatare.txt`, `OSCBefehllisteOhneAvatare.txt`.

Wichtig: Spalte **`qlab_cue_number`** ist maßgeblich — das sendet Theatermaschine (inkl. Aliase, z. B. `BAK1_Nicolas_Pflanzen` statt `BAK1_NicolasPflanzen3`). Spalte `osc_list_name` ist nur Referenz.

| Cue-Nummer | Beispiel-Clip |
|------------|---------------|
| `KI_RZ21.Clyde` | Clyde auf RZ21 |
| `KI_RZ21.BAK1_Nicolas_Pflanzen` | Avatar BAK1 (Alias!) |
| `KI_RZ21.AffenSlowOdysee` | Atmosphäre ohne Avatar |

Für den Start reicht oft nur **ein** Projektor (`qlab_cue_list_rz21.csv`). Theatermaschine schickt bei Standard-Clips vier Befehle — fehlende Cues in QLab werden ignoriert.

### Viele Cues auf einmal anlegen (schnellster Weg)

QLab hat keinen CSV-Import. Zwei praktische Wege:

**A) Python-Importer (empfohlen)** — zuverlässiger als reines AppleScript:

```bash
make qlab-cue-list
make qlab-import VIDEO_DIR="/Pfad/zu/deinen/Videos" SOURCE=avatar
```

Nur Avatar-Clips (Ordner wie `KI Test/Avatare`): `SOURCE=avatar` setzen — sonst sucht das Skript auch Database- und Atmosphäre-Clips, die in dem Ordner nicht liegen.

Oder direkt:

```bash
python3 tools/qlab_import_video_cues.py "/Pfad/zu/deinen/Videos" data/qlab_cue_list_rz21.csv
python3 tools/qlab_import_video_cues.py "/Pfad/zu/deinen/Videos" data/qlab_cue_list_rz21.csv --dry-run
```

Voraussetzungen: QLab offen, Ziel-Workspace im Vordergrund, Videodateien im Ordner (`.mp4`/`.mov`). Matcht Dateinamen grob an `clip_part`.

**A2) AppleScript** (Alternative):

```bash
osascript tools/qlab_import_video_cues.applescript "/Pfad/zu/deinen/Videos" "data/qlab_cue_list_rz21.csv"
```

**B) Drag & Drop + Nummern manuell** — alle Videos in QLab ziehen (erzeugt Cues 1…n), dann pro Cue im Tab **Basics** das Feld **Number** aus der CSV setzen. Für 21 Clips okay, für 100+ eher A).

**C) Bereits angelegte Cues umbenennen** — wenn du schon Cues 1–21 hast: nur **Number** je Cue aus `qlab_cue_list_rz21.csv` eintragen, Dateien können bleiben.

### Preview: Video-Stages pro Projektor

Für die Vorschau auf dem Mac alle Projektoren auf separate QLab-Stages legen:

| Cue-Präfix | Video Output Stage |
|------------|-------------------|
| `KI_RZ21.*` | Stage 1 |
| `KI_Adam.*` | Stage 2 |
| `KI_Eva.*` | Stage 3 |
| `KI_LED.*` | Stage 4 |

```bash
make qlab-stages
```

QLab muss offen sein. Das Skript setzt bei allen **Video Cues** die `stage number` anhand der Cue-Nummer. Nach neuem Import erneut ausführen.

### Clip-Dauern aus QLab (ms)

Die Numbers-Spalte «Zeit» ist nur sekundengenau. Für Beamer-Sperren und Avatar-Timing die echten QLab-Dauern übernehmen:

```bash
make qlab-sync-durations
```

Schreibt millisekundengenau nach `media/video/Avatar Textzuordnung.csv`, `data/avatar_speech.json` und `data/video_cues.json`. QLab-Workspace muss offen sein. Nach `make avatar-import` (Numbers) erneut ausführen — sonst überschreibt der Import wieder Sekundenwerte.

Bereits vorbereitete Inszenierungen speichern alte `duration_ms` — Prepare erneut laufen lassen.

In QLab unter **Workspace Settings → Video → Video Outputs** sollten Stage 1–4 auf verschiedene Bildschirme/Fenster geroutet sein (z. B. vier Audition-Fenster oder Monitor-Layouts).

### Video-Ausgabe

- **Video Output Patch** auf Mac-Bildschirm oder Test-Monitor
- Workspace nicht auf Pause/Panic

### Manueller QLab-Test (ohne Relay)

```bash
echo "/cue/KI_RZ21.Clyde/start" | nc -u -w1 127.0.0.1 53535
```

Wenn der Cue startet, ist QLab korrekt konfiguriert.

### Licht-Cues (Simulation)

Für lokale Licht-Timing-Tests ohne EOS-Pult: Light-Cues in QLab, gesteuert über den gleichen Relay.

**Quelle:** `data/light_scenes.json` (abgeleitet aus `media/light/Kanal Übersicht.xlsx` / `Light Channels KI.txt`).

| Datei | Inhalt |
|-------|--------|
| [`data/qlab_light_cue_list.csv`](../data/qlab_light_cue_list.csv) | 19 Lichtstimmungen (`scene_id` = Cue-Nummer) |

Neu erzeugen:

```bash
make qlab-light-cue-list
```

**Cue-Nummer = `scene_id`** — das sendet Theatermaschine via Mirror-OSC, z. B. `saallicht`, `gegenlicht_weich`, `blackout`.

#### Patch einmalig anlegen (automatisch)

QLab hat kein AppleScript für den Light Patch — das Skript steuert die Workspace Settings per UI:

```bash
make qlab-light-patch
```

Voraussetzungen: QLab offen, Ziel-Workspace im Vordergrund. Beim ersten Lauf ggf. **Bedienungshilfen** für Terminal/Cursor erlauben (Systemeinstellungen → Datenschutz).

Das Skript legt Instrument **`TMPREVIEW`** an (Generic → RGB Fixture with Intensity) und patched es per Auto-Patch.

Manuell (falls Automation scheitert): Workspace Settings → Lighting → Patch → + Instrument, Name **`TMPREVIEW`** (kein Unterstrich — QLab erlaubt `_` in Instrument-Namen nicht), Definition **RGB Fixture with Intensity**, Auto-Patch.

#### Cues importieren

```bash
make qlab-light-cue-list
make qlab-light-patch    # TMPREVIEW anlegen
make qlab-light-import   # Patch + Cues (oder nur import wenn Patch schon da)
```

Dry-run / bestehende Cues aktualisieren (z. B. nach Umbenennung `TM_PREVIEW` → `TMPREVIEW`):

```bash
python3 tools/qlab_import_light_cues.py data/qlab_light_cue_list.csv --dry-run
python3 tools/qlab_import_light_cues.py data/qlab_light_cue_list.csv --replace-existing
```

Jeder Light-Cue enthält RGB-Werte für `TMPREVIEW` (Stimmungs-Näherung, kein EOS-Kanalmodell). Kanäle/Gruppen stehen als Kommentar in der Cue.

#### Manueller Licht-Test (Technik-Seite oder Terminal)

Relay läuft (`make qlab-relay`), Backend mit `LIGHT_OUTPUT=mirror`, dann:

- Browser: **Technik-Test** → Licht-Szene wählen → **Signal senden** (kein EOS-TCP nötig)
- Unten erscheinen die letzten `[light]`-Zeilen aus `logs/osc.log`
- QLab: **Window → Light Dashboard** (`TMPREVIEW`) und **Window → Status** (OSC)

Terminal:

```bash
echo "/light/set_scene saallicht 4" | nc -u -w1 127.0.0.1 7000
echo "/light/blackout" | nc -u -w1 127.0.0.1 7000
```

Mapping:

```
/light/set_scene  "saallicht,gegenlicht_weich"  4.0  →  /cue/saallicht/start
                                                       →  /cue/gegenlicht_weich/start
/light/blackout                                       →  /cue/blackout/start
```

---

## 3. Relay starten

```bash
make qlab-relay
```

Oder direkt:

```bash
cd backend && .venv/bin/python ../tools/pixera_qlab_relay.py -v
```

Umgebungsvariablen (optional):

| Variable | Standard | Bedeutung |
|----------|----------|-----------|
| `PIXERA_LISTEN_HOST` | `127.0.0.1` | Relay lauscht hier |
| `PIXERA_LISTEN_PORT` | `8990` | = `PIXERA_OSC_PORT` im Backend (Video) |
| `LIGHT_LISTEN_PORT` | `7000` | = `OSC_PORT` wenn `LIGHT_OSC_MIRROR=true` |
| `QLAB_HOST` | `127.0.0.1` | QLab-Mac |
| `QLAB_PORT` | `53000` | QLab OSC-Port |
| `AVATAR_DONE_HOST` | `127.0.0.1` | Ziel für `/avatar/done` (Backend-Listener) |
| `AVATAR_DONE_PORT` | `8991` | = `AVATAR_DONE_OSC_PORT` |
| `QLAB_FEEDBACK_KEEPALIVE_S` | `30` | `/listen` + `/udpKeepAlive` Intervall |

Avatar-Done-Gate (Sync bei Drift, sonst parallel): [avatar_done_gate.md](avatar_done_gate.md). Abschalten am Relay: `--no-qlab-feedback`.

Video-Mapping:

```
/pixera/args/cue/apply  "KI_RZ21.Clyde"  →  /cue/KI_RZ21.Clyde/start
```

Licht-Mapping (wenn Mirror aktiv):

```
/light/set_scene  "saallicht"  4.0  →  /cue/saallicht/start
/light/blackout                     →  /cue/blackout/start
```

---

## 4. Test-Ablauf

1. QLab mit Video- und Licht-Test-Cues öffnen
2. `make qlab-relay` (eigenes Terminal)
3. `make run` (Backend nativ, `.env` mit Mirror siehe oben)
4. Browser: http://localhost:3003/technik
5. Clip wählen (z. B. `clyde`) → **Video senden**
6. Licht-Stimmung wählen → **Licht senden** (oder Aufführung mit Licht-Cues)
7. Prüfen:
   - `logs/osc.log` — Pixera + `/light/set_scene`
   - Relay-Terminal — `relay pixera …` / `relay light …`
   - QLab — Video bzw. Light-Cue startet

---

## 5. Auf der Bühne umschalten

1. Relay beenden (Ctrl+C)
2. In `backend/.env`:

```env
PIXERA_OSC_HOST=172.27.27.1
PIXERA_OSC_PORT=8990
```

3. Backend neu starten

Gleicher Katalog (`video_cues.json`), gleiche Inszenierung — nur das Ziel ändert sich. QLab auf der Bühne ist nicht nötig, wenn Pixera die Videos ausspielt.

---

## Was nicht funktioniert

| Ansatz | Problem |
|--------|---------|
| `PIXERA_OSC_PORT=53000` ohne Relay | Falsches OSC-Format für QLab |
| `OSC_DRY_RUN=true` | Nur Logging, kein UDP |
| `VISUAL_OUTPUT=touchdesigner` | Andere Adressen (`/visual/play_clip`) |
| QLab „OSC Controls“ | Nur Workspace-Aktionen, nicht pro Video-Cue |
| `LIGHT_OUTPUT=mirror` ohne Relay | OSC geht ins Leere — `make qlab-relay` starten |
| `LIGHT_OUTPUT=tcp` + lokaler Test | EOS-Timeouts — für QLab `LIGHT_OUTPUT=mirror` setzen |
| TouchDesigner + Relay auf `:7000` | Port-Konflikt — nur eines gleichzeitig |
