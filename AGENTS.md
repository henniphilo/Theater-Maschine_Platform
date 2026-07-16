# Theatermaschine — Agent Guide

Live-theater control system: FastAPI backend + Next.js frontend → OSC / MIDI / TCP to stage hardware.

## Modes

| Mode | Routes | Description |
|------|--------|-------------|
| Teil 1 | `/dramaturgie` → `/stueck` → `/auffuehrung` | Script dramaturgy workshop, sequential playback |
| Teil 2 | `/inszenierung` → prepare → `/inszenierung/auffuehrung` | Text-sync avatars, TTS as master clock |
| Operator | `/director` | Manual director panel, safety toggles |
| Remote | `/remote` | Phone Play/Pause/Stop; Mac Aufführung tab executes (TTS stays on Mac) — [docs/remote_transport.md](docs/remote_transport.md) |

## Key paths

| Area | Path |
|------|------|
| Director pipeline | `backend/app/director/pipeline.py` |
| OSC queue + trace | `backend/app/director/outputs/osc_queue.py`, `signal_trace.py` |
| Teil 2 prepare | `backend/app/services/teil2_prepare_service.py` |
| Teil 2 playback | `frontend/features/inszenierung/teil2TextSyncPlayback.ts` |
| Sentence split (Teil 2) | `backend/app/services/text_split.py` ↔ `frontend/lib/text/splitSentences.ts` |
| Fake OSC receiver (tests) | `backend/app/director/testing/fake_osc_receiver.py` |
| Runtime logs | `logs/signal_trace.jsonl`, `logs/osc.log`, `logs/director.log` |
| Inszenierung data | `data/inszenierungen/{uuid}.json` |
| Media catalogs | `data/video_cues.json`, `data/sound_cues.json`, `media/video/` |

## Dev commands

Prefer Makefile targets over ad-hoc commands:

```bash
make run              # Docker infra + native backend (MIDI, macOS say)
make up               # Full Docker stack
make stop             # Stop everything
make test             # Backend + frontend tests
make test-backend     # pytest via backend/run-tests.sh
make test-frontend    # vitest
make analyze-signal-trace
make visualize-logs
make run-tryout       # Probe run + analysis
make avatar-import    # Regenerate avatar catalogs
make video-import     # Regenerate video/atmosphere catalogs
```

Secrets live in `backend/.env` only — never commit.

## Architecture (short)

```
DialogueEvent → DramaturgyDecision → ScheduledCue → OSC / MIDI / TCP
```

Details: [docs/architektur.md](docs/architectur.md) · Teil 2: [docs/teil2_inszenierung.md](docs/teil2_inszenierung.md)

## Before committing

```bash
make test-backend && make test-frontend
```

Backend CI runs ruff + pytest. Frontend CI runs lint + build + vitest.

## Dangerous actions

- Setting `OSC_DRY_RUN=false` in tests or shell without fake receivers
- Changing sentence split on only one side (`text_split.py` / `splitSentences.ts`)
- Committing `backend/.env` or any file with API keys
- Sending OSC/MIDI/TCP to production hosts during development
- Using `script_splitter.py` for Teil 2 avatar char-offset alignment (use `text_split.py`)

## Cursor project skills

Invoke explicitly when relevant:

- `debug-signal-drops` — analyze missing cues / signal trace
- `tryout-run` — automated probe run before a show
- `teil2-prepare-review` — review Prepare / alignment changes
- `media-import` — CSV/Numbers import workflows

## Cursor MCP (optional)

Project MCP server `theatermaschine-debug` in `.cursor/mcp.json` — read-only tools for trace analysis, inszenierung summaries, cue lookup. Setup: [tools/mcp-theatermaschine/README.md](tools/mcp-theatermaschine/README.md)

## Native vs Docker

| Feature | Native (`make run`) | Docker (`make up`) |
|---------|---------------------|-------------------|
| MIDI → Ableton | Yes | No |
| macOS `say` TTS | Yes | No (edge-tts) |
| OSC to TouchDesigner | `OSC_HOST=127.0.0.1` | `host.docker.internal` |

Signal-drop debugging: [docs/debug_signal_drop_plan.md](docs/debug_signal_drop_plan.md)
