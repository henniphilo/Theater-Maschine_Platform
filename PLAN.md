# Entwicklungsplan: KI-gestützte Live-Regie für Theater mit TouchDesigner, Video, Ton und Licht

## 1. Ziel des Programms

Das Programm soll während einer Live-Theateraufführung dramaturgische Entscheidungen treffen und diese technisch ausführen. Grundlage ist ein bestehendes KI-Dialogsystem, in dem zwei KIs über ein Thema sprechen. Während dieser KI-generierte oder KI-gesprochene Text läuft, soll ein Regie-System entscheiden:

* Welche Videoclips oder Live-Aufnahmen auf dem Beamer erscheinen
* Welche Musik, Sound-Cues oder Tonsignale ausgelöst werden
* Welche Lichtstimmungen oder Licht-Cues aktiviert werden
* Wann Bildmaterial live aufgenommen und später wieder abgespielt wird
* Welche Inhalte aus einer vorbereiteten Medien-Datenbank verwendet werden

Das System soll nicht vollständig autonom und unkontrollierbar sein, sondern als **semi-autonome Live-Regie** funktionieren: KI schlägt vor und steuert, aber ein Mensch kann jederzeit eingreifen.

---

## 2. Grundidee der Architektur

Das Projekt besteht aus vier Hauptteilen:

### A. KI-Dialog / Textquelle

Das bestehende Programm mit zwei KIs bleibt die dramaturgische Textquelle.

Es liefert live:

* aktuellen gesprochenen Text
* Sprecher: KI A oder KI B
* Thema
* emotionale Färbung
* dramaturgische Situation
* mögliche Schlüsselwörter
* Timing-Informationen

Beispiel-Output:

```json
{
  "speaker": "AI_A",
  "text": "Vielleicht ist Erinnerung nur eine technische Störung.",
  "topic": "Erinnerung",
  "mood": "melancholisch",
  "intensity": 0.72,
  "timestamp": 183.4
}
```

---

### B. Dramaturgie-Engine

Die Dramaturgie-Engine interpretiert den Text und entscheidet, was auf der Bühne technisch passieren soll.

Sie bekommt den Text der KI und erzeugt daraus Regieentscheidungen:

```json
{
  "visual": {
    "action": "play_clip",
    "clip_id": "memory_noise_03",
    "blend": "slow_fade",
    "opacity": 0.8
  },
  "sound": {
    "action": "trigger_cue",
    "cue_id": "low_drone_02",
    "volume": 0.6
  },
  "light": {
    "action": "set_scene",
    "scene_id": "cold_blue_low",
    "fade_time": 4.0
  },
  "reason": "Der Text spricht über Erinnerung und technische Störung; daher werden Archivbild, tiefer Drone und kaltes Licht kombiniert."
}
```

Wichtig: Die Dramaturgie-Engine sollte nicht direkt Geräte steuern. Sie erzeugt erst abstrakte Regie-Cues. Diese werden dann von spezialisierten Output-Modulen übersetzt.

---

### C. Output-Controller

Der Output-Controller übersetzt dramaturgische Entscheidungen in technische Befehle:

* Visuals → TouchDesigner via OSC, WebSocket oder lokale API
* Sound → OSC, MIDI, Ableton, QLab oder eigenes Audio-Modul
* Licht → DMX, Art-Net oder sACN
* Recording → Befehl an TouchDesigner, Livebild aufzuzeichnen
* Playback → Befehl an TouchDesigner, aufgezeichnetes Material wieder abzuspielen

Beispiel:

```json
{
  "target": "touchdesigner",
  "address": "/visual/play",
  "args": ["memory_noise_03", 0.8, "slow_fade"]
}
```

oder für Licht:

```json
{
  "target": "lighting",
  "protocol": "artnet",
  "universe": 0,
  "channels": {
    "1": 120,
    "2": 80,
    "3": 255
  },
  "fade_time": 4.0
}
```

---

### D. TouchDesigner-Setup

TouchDesigner übernimmt primär die visuelle Ebene:

* Abspielen vorbereiteter Videoclips
* Live-Eingang eines Kamerabildes
* Aufnahme des eingespeisten Videobildes
* Wiedergabe zuvor aufgezeichneter Aufnahmen
* Layering, Blending, Effekte, Feedback, Verzerrung
* Projektion auf Beamer
* optional: DMX/Art-Net-Ausgabe für Licht, falls das Licht direkt aus TouchDesigner gesteuert werden soll

Empfehlung: TouchDesigner sollte zunächst nur Visuals steuern. Licht und Ton können später entweder ebenfalls über TouchDesigner oder über den externen Orchestrator gesteuert werden.

---

## 3. Empfohlene technische Struktur

### Programmiersprache

Für den Orchestrator empfehle ich:

```text
Python
```

Begründung:

* gut für KI-Anbindung
* gut für OSC, MIDI, Datenbanken und Netzwerksteuerung
* gut mit TouchDesigner kombinierbar
* gut für schnelle Prototypen in Cursor

Mögliche Libraries:

```text
python-osc
fastapi
uvicorn
pydantic
sqlite
watchdog
python-rtmidi
```

Optional später:

```text
openai / lokales LLM
transformers
chromadb
sentence-transformers
```

---

## 4. Systemmodule

### Modul 1: `dialogue_input`

Dieses Modul empfängt den Text aus dem bestehenden KI-Gespräch.

Aufgaben:

* Text entgegennehmen
* Sprecher erkennen
* Zeitstempel speichern
* Text in Events umwandeln
* an Dramaturgie-Engine weitergeben

MVP-Version:

* Text kommt über eine lokale HTTP-API oder WebSocket rein

Beispiel-Endpunkt:

```text
POST /dialogue-event
```

---

### Modul 2: `dramaturgy_engine`

Dieses Modul trifft die künstlerischen Entscheidungen.

Es sollte zwei Modi geben:

#### Regelbasierter Modus

Am Anfang sollte das System noch nicht komplett frei mit KI entscheiden, sondern mit Regeln arbeiten:

```text
Wenn mood = melancholisch → kaltes Licht, langsame Videos
Wenn intensity > 0.8 → schneller Schnitt, stärkeres Licht, mehr Sound
Wenn Thema = Erinnerung → Archivmaterial oder verzerrte Aufnahmen
Wenn Thema = Körper → Nahaufnahmen, warme Hautfarben, tiefe Frequenzen
```

#### KI-gestützter Modus

Später kann ein LLM aus dem Text eine Regieentscheidung erzeugen.

Wichtig: Das LLM sollte nur aus einer begrenzten Liste erlaubter Aktionen wählen dürfen.

Beispiel:

```json
{
  "allowed_visual_actions": ["play_clip", "record_live", "play_recording", "fade_to_black"],
  "allowed_sound_actions": ["trigger_cue", "stop_cue", "set_volume"],
  "allowed_light_actions": ["set_scene", "fade_blackout", "pulse"]
}
```

Dadurch wird das System sicherer und bühnentauglicher.

---

### Modul 3: `media_database`

Eine Datenbank verwaltet verfügbare Clips, Sounds, Lichtstimmungen und aufgezeichnete Live-Videos.

Für den Anfang reicht SQLite oder eine JSON-Datei.

Beispiel für einen Videoclip:

```json
{
  "id": "memory_noise_03",
  "file": "media/video/memory_noise_03.mp4",
  "tags": ["memory", "glitch", "archive", "cold"],
  "mood": ["melancholisch", "unheimlich"],
  "intensity": 0.6,
  "duration": 42.0,
  "loopable": true
}
```

Beispiel für Sound:

```json
{
  "id": "low_drone_02",
  "file": "media/audio/low_drone_02.wav",
  "tags": ["drone", "tension", "dark"],
  "intensity": 0.7
}
```

Beispiel für Licht:

```json
{
  "id": "cold_blue_low",
  "description": "Kaltes, tiefes blaues Seitenlicht",
  "dmx": {
    "1": 30,
    "2": 60,
    "3": 180,
    "4": 0
  },
  "fade_time": 4.0
}
```

---

### Modul 4: `cue_scheduler`

Dieses Modul verhindert Chaos.

Es entscheidet:

* darf ein neuer Cue jetzt starten?
* überlagert er sich mit einem laufenden Cue?
* soll etwas langsam überblenden?
* gibt es Mindestabstände zwischen Cues?
* ist eine manuelle Sperre aktiv?

Beispiel-Regeln:

```text
Nicht mehr als ein großer Lichtwechsel alle 10 Sekunden.
Keine neuen Videos während eines wichtigen Textmoments, außer Intensität > 0.85.
Sound-Cues müssen weich ein- und ausgeblendet werden.
Blackout nur, wenn explizit erlaubt.
```

---

### Modul 5: `touchdesigner_bridge`

Dieses Modul sendet Befehle an TouchDesigner.

Empfohlene Kommunikation:

```text
OSC
```

Beispiele:

```text
/visual/play_clip memory_noise_03
/visual/set_opacity 0.8
/visual/fade 4.0
/visual/record_start recording_2026_06_08_001
/visual/record_stop
/visual/play_recording recording_2026_06_08_001
/visual/blackout
```

TouchDesigner empfängt diese Nachrichten und mapped sie auf:

* Movie File In TOP
* Switch TOP
* Composite TOP
* Level TOP
* Movie File Out TOP
* Container COMP Controls
* Custom Python callbacks

---

### Modul 6: `sound_bridge`

Für Ton gibt es drei mögliche Wege.

#### Option A: OSC zu QLab oder Ableton

Gut für Theater, weil QLab/Ableton oft bereits in Aufführungssettings genutzt werden.

Beispiele:

```text
/sound/play low_drone_02
/sound/stop low_drone_02
/sound/volume low_drone_02 0.6
```

#### Option B: MIDI

Gut, wenn Hardware, Ableton oder ein Mischpult MIDI versteht.

#### Option C: internes Audio-Modul

Für einen ersten Prototypen kann Python selbst Audiodateien triggern. Für eine professionelle Aufführung ist das aber weniger robust als QLab/Ableton.

---

### Modul 7: `light_bridge`

Für Licht gibt es mehrere Stufen.

#### MVP

Lichtbefehle werden nur geloggt oder als OSC an TouchDesigner gesendet.

#### Testversion

TouchDesigner oder Python sendet Art-Net/DMX an ein Test-Interface.

#### Aufführungsversion

Das System sendet entweder:

* Art-Net an ein Lichtpult
* sACN an ein Lichtnetzwerk
* OSC an ein Lichtpult oder eine Lichtsoftware
* MIDI/MSC an eine bestehende Show-Control-Struktur

Wichtig: Licht sollte immer einen manuellen Override haben.

---

### Modul 8: `operator_ui`

Eine einfache Bedienoberfläche ist wichtig.

Funktionen:

* aktueller KI-Text
* erkannte Stimmung
* vorgeschlagene Regieentscheidung
* aktuell laufende Cues
* Button: Entscheidung ausführen
* Button: Autopilot an/aus
* Button: Blackout sperren
* Button: Sound sperren
* Button: Licht sperren
* Button: alles stoppen
* Button: Aufnahme starten/stoppen
* Button: Livebild wiedergeben

Für den Anfang reicht eine lokale Weboberfläche mit FastAPI.

---

## 5. MVP: Erste umsetzbare Version

Der erste Prototyp sollte bewusst klein sein.

### MVP-Ziel

Wenn ein Text-Event reinkommt, entscheidet das Programm anhand von Tags und Stimmung:

1. Welcher Videoclip in TouchDesigner abgespielt wird
2. Welcher Sound-Cue ausgelöst wird
3. Welche Lichtstimmung als abstrakter Cue ausgegeben wird

Noch nicht nötig:

* perfekte KI-Regie
* vollständige Lichtsteuerung
* komplexe Datenbank
* perfekte UI
* Live-Aufnahme und Wiederverwendung

### MVP-Ablauf

```text
KI spricht Text
↓
Text wird an Orchestrator geschickt
↓
Text wird analysiert
↓
passende Tags werden erkannt
↓
Dramaturgie-Engine wählt Cue
↓
OSC-Befehl geht an TouchDesigner
↓
Video wird abgespielt
↓
Sound-Cue wird ausgelöst oder geloggt
↓
Licht-Cue wird ausgelöst oder geloggt
```

---

## 6. Empfohlene Ordnerstruktur für Cursor

```text
theater_ai_director/
│
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── dialogue/
│   │   ├── input_api.py
│   │   └── models.py
│   │
│   ├── dramaturgy/
│   │   ├── engine.py
│   │   ├── rules.py
│   │   ├── llm_director.py
│   │   └── prompts.py
│   │
│   ├── media/
│   │   ├── database.py
│   │   ├── selector.py
│   │   └── media_schema.py
│   │
│   ├── cues/
│   │   ├── cue_models.py
│   │   ├── scheduler.py
│   │   └── safety.py
│   │
│   ├── outputs/
│   │   ├── touchdesigner.py
│   │   ├── sound.py
│   │   ├── lighting.py
│   │   └── logger.py
│   │
│   └── ui/
│       ├── server.py
│       └── templates/
│
├── data/
│   ├── media.json
│   ├── light_scenes.json
│   └── dramaturgy_rules.json
│
├── media/
│   ├── video/
│   ├── audio/
│   └── recordings/
│
├── touchdesigner/
│   └── README_touchdesigner_setup.md
│
├── tests/
│   ├── test_dramaturgy.py
│   ├── test_media_selector.py
│   └── test_cue_scheduler.py
│
├── requirements.txt
└── README.md
```

---

## 7. Konkrete Cursor-Aufgaben

### Aufgabe 1: Projektgrundgerüst erstellen

Prompt für Cursor:

```text
Erstelle ein Python-Projekt namens theater_ai_director mit FastAPI, Pydantic und python-osc. Lege die Ordnerstruktur aus dem Entwicklungsplan an. Erstelle lauffähige Platzhalterdateien für dialogue input, dramaturgy engine, media database, cue scheduler und output bridges. Das Projekt soll mit uvicorn gestartet werden können.
```

---

### Aufgabe 2: Datenmodelle erstellen

Prompt für Cursor:

```text
Erstelle Pydantic-Modelle für DialogueEvent, DramaturgyDecision, VisualCue, SoundCue, LightCue und ScheduledCue. Die Modelle sollen JSON-serialisierbar sein und Felder für speaker, text, mood, intensity, tags, cue ids, fade times und timestamps enthalten.
```

---

### Aufgabe 3: Media-Datenbank als JSON laden

Prompt für Cursor:

```text
Implementiere eine MediaDatabase-Klasse, die media.json, light_scenes.json und dramaturgy_rules.json lädt. Sie soll Methoden anbieten wie get_video_by_tags(tags, mood, intensity), get_sound_by_tags(tags) und get_light_scene(mood, intensity).
```

---

### Aufgabe 4: Regelbasierte Dramaturgie-Engine bauen

Prompt für Cursor:

```text
Implementiere eine regelbasierte DramaturgyEngine. Sie bekommt ein DialogueEvent und erzeugt eine DramaturgyDecision. Nutze einfache Keyword- und Mood-Regeln: memory/erinnerung, body/körper, machine/maschine, fear/angst, silence/stille. Die Engine soll passende Visual-, Sound- und Light-Cues aus der MediaDatabase auswählen.
```

---

### Aufgabe 5: OSC-Ausgabe zu TouchDesigner

Prompt für Cursor:

```text
Implementiere eine TouchDesignerBridge mit python-osc. Sie soll Methoden haben: play_clip(clip_id, opacity, fade_time), stop_clip(), start_recording(recording_id), stop_recording(), play_recording(recording_id), blackout(). Die OSC-Zieladresse und der Port sollen über config.py konfigurierbar sein.
```

---

### Aufgabe 6: Test-Endpunkt für Text-Events

Prompt für Cursor:

```text
Erstelle einen FastAPI-Endpunkt POST /dialogue-event. Der Endpunkt nimmt ein DialogueEvent entgegen, gibt es an die DramaturgyEngine, erzeugt eine DramaturgyDecision, sendet die VisualCue an TouchDesignerBridge und gibt die gesamte Entscheidung als JSON zurück.
```

---

### Aufgabe 7: Safety- und Override-System

Prompt für Cursor:

```text
Implementiere ein SafetyState-Modul mit Flags: autopilot_enabled, visuals_enabled, sound_enabled, lights_enabled, blackout_locked. Der CueScheduler darf Cues nur ausführen, wenn sie durch den SafetyState erlaubt sind. Erstelle außerdem API-Endpunkte, um diese Flags umzuschalten.
```

---

### Aufgabe 8: einfache Operator-Weboberfläche

Prompt für Cursor:

```text
Erstelle eine einfache Weboberfläche für den Operator. Sie soll den letzten DialogueEvent, die letzte DramaturgyDecision, aktive Safety-Flags und Buttons für Autopilot, Visuals an/aus, Sound an/aus, Licht an/aus, Record Start, Record Stop und Emergency Stop anzeigen.
```

---

## 8. TouchDesigner-Seite

In TouchDesigner sollte ein klarer OSC-Empfänger gebaut werden.

Empfohlene OSC-Adressen:

```text
/visual/play_clip
/visual/stop_clip
/visual/set_opacity
/visual/fade
/visual/record_start
/visual/record_stop
/visual/play_recording
/visual/blackout
/light/set_scene
/sound/trigger
```

TouchDesigner-Netzwerk grob:

```text
OSC In DAT / OSC In CHOP
↓
Python Callback
↓
Media Router
↓
Movie File In TOPs
↓
Switch TOP / Cross TOP / Composite TOP
↓
Effects
↓
Out TOP für Beamer
↓
Movie File Out TOP für Recording
```

---

## 9. Datenbank-Logik für dramaturgische Auswahl

Jedes Medium sollte dramaturgisch beschrieben werden:

```json
{
  "id": "clip_001",
  "type": "video",
  "path": "media/video/clip_001.mp4",
  "tags": ["memory", "archive", "glitch"],
  "moods": ["melancholisch", "unheimlich"],
  "intensity_min": 0.3,
  "intensity_max": 0.8,
  "duration": 32,
  "loopable": true,
  "preferred_blend": "slow_fade"
}
```

Die Engine kann dann so auswählen:

```text
1. Welche Tags passen zum Text?
2. Welche Stimmung wurde erkannt?
3. Welche Intensität hat der Moment?
4. Welche Medien wurden kürzlich schon benutzt?
5. Welche Medien sind dramaturgisch noch nicht ausgeschöpft?
6. Gibt es ein Live-Recording, das besser passt?
```

---

## 10. Live-Aufnahme und Wiederverwendung

Spätere Erweiterung:

```text
/visual/record_start live_memory_001
/visual/record_stop
```

TouchDesigner speichert die Aufnahme.

Danach meldet TouchDesigner oder der Orchestrator:

```json
{
  "id": "live_memory_001",
  "type": "recording",
  "path": "media/recordings/live_memory_001.mp4",
  "tags": ["live", "recent", "body", "fragment"],
  "created_at": "2026-06-08T21:14:00"
}
```

Dann kann die Dramaturgie-Engine dieses Material später wie normales Datenbankmaterial auswählen.

---

## 11. LLM-Regie erst in Phase 2

Die erste Version sollte regelbasiert sein. Danach kann ein LLM eingebaut werden.

Das LLM bekommt:

* aktuellen Text
* letzte 5 Text-Events
* verfügbare Medien-Tags
* erlaubte Aktionen
* aktuelle Safety-Regeln
* laufende Cues

Das LLM darf nur JSON ausgeben.

Beispiel-Systemprompt:

```text
Du bist eine dramaturgische Live-Regie-Engine für eine Theateraufführung.
Du darfst nur Aktionen aus der erlaubten Aktionsliste wählen.
Erzeuge keine freien technischen Befehle.
Deine Ausgabe muss valides JSON sein.
Berücksichtige Rhythmus, Wiederholung, Kontrast, Eskalation und Pausen.
Vermeide zu häufige Cue-Wechsel.
```

---

## 12. Entwicklungsphasen

### Phase 1: Technischer MVP

Ziel:

* Text rein
* Entscheidung raus
* OSC an TouchDesigner
* Video wird abgespielt

Dauer im Projekt:

* erste funktionierende Grundlage

Features:

* FastAPI
* JSON-Mediendatenbank
* regelbasierte Dramaturgie
* TouchDesigner OSC Bridge
* Logging

---

### Phase 2: Sound und Licht simulieren

Ziel:

* Sound- und Lichtentscheidungen werden erzeugt
* noch nicht zwingend echte Geräte

Features:

* SoundCue-Logging
* LightCue-Logging
* Testausgabe per OSC
* Operator UI

---

### Phase 3: echte Ton- und Lichtausgabe

Ziel:

* Sound und Licht real steuern

Features:

* OSC/MIDI zu Soundsoftware
* Art-Net/sACN/DMX für Licht
* Fade-Zeiten
* Safety-Override
* Emergency Stop

---

### Phase 4: Live-Recording

Ziel:

* TouchDesigner nimmt Bildmaterial auf
* Orchestrator registriert neue Aufnahmen
* Aufnahmen können später wieder dramaturgisch verwendet werden

Features:

* Recording Start/Stop
* Recording-Metadaten
* automatische Datenbankeinträge
* Playback von Live-Aufnahmen

---

### Phase 5: KI-Dramaturgie

Ziel:

* LLM trifft komplexere dramaturgische Entscheidungen

Features:

* strukturierte JSON-Ausgabe
* begrenzte Aktionsliste
* dramaturgisches Gedächtnis
* Wiederholungsvermeidung
* Eskalationskurven
* manuelle Freigabe oder Autopilot

---

## 13. Teil 2 — Anarchische Inszenierung (implementiert)

Neben dem **Teil-1-Stücktext-Workflow** (`/dramaturgie` → `/stueck` → `/auffuehrung`) gibt es einen separaten Modus für **mehrere Tier-Szenen** mit eskalierender, überlagernder Aufführung — gedacht für Jelinek *Unter Tieren* / Thema **Geld**.

### Ablauf

```text
/inszenierung              Korpus + Szenen-Import (TXT/JSON)
        ↓
/inszenierung/analyse      Gesamtkonzept, Geld-Achsen, Anarchie-Kurve (SSE)
        ↓
/inszenierung/komposition  Textausschnitte + Regie pro Moment (SSE)
        ↓
/inszenierung/auffuehrung  Anarchie-Player (parallele Stimmen, Layer-Cues)
```

Persistenz: `data/inszenierungen/{id}.json` (parallel zu Teil-1-Produktionen unter `data/productions/`).

### Sprache & Medien

| `speech_mode` | Quelle |
|---------------|--------|
| `avatar_video` | Pixera-Avatar-Clip (Text im Video, kein TTS) |
| `tts` | KI-Stimmen Teil 2 (eigene Voice-Profile, getrennt von Teil 1) |
| `silent` | Nur Cues |

Avatar-Texte: [`media/video/Avatar Textzuordnung.csv`](media/video/Avatar%20Textzuordnung.csv) → `data/avatar_speech.json`. Die Komposition matcht Jelinek-Ausschnitte an Snippets (DEL/BK/LG/PET/WO) und steigert `anarchy_level` / `overlap_with_previous`.

Technik: `POST /api/v1/director/execute-layered`, `VisualCue.blend_mode: "layer"`, Frontend `anarchyPlayback.ts` + `inszenierungBuffer.ts`.

**Doku:** [`docs/teil2_inszenierung.md`](docs/teil2_inszenierung.md) · **Übersicht:** [`README.md`](README.md#teil-2--anarchische-inszenierung)

---

## 14. Wichtigste Designentscheidung

Das System sollte drei Ebenen strikt trennen:

```text
Dramaturgie ≠ Technik ≠ Ausgabe
```

Also:

```text
„Der Moment soll kalt, fragmentiert und erinnerungshaft werden.“
```

wird zuerst zu:

```text
Visual: glitch archive clip
Sound: low drone
Light: cold blue low
```

und erst danach zu:

```text
OSC / DMX / MIDI / Art-Net
```

Diese Trennung macht das System stabiler, künstlerisch flexibler und leichter in Cursor umzusetzen.

---

## 15. Erste konkrete Version

Die allererste Version sollte nur Folgendes können:

1. Lokaler Server läuft
2. Text-Event wird per API empfangen
3. Stimmung und Tags werden erkannt
4. Passender Videoclip wird aus `media.json` gewählt
5. OSC-Befehl wird an TouchDesigner gesendet
6. TouchDesigner spielt Clip ab
7. Entscheidung wird in einer Logdatei gespeichert

Erst wenn das zuverlässig funktioniert, sollten Sound, Licht, Recording und LLM-Regie ergänzt werden.
