from functools import lru_cache
from pathlib import Path

from app.core.config import settings


def _repo_roots() -> list[Path]:
    module_root = Path(__file__).resolve()
    data_dir = Path(settings.director_data_dir)
    if not data_dir.is_absolute():
        data_dir = module_root.parents[3] / data_dir
    return [
        data_dir.parent,
        module_root.parents[3],
        module_root.parents[4],
        Path.cwd(),
        Path("/app"),
    ]


def _rules_path() -> Path | None:
    for root in _repo_roots():
        candidate = root / "docs" / "dramaturgy_rules.md"
        if candidate.is_file():
            return candidate
    return None


@lru_cache(maxsize=1)
def load_dramaturgy_rules() -> str:
    path = _rules_path()
    if path is None:
        return (
            "Dramaturgie-Regeln: Nur Video, Sound, Licht per OSC. "
            "Keine Illustration. Jelinek-nahe Gegenstimme. Nur verfügbare Medien-IDs."
        )
    return path.read_text(encoding="utf-8")


def dramaturgy_rules_excerpt(max_chars: int = 8000) -> str:
    text = load_dramaturgy_rules().strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n[… Regelwerk gekürzt — vollständige Regeln gelten.]"
