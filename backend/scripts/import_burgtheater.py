#!/usr/bin/env python3
"""CLI: Burgtheater → Production import (dry-run by default).

Examples:
  python scripts/import_burgtheater.py
  python scripts/import_burgtheater.py --apply
  python scripts/import_burgtheater.py --data-dir /path/to/data --media-dir /path/to/media
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow `python scripts/import_burgtheater.py` from backend/ with app on path.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Import Burgtheater legacy data into a Production (idempotent)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes (default is dry-run analysis only).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Force dry-run (default).")
    parser.add_argument("--repo-root", type=Path, default=None)
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--media-dir", type=Path, default=None)
    parser.add_argument(
        "--include-hardware-addresses",
        action="store_true",
        help="Allow non-secret overlay keys (host/port still refused).",
    )
    parser.add_argument(
        "--no-copy-media",
        action="store_true",
        help="Do not copy media bytes into storage on apply.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write JSON import report to this path.",
    )
    parser.add_argument("-q", "--quiet", action="store_true")
    args = parser.parse_args(argv)

    dry_run = not args.apply or args.dry_run
    if args.apply and args.dry_run:
        print("Both --apply and --dry-run set; staying in dry-run.", file=sys.stderr)
        dry_run = True

    from app.db.session import SessionLocal
    from app.services.burgtheater_import import BurgtheaterImportOptions, run_burgtheater_import
    from app.storage import get_storage_backend

    options = BurgtheaterImportOptions(
        dry_run=dry_run,
        repo_root=args.repo_root,
        data_dir=args.data_dir,
        media_dir=args.media_dir,
        include_hardware_addresses=args.include_hardware_addresses,
        copy_media_into_storage=not args.no_copy_media,
    )

    db = SessionLocal()
    try:
        storage = get_storage_backend()
        report = run_burgtheater_import(db, storage=storage, options=options)
    finally:
        db.close()

    payload = report.to_dict()
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.quiet:
        mode = "DRY-RUN" if report.dry_run else "APPLY"
        print(f"[{mode}] Burgtheater import — production={report.production_slug}")
        print(f"  production_id: {report.production_id}")
        print(f"  source_root:   {report.source_root}")
        print(f"  warnings:      {len(report.warnings)}")
        print(f"  missing_media: {len(report.missing_media)}")
        for kind, counts in sorted(report.counts_by_kind.items()):
            print(
                f"  {kind}: created={counts.created} updated={counts.updated} "
                f"skipped={counts.skipped} planned={counts.planned}"
            )
        for warning in report.warnings[:20]:
            print(f"  ! {warning.severity}: {warning.code}: {warning.message}")
        if len(report.warnings) > 20:
            print(f"  … {len(report.warnings) - 20} more warnings")
        if args.report is not None:
            print(f"  report written: {args.report}")

    # Non-zero only on hard errors; warnings are expected (e.g. missing media).
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
