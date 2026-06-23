"""Parse uploaded scene files for Teil 2 corpus import."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app.schemas.inszenierung import CreateAnimalSceneRequest
from app.services.script_splitter import extract_scene_title_and_body

_HEADER_TIER_RE = re.compile(r"^(?:tier|animal)\s*:\s*(.+)$", re.IGNORECASE)
_HEADER_SCENE_RE = re.compile(r"^(?:szene|title|titel)\s*:\s*(.+)$", re.IGNORECASE)
_SCENE_SPLIT_RE = re.compile(r"\n\s*---\s*\n")


def _animal_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem.strip()
    if not stem:
        return None
    if "_" in stem:
        return stem.split("_", 1)[0].replace("-", " ").strip()
    return stem


def _parse_metadata_header(text: str) -> tuple[str | None, str | None, str]:
    """Read optional Tier:/Szene: lines at top; return animal, title, remaining body."""
    animal: str | None = None
    title: str | None = None
    lines = text.splitlines()
    body_start = 0
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            body_start = index + 1
            break
        if stripped == "---":
            body_start = index + 1
            break
        tier_match = _HEADER_TIER_RE.match(stripped)
        if tier_match:
            animal = tier_match.group(1).strip()
            body_start = index + 1
            continue
        scene_match = _HEADER_SCENE_RE.match(stripped)
        if scene_match:
            title = scene_match.group(1).strip()
            body_start = index + 1
            continue
        body_start = index
        break
    body = "\n".join(lines[body_start:]).strip()
    return animal, title, body


def _scene_from_text(
    text: str,
    *,
    filename: str,
    default_animal: str | None = None,
) -> CreateAnimalSceneRequest:
    animal_hint, title_hint, body = _parse_metadata_header(text)
    if not body:
        body = text.strip()
    scene_title, source_text = extract_scene_title_and_body(body)
    animal = animal_hint or default_animal or _animal_from_filename(filename)
    if not animal:
        raise ValueError(f"Tier fehlt in {filename!r} — Kopfzeile „Tier: …“ oder Dateiname „Bär.txt“")
    if not source_text.strip():
        raise ValueError(f"Leerer Text in {filename!r}")
    return CreateAnimalSceneRequest(
        animal=animal,
        title=title_hint or scene_title or "",
        source_text=source_text.strip(),
    )


def parse_json_scenes(content: str, *, filename: str) -> list[CreateAnimalSceneRequest]:
    data = json.loads(content)
    if isinstance(data, dict) and "scenes" in data:
        data = data["scenes"]
    if not isinstance(data, list):
        raise ValueError(f"{filename}: JSON muss ein Array oder {{\"scenes\": [...]}} sein")
    return [CreateAnimalSceneRequest.model_validate(item) for item in data]


def parse_text_scenes(content: str, *, filename: str) -> list[CreateAnimalSceneRequest]:
    trimmed = content.strip()
    if not trimmed:
        raise ValueError(f"{filename}: Datei ist leer")

    chunks = _SCENE_SPLIT_RE.split(trimmed)
    if len(chunks) > 1:
        default_animal = _animal_from_filename(filename)
        return [_scene_from_text(chunk, filename=filename, default_animal=default_animal) for chunk in chunks if chunk.strip()]

    return [_scene_from_text(trimmed, filename=filename)]


def parse_uploaded_file(filename: str, content: str) -> list[CreateAnimalSceneRequest]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".json":
        return parse_json_scenes(content, filename=filename)
    if suffix in {".txt", ".text", ""}:
        return parse_text_scenes(content, filename=filename)
    raise ValueError(f"Nicht unterstütztes Format: {filename} (nur .txt, .json)")


def parse_uploaded_files(files: list[tuple[str, str]]) -> list[CreateAnimalSceneRequest]:
    scenes: list[CreateAnimalSceneRequest] = []
    for filename, content in files:
        scenes.extend(parse_uploaded_file(filename, content))
    if not scenes:
        raise ValueError("Keine Szenen in den Dateien gefunden")
    return scenes
