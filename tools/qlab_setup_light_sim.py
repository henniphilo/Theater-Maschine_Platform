#!/usr/bin/env python3
"""Print one-time QLab light simulation patch setup (instrument TMPREVIEW)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from qlab_light_sim import SIM_INSTRUMENT


def main() -> int:
    print(
        f"""QLab Licht-Simulation — Patch-Setup

Theatermaschine startet Light-Cues per OSC (/cue/{{scene_id}}/start).
Jeder Cue setzt RGB-Werte auf ein simuliertes Vorschau-Instrument.

1. QLab-Workspace öffnen
2. Workspace Settings → Lighting → Patch
3. Neues Instrument anlegen:
   · Name: {SIM_INSTRUMENT}
   · Definition: Color (RGB + Intensity) — QLab-Vorlage „Color“
   · DMX-Adresse beliebig (nur Simulation, kein Art-Net nötig)
4. Cues importieren:
   make qlab-light-cue-list
   make qlab-light-import

Test (Relay + Backend laufen):
   echo '/light/set_scene saallicht 4' | nc -u -w1 127.0.0.1 7000

Light Dashboard in QLab zeigt die Vorschau-Farben; auf der Bühne bleibt EOS maßgeblich.
"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
