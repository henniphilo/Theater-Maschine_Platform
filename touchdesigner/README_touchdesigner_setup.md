# TouchDesigner setup for Theatermaschine Live-Regie

## Overview

The Python orchestrator sends **OSC** messages to TouchDesigner on port **7000** (default). TouchDesigner maps these to video playback, recording, and compositing.

Configure in `backend/.env`:

```env
OSC_HOST=127.0.0.1
OSC_PORT=7000
OSC_DRY_RUN=false
```

When running the backend in Docker on Mac, use `OSC_HOST=host.docker.internal` so UDP reaches TouchDesigner on the host.

## Network setup

1. Add an **OSC In DAT** (or OSC In CHOP) to your TouchDesigner project.
2. Set **Network Port** to `7000` (match `OSC_PORT`).
3. Add a **Python DAT** or **Callbacks DAT** wired to the OSC In DAT.
4. Route commands to Movie File In TOPs, Switch TOP, Composite TOP, Level TOP, and Out TOP.

## OSC address mapping

| OSC Address | Arguments | Action |
|-------------|-----------|--------|
| `/visual/play_clip` | `clip_id`, `opacity`, `fade_time` | Load and play clip from media library |
| `/visual/stop_clip` | — | Stop current clip |
| `/visual/set_opacity` | `opacity` | Set composite opacity (0.0–1.0) |
| `/visual/fade` | `fade_time` | Crossfade over N seconds |
| `/visual/record_start` | `recording_id` | Start Movie File Out TOP recording |
| `/visual/record_stop` | — | Stop recording |
| `/visual/play_recording` | `recording_id` | Play back a previous recording |
| `/visual/blackout` | — | Fade to black / hide output |
| `/light/set_scene` | `scene_id`, `fade_time` | Optional: route to DMX if TD controls light |

**Licht am Pult (Unter Tieren / ETC EOS):** TCP-Port **3032** ist laut [ETC EOS OSC Setup](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/23_Show_Control/08_OSC/Using_OSC_with_Eos/Eos_OSC_Setup.htm) der native **OSC-over-TCP**-Port. Kein UDP, kein JSON-Handshake nötig.

| Schritt | Ziel | Aktion |
|---------|------|--------|
| 1 | `10.101.90.112:3032` (TCP) | Socket verbinden (EOS lauscht als Server) |
| 2 | dieselbe TCP-Verbindung | Binäres OSC mit **4-Byte-Längenpräfix** (EOS „OSC 1.0 TCP“) |
| Stopp | TCP | `/eos/key/out` als OSC-Paket, dann Socket schließen |

EOS Setup am Pult: **OSC RX** und **OSC TX** aktivieren, TCP-Modus **OSC 1.0** (Packet Length Headers).

Beispiel-Adressen:

```text
/eos/chan/6/full
/eos/chan/92/full
/eos/key/out
```

Backend-Defaults: `LIGHT_TCP_HANDSHAKE=none`, `LIGHT_OSC_TCP_FORMAT=binary`, `LIGHT_OSC_TCP_FRAMING=length_prefix`.

Falls das Pult **OSC 1.1 (SLIP)** erwartet: `LIGHT_OSC_TCP_FRAMING=slip`.

Legacy JSON-Handshake (nur falls vom Venue verlangt): `LIGHT_TCP_HANDSHAKE=json`.

Optional: `LIGHT_OSC_MIRROR=true` spiegelt dieselben OSC-Befehle zusätzlich an TouchDesigner (`OSC_HOST:OSC_PORT`).

| Einstellung | Wert |
|-------------|------|
| TCP IP / Port | `10.101.90.112` / `3032` (EOS OSC-over-TCP) |
| OSC-Format | `binary` + `length_prefix` (EOS OSC 1.0 TCP) |
| Handshake | `none` (kein JSON — nur Socket + OSC-Pakete) |

Beispiel TCP-Handshake:

```json
{"protocol":"1.0","command":"connect"}
```

Danach binäres OSC über dieselbe TCP-Verbindung `:3032` (4-Byte-Längenpräfix, dann OSC-Body):

```text
/eos/chan/6/full
/eos/key/out
```

Im Log: `[OSC SEND] [light] → 10.101.90.112:3032 tcp/osc binary+length_prefix 28B /eos/chan/6/full`

Beispiel Szene `panolatte_rechts` → Kanäle 92, 94, 96, 98 je `/eos/chan/N/full`.  
Stopp/Blackout → `/eos/key/out`, dann TCP `disconnect`.

Konfiguration in `backend/.env`: `LIGHT_TCP_HOST`, `LIGHT_TCP_PORT`, `LIGHT_TCP_PROTOCOL`.
| `/sound/trigger` | `cue_id`, `volume` | Optional: forward to QLab/Ableton |
| `/sound/hold` | `cue_id`, `volume` | Technik-Test: Soundfläche halten (Keepalive) |
| `/sound/stop` | `cue_id` | Cue stoppen |
| `/light/hold` | `scene_id` | Technik-Test: Lichtszene halten (Keepalive, parallel TCP `hold`) |

## Suggested TD network

```text
OSC In DAT (port 7000)
    ↓
Python callback (parse address + args)
    ↓
Media Router (select TOP by clip_id)
    ↓
Movie File In TOPs  →  Switch TOP / Cross TOP  →  Level TOP
    ↓
Effects (optional)
    ↓
Out TOP (projector)
    ↓
Movie File Out TOP (recordings → media/recordings/)
```

## Example Python callback (OSC In DAT)

```python
def onReceiveOSC(dat, rowIndex, message, bytes, time, address, args, peer):
    if address == '/visual/play_clip':
        clip_id, opacity, fade = args[0], float(args[1]), float(args[2])
        op('media_router').par.Clipid = clip_id
        op('level_top').par.opacity = opacity
        op('cross_top').par.fade = fade
    elif address == '/visual/blackout':
        op('level_top').par.opacity = 0
    elif address == '/visual/record_start':
        rec_id = args[0]
        op('moviefileout1').par.file = f'recordings/{rec_id}.mp4'
        op('moviefileout1').par.record = True
    elif address == '/visual/record_stop':
        op('moviefileout1').par.record = False
    return
```

## Clip ID → file path

Clip IDs are **auto-scanned** from `media/video/` and `media/recordings/` (e.g. `kuh.mov` → `clip_id` `kuh`). Map each `id` to a `Movie File In TOP` or a folder lookup, e.g.:

Alle Dateien in `media/video/` werden automatisch erkannt (`clip_id` = Dateiname ohne Endung, Leerzeichen → `_`, Umlaute → ae/oe/ue). Aktuell z. B.:

| clip_id | Datei |
|---------|-------|
| `kuh` | `kuh.mov` |
| `fuchs` | `fuchs.mov` |
| `ente` | `Ente.mov` |
| `bar_avatar` | `Bär Avatar.mp4` |
| `fuchs_avatar` | `Fuchs Avatar.mp4` |
| `hund_avatar` | `Hund Avatar.mp4` |
| `esel_lauft_27-05` | `Esel läuft 27-05.mp4` |
| `lowe_test` | `Löwe Test.mp4` |
| `gehirn_test` | `Gehirn Test.mp4` |
| `schmetterlinge` | `Schmetterlinge.mp4` |
| `insekten` | `Insekten.mp4` |
| `mehlwurmer` | `Mehlwürmer.mp4` |

Licht-Szenen kommen aus `data/light_scenes.json` (abgeleitet aus `media/light/Kanal Übersicht.xlsx`). OSC: `/light/set_scene <scene_id> <fade_time>` — z. B. `vorbuehnenzug` → Kanäle 11–19.

Sounds sind aktuell **Dummy-WAVs** in `media/audio/dummy_*.wav` bis echte Cues eingepflegt sind.

Legacy example:

```text
memory_noise_03  →  ../media/video/memory_noise_03.mp4
```

## TouchDesigner Checkliste (wenn „nichts ankommt“)

Das Backend **sendet** OSC (Log: `[OSC SEND] → host.docker.internal:7000`). TouchDesigner lauscht typischerweise auf Port **7000**. Wenn trotzdem nichts passiert:

1. **OSC In DAT** → Parameter **Network Port** = `7000`, **Active** = an
2. **Callbacks DAT** verknüpfen: OSC In DAT → Parameter **Callbacks DAT** → dein Callbacks-DAT
3. **Textport** öffnen (Alt+T) — bei ankommendem OSC muss etwas erscheinen (siehe `theatermaschine_callbacks.py`)
4. Im OSC In DAT die **Tabelle** prüfen — neue Zeilen mit `/visual/play_clip`?
5. **Adresse exakt**: `/visual/play_clip` (nicht `/play_clip`)
6. **Argumente**: `clip_id` (string), `opacity` (float), `fade_time` (float) — z. B. `kuh`, `0.8`, `4.0`

Schnelltest vom Mac (Backend muss laufen):

```bash
curl -X POST http://localhost:8000/api/v1/director/osc-test \
  -H 'Content-Type: application/json' \
  -d '{"clip_id":"kuh"}'
```

Wenn im Textport `[TM] OSC /visual/play_clip ...` erscheint, ist die Verbindung OK — dann Clip-Mapping / Movie File In TOP prüfen.

Referenz-Callback: [`theatermaschine_callbacks.py`](theatermaschine_callbacks.py)

## Testing without full TD network

1. Set `OSC_DRY_RUN=true` in `.env` — commands are logged, not sent.
2. Or use a tool like **OSCulator** / **Protokol** to monitor incoming OSC on port 7000.
3. Send a test event:

```bash
curl -X POST http://localhost:8000/api/v1/director/dialogue-event \
  -H 'Content-Type: application/json' \
  -d '{"speaker":"AI_A","text":"Erinnerung ist vielleicht nur eine technische Störung.","topic":"Erinnerung","mood":"melancholisch","intensity":0.72,"tags":["memory","erinnerung"]}'
```

## Phase 4: recordings

When `/visual/record_stop` completes, TouchDesigner should save to `media/recordings/{recording_id}.mp4`. The orchestrator registers new recordings via `RecordingManager` when you call `POST /api/v1/director/record/stop`.
