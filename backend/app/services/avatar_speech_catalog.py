import csv
import json
import re
import unicodedata
from pathlib import Path

from app.core.config import settings
from app.schemas.avatar_speech import AvatarRole, AvatarSpeechCatalog, AvatarSpeechCue

PREFIX_AVATAR: dict[str, tuple[AvatarRole, str]] = {
    "DEL": ("delphin", "avatar"),
    "BK": ("baerenklau", "avatar2"),
    "LG": ("lamm", "esel"),
    "PET": ("petya", "hundethiel"),
    "WO": ("wolf", "thiel"),
}

AVATAR_CSV_NAME = "Avatar Textzuordnung.csv"


def _repo_roots() -> list[Path]:
    module_root = Path(__file__).resolve()
    data_dir = Path(settings.director_data_dir)
    if not data_dir.is_absolute():
        data_dir = module_root.parents[1] / data_dir
    return [data_dir.parent, data_dir, module_root.parents[2], module_root.parents[3], Path.cwd()]


def _data_dir() -> Path:
    configured = Path(settings.director_data_dir)
    if configured.is_absolute():
        return configured
    for root in _repo_roots():
        candidate = root / configured
        if candidate.is_dir():
            return candidate
    return Path.cwd() / configured


def resolve_avatar_csv_path() -> Path | None:
    for root in _repo_roots():
        candidate = root / "media" / "video" / AVATAR_CSV_NAME
        if candidate.is_file():
            return candidate
    return None


def catalog_json_path() -> Path:
    return _data_dir() / "avatar_speech.json"


def normalize_avatar_text(text: str) -> str:
    cleaned = text.replace("_x000B_", " ").replace("\n", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _tokenize(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    return {t for t in re.findall(r"[a-zäöüß]{4,}", normalized) if len(t) >= 4}


def parse_avatar_csv(path: Path) -> AvatarSpeechCatalog:
    cues: list[AvatarSpeechCue] = []
    seen_ids: dict[str, int] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            raw_id = (row.get("id") or "").strip()
            if not raw_id:
                continue
            text = normalize_avatar_text(row.get("text") or "")
            if not text:
                continue
            cue_id = raw_id
            seen_ids[raw_id] = seen_ids.get(raw_id, 0) + 1
            if seen_ids[raw_id] > 1:
                suffix = chr(ord("a") + seen_ids[raw_id] - 2)
                cue_id = f"{raw_id}{suffix}"
            avatar_raw = (row.get("avatar") or "").strip().lower()
            clip_raw = (row.get("video_clip_id") or "").strip().lower()
            prefix_match = re.match(r"^([A-Z]+)", raw_id.upper())
            prefix = prefix_match.group(1) if prefix_match else "DEL"
            default_avatar, default_clip = PREFIX_AVATAR.get(prefix, ("delphin", "avatar"))
            valid_avatars = {"delphin", "baerenklau", "lamm", "petya", "wolf"}
            avatar: AvatarRole = avatar_raw if avatar_raw in valid_avatars else default_avatar  # type: ignore[assignment]
            video_clip_id = clip_raw or default_clip
            scene_ref = (row.get("scene_ref") or "").strip() or None
            cues.append(
                AvatarSpeechCue(
                    id=cue_id,
                    avatar=avatar,
                    text=text,
                    video_clip_id=video_clip_id,
                    scene_ref=scene_ref,
                )
            )
    return AvatarSpeechCatalog(cues=cues)


def match_avatar_cues(
    excerpt: str,
    *,
    limit: int = 5,
    exclude_baerenklau: bool = False,
) -> list[AvatarSpeechCue]:
    catalog = get_avatar_speech_catalog_service().load()
    excerpt_tokens = _tokenize(excerpt)
    if not excerpt_tokens:
        return []
    scored: list[tuple[float, AvatarSpeechCue]] = []
    for cue in catalog.cues:
        if exclude_baerenklau and cue.id.upper().startswith("BK"):
            continue
        cue_tokens = _tokenize(cue.text)
        if not cue_tokens:
            continue
        overlap = len(excerpt_tokens & cue_tokens)
        if overlap == 0:
            continue
        score = overlap / max(len(excerpt_tokens), 1)
        scored.append((score, cue))
    scored.sort(key=lambda item: (-item[0], item[1].id))
    return [cue for _, cue in scored[:limit]]


class AvatarSpeechCatalogService:
    def load(self) -> AvatarSpeechCatalog:
        csv_path = resolve_avatar_csv_path()
        if csv_path is not None:
            catalog = parse_avatar_csv(csv_path)
            self._write_json_cache(catalog, source=str(csv_path))
            return catalog
        json_path = catalog_json_path()
        if json_path.is_file():
            return AvatarSpeechCatalog.model_validate_json(json_path.read_text(encoding="utf-8"))
        return AvatarSpeechCatalog()

    @staticmethod
    def _write_json_cache(catalog: AvatarSpeechCatalog, *, source: str) -> None:
        path = catalog_json_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": catalog.version,
            "_source": source,
            "cues": [c.model_dump() for c in catalog.cues],
        }
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def cue_by_id(self, cue_id: str, catalog: AvatarSpeechCatalog | None = None) -> AvatarSpeechCue | None:
        catalog = catalog or self.load()
        normalized = cue_id.strip()
        return next((c for c in catalog.cues if c.id == normalized), None)


_service: AvatarSpeechCatalogService | None = None


def get_avatar_speech_catalog_service() -> AvatarSpeechCatalogService:
    global _service
    if _service is None:
        _service = AvatarSpeechCatalogService()
    return _service
