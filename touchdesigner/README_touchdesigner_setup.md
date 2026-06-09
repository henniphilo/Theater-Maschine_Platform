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
| `/sound/trigger` | `cue_id`, `volume` | Optional: forward to QLab/Ableton |

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

Clip IDs come from `data/media.json`. Map each `id` to a `Movie File In TOP` or a folder lookup, e.g.:

```text
memory_noise_03  →  ../media/video/memory_noise_03.mp4
```

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
