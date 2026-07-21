#!/usr/bin/env python3
"""Import QLab Light cues for Theatermaschine light simulation (scene_id = cue number)."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from qlab_light_sim import SIM_INSTRUMENT


def _escape_applescript(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _load_csv_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"qlab_cue_number", "description", "fade_time", "command_text"}
        if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV braucht Spalten: {', '.join(sorted(required))}")
        return [dict(row) for row in reader]


def _command_text_from_row(row: dict[str, str]) -> str:
    raw = (row.get("command_text") or "").strip()
    return raw.replace("\\n", "\n")


def _build_applescript(cue_number: str, cue_name: str, command_text: str, fade_time: float) -> str:
    cue_number_esc = _escape_applescript(cue_number)
    cue_name_esc = _escape_applescript(cue_name)
    command_esc = _escape_applescript(command_text)
    return f'''tell application id "com.figure53.QLab.5"
    activate
    if (count of workspaces) is 0 then error "Kein QLab-Workspace geöffnet"
    tell front workspace
        make type "Light"
        set newCue to last item of (selected as list)
        set the q number of newCue to "{cue_number_esc}"
        set the q name of newCue to "{cue_name_esc}"
        set command text of newCue to "{command_esc}"
        set duration of newCue to {fade_time}
    end tell
end tell'''


def _build_update_applescript(cue_number: str, cue_name: str, command_text: str, fade_time: float) -> str:
    cue_number_esc = _escape_applescript(cue_number)
    cue_name_esc = _escape_applescript(cue_name)
    command_esc = _escape_applescript(command_text)
    return f'''tell application id "com.figure53.QLab.5"
    activate
    if (count of workspaces) is 0 then error "Kein QLab-Workspace geöffnet"
    tell front workspace
        set targetCue to missing value
        repeat with c in cues
            try
                if (q number of c as text) is "{cue_number_esc}" then
                    set targetCue to c
                    exit repeat
                end if
            end try
        end repeat
        if targetCue is missing value then error "Cue nicht gefunden: {cue_number_esc}"
        set the q name of targetCue to "{cue_name_esc}"
        set command text of targetCue to "{command_esc}"
        set duration of targetCue to {fade_time}
    end tell
end tell'''


def _update_qlab_light_cue(
    cue_number: str,
    cue_name: str,
    command_text: str,
    fade_time: float,
) -> None:
    script = _build_update_applescript(cue_number, cue_name, command_text, fade_time)
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)


def _create_qlab_light_cue(
    cue_number: str,
    cue_name: str,
    command_text: str,
    fade_time: float,
) -> None:
    script = _build_applescript(cue_number, cue_name, command_text, fade_time)
    subprocess.run(["osascript", "-e", script], check=True, capture_output=True, text=True)


def _existing_qlab_cue_numbers() -> set[str]:
    script = '''tell application id "com.figure53.QLab.5"
    if (count of workspaces) is 0 then return ""
    tell front workspace
        set out to ""
        repeat with c in cues
            try
                set n to q number of c
                if n is not missing value and n is not "" then
                    set out to out & n & linefeed
                end if
            end try
        end repeat
        return out
    end tell
end tell'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _instrument_exists() -> bool:
    """Best-effort check whether TMPREVIEW responds to setLight (requires QLab open)."""
    script = f'''tell application id "com.figure53.QLab.5"
    if (count of workspaces) is 0 then return "no-workspace"
    tell front workspace
        try
            set theDashboard to current light dashboard
            setLight theDashboard selector "{SIM_INSTRUMENT}.intensity" value "1"
            revert theDashboard
            return "yes"
        on error errMsg number errNum
            return "no:" & errNum
        end try
    end tell
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


def _warn_if_patch_missing(*, strict: bool) -> bool:
    """Return False when strict patch check should abort."""
    status = _instrument_exists()
    if status:
        return True
    message = (
        f"Hinweis: Instrument '{SIM_INSTRUMENT}' fehlt im QLab Light Patch.\n"
        "Cues werden trotzdem angelegt; Vorschau wirkt erst nach manuellem Patch-Setup:\n"
        "  Workspace Settings → Lighting → Patch → + Instrument\n"
        "  Name: TMPREVIEW · Typ: RGB Fixture with Intensity\n"
        "  Oder: make qlab-light-setup\n"
    )
    if strict:
        print(message, file=sys.stderr)
        return False
    print(message)
    return True


def import_cues(
    csv_path: Path,
    *,
    dry_run: bool = False,
    skip_existing: bool = True,
    replace_existing: bool = False,
) -> tuple[int, int, int, int]:
    rows = _load_csv_rows(csv_path)
    existing = _existing_qlab_cue_numbers() if (skip_existing or replace_existing) and not dry_run else set()
    created = 0
    updated = 0
    skipped = 0
    failed = 0

    for row in rows:
        cue_number = (row.get("qlab_cue_number") or "").strip()
        cue_name = (row.get("description") or cue_number).strip()
        if not cue_number:
            continue
        try:
            fade_time = float(row.get("fade_time") or 3.0)
        except ValueError:
            fade_time = 3.0
        command_text = _command_text_from_row(row)

        if cue_number in existing:
            if replace_existing:
                if dry_run:
                    print(f"  würde aktualisieren: {cue_number} ({cue_name}) fade={fade_time}s")
                    updated += 1
                    continue
                try:
                    _update_qlab_light_cue(cue_number, cue_name, command_text, fade_time)
                    updated += 1
                    print(f"  aktualisiert: {cue_number} — {cue_name}")
                except subprocess.CalledProcessError as exc:
                    failed += 1
                    err = (exc.stderr or exc.stdout or str(exc)).strip()
                    print(f"  fehler: {cue_number} — {err}")
                continue
            skipped += 1
            continue

        if dry_run:
            print(f"  würde anlegen: {cue_number} ({cue_name}) fade={fade_time}s")
            created += 1
            continue
        try:
            _create_qlab_light_cue(cue_number, cue_name, command_text, fade_time)
            existing.add(cue_number)
            created += 1
            print(f"  ok: {cue_number} — {cue_name}")
        except subprocess.CalledProcessError as exc:
            failed += 1
            err = (exc.stderr or exc.stdout or str(exc)).strip()
            print(f"  fehler: {cue_number} — {err}")

    return created, updated, skipped, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="QLab Light-Cues für Licht-Simulation importieren")
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=ROOT / "data" / "qlab_light_cue_list.csv",
        help="CSV aus make qlab-light-cue-list",
    )
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts in QLab anlegen")
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Bestehende Cues (gleiche Cue-Nummer) mit Command-Text aus CSV aktualisieren",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Auch Cues anlegen, deren Nummer schon in QLab existiert (Duplikate)",
    )
    parser.add_argument(
        "--strict-patch",
        action="store_true",
        help="Abbrechen wenn TMPREVIEW im Light Patch fehlt (Standard: nur Hinweis)",
    )
    parser.add_argument(
        "--skip-patch-check",
        action="store_true",
        help="Patch-Hinweis unterdrücken",
    )
    args = parser.parse_args(argv)

    csv_path = args.csv_path if args.csv_path.is_absolute() else Path.cwd() / args.csv_path
    if not csv_path.is_file():
        print(f"CSV nicht gefunden: {csv_path}", file=sys.stderr)
        print("Zuerst: make qlab-light-cue-list", file=sys.stderr)
        return 1

    if not args.dry_run and not args.skip_patch_check:
        if not _warn_if_patch_missing(strict=args.strict_patch):
            return 1

    print(f"CSV: {csv_path}")
    created, updated, skipped, failed = import_cues(
        csv_path,
        dry_run=args.dry_run,
        skip_existing=not args.no_skip_existing,
        replace_existing=args.replace_existing,
    )
    print(
        f"Fertig: {created} angelegt, {updated} aktualisiert, {skipped} übersprungen, {failed} Fehler."
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
