# Theatermaschine Debug MCP

Read-only MCP tools for signal trace analysis, inszenierung summaries, and cue catalog lookup.

## Setup

1. Backend venv should exist: `cd backend && python3.11 -m venv .venv && pip install -e ".[dev]"`
2. Enable in Cursor: project `.cursor/mcp.json` registers `theatermaschine-debug`
3. First start installs `mcp` from `requirements.txt` into the backend venv

## Tools

| Tool | Description |
|------|-------------|
| `analyze_signal_trace` | Drop report from `logs/signal_trace.jsonl` |
| `analyze_show_run` | Post-run: pauses, drops, avatar cascades, companion storms |
| `read_inszenierung` | Summary of `data/inszenierungen/{id}.json` |
| `list_recent_traces` | Recent trace events, filter by bridge/cue_id |
| `cue_catalog_lookup` | Search `video_cues.json` or `sound_cues.json` |

## Manual test

```bash
bash tools/mcp-theatermaschine/run.sh
```

Server speaks MCP over stdio — normally started by Cursor, not manually.

## Safety

This server is **read-only**. It does not send OSC, MIDI, or TCP.
