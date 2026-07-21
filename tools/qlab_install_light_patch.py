#!/usr/bin/env python3
"""Install TMPREVIEW light instrument in the open QLab workspace (UI automation)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from qlab_light_sim import SIM_INSTRUMENT

APPLESCRIPT_PATH = Path(__file__).with_suffix(".applescript")


def _instrument_exists() -> bool:
    script = f'''tell application id "com.figure53.QLab.5"
    if (count of workspaces) is 0 then return "no"
    activate
    tell application "System Events"
        tell process "QLab"
            try
                click menu item "Light Patch" of menu "Window" of menu bar 1
            end try
            delay 0.8
            repeat with w in windows
                set wName to name of w as text
                if wName contains "Settings" or wName contains "Einstellungen" then
                    repeat with o in outlines of w
                        try
                            repeat with r in rows of o
                                try
                                    if (value of r as text) contains "{SIM_INSTRUMENT}" then
                                        keystroke "w" using command down
                                        return "yes"
                                    end if
                                end try
                            end repeat
                        end try
                    end repeat
                    repeat with t in tables of w
                        try
                            repeat with r in rows of t
                                try
                                    if (value of r as text) contains "{SIM_INSTRUMENT}" then
                                        keystroke "w" using command down
                                        return "yes"
                                    end if
                                end try
                            end repeat
                        end try
                    end repeat
                    keystroke "w" using command down
                end if
            end repeat
        end tell
    end tell
    return "no"
end tell'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return False
    return result.stdout.strip() == "yes"


def install_patch(*, dry_run: bool = False) -> str:
    if _instrument_exists():
        return "exists"

    if dry_run:
        return "would-create"

    if not APPLESCRIPT_PATH.is_file():
        raise FileNotFoundError(f"AppleScript fehlt: {APPLESCRIPT_PATH}")

    try:
        result = subprocess.run(
            ["osascript", str(APPLESCRIPT_PATH), SIM_INSTRUMENT],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or exc.stdout or str(exc)).strip()
        if "1719" in err or "Assistive" in err or "Hilfszugriff" in err or "-1719" in err:
            raise RuntimeError(
                "Keine Bedienungshilfen-Berechtigung für osascript/System Events.\n"
                "Systemeinstellungen → Datenschutz & Sicherheit → Bedienungshilfen → "
                "Terminal oder Cursor aktivieren, dann erneut ausführen."
            ) from exc
        raise RuntimeError(err) from exc

    status = (result.stdout or "").strip() or "created"
    if _instrument_exists():
        return status
    return f"{status} (Hinweis: Instrument noch nicht verifizierbar — Patch in QLab prüfen)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="QLab Light-Patch TMPREVIEW anlegen (Workspace Settings, UI-Automation)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Nur prüfen, nichts anlegen")
    args = parser.parse_args(argv)

    try:
        status = install_patch(dry_run=args.dry_run)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if status == "exists":
        print(f"OK: Instrument '{SIM_INSTRUMENT}' ist bereits im Light Patch.")
    elif status == "would-create":
        print(f"Dry-run: würde Instrument '{SIM_INSTRUMENT}' anlegen.")
    elif status.startswith("created"):
        print(f"OK: Instrument '{SIM_INSTRUMENT}' angelegt.")
        print("Als Nächstes: make qlab-light-import")
    else:
        print(status)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
