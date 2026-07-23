"""Import report models for Burgtheater import dry-run / apply."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EntityKind = Literal[
    "production",
    "asset",
    "tag",
    "cue",
    "device",
    "rule",
]
ChangeKind = Literal["created", "updated", "skipped", "planned"]
WarningSeverity = Literal["warning", "error", "info"]


@dataclass
class ImportWarning:
    code: str
    message: str
    severity: WarningSeverity = "warning"
    path: str | None = None
    legacy_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity,
            "path": self.path,
            "legacy_id": self.legacy_id,
            "details": dict(self.details),
        }


@dataclass
class ImportCounts:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    planned: int = 0

    def bump(self, change: ChangeKind) -> None:
        setattr(self, change, getattr(self, change) + 1)

    def to_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "skipped": self.skipped,
            "planned": self.planned,
        }


@dataclass
class ImportReport:
    dry_run: bool
    production_id: str | None
    production_slug: str
    production_name: str
    source_root: str
    warnings: list[ImportWarning] = field(default_factory=list)
    counts_by_kind: dict[str, ImportCounts] = field(default_factory=dict)
    changes: list[dict[str, Any]] = field(default_factory=list)
    sources_seen: list[str] = field(default_factory=list)
    missing_media: list[str] = field(default_factory=list)

    def ensure_counts(self, kind: EntityKind) -> ImportCounts:
        if kind not in self.counts_by_kind:
            self.counts_by_kind[kind] = ImportCounts()
        return self.counts_by_kind[kind]

    def record(
        self,
        *,
        kind: EntityKind,
        change: ChangeKind,
        legacy_id: str,
        entity_id: str,
        name: str,
        detail: str | None = None,
    ) -> None:
        self.ensure_counts(kind).bump(change)
        self.changes.append(
            {
                "kind": kind,
                "change": change,
                "legacy_id": legacy_id,
                "entity_id": entity_id,
                "name": name,
                "detail": detail,
            }
        )

    def warn(
        self,
        code: str,
        message: str,
        *,
        severity: WarningSeverity = "warning",
        path: str | None = None,
        legacy_id: str | None = None,
        **details: Any,
    ) -> None:
        self.warnings.append(
            ImportWarning(
                code=code,
                message=message,
                severity=severity,
                path=path,
                legacy_id=legacy_id,
                details=details,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dry_run": self.dry_run,
            "production_id": self.production_id,
            "production_slug": self.production_slug,
            "production_name": self.production_name,
            "source_root": self.source_root,
            "warnings": [w.to_dict() for w in self.warnings],
            "counts_by_kind": {k: v.to_dict() for k, v in self.counts_by_kind.items()},
            "changes": list(self.changes),
            "sources_seen": list(self.sources_seen),
            "missing_media": list(self.missing_media),
            "summary": {
                "warning_count": len(self.warnings),
                "missing_media_count": len(self.missing_media),
                "totals": {
                    change: sum(getattr(c, change) for c in self.counts_by_kind.values())
                    for change in ("created", "updated", "skipped", "planned")
                },
            },
        }
