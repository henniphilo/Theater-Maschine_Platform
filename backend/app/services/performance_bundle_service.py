import re
import shutil
import zipfile
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status

from app.director.media.database import MediaDatabase
from app.schemas.performance import PERFORMANCE_FORMAT_VERSION, PerformanceAudioEntry, PerformanceManifest
from app.schemas.script import ProductionScript, ScriptBeat
from app.services.script_splitter import split_sentences
from app.services.script_store import ScriptStore
from app.services.spoken_text import spoken_discussion_text
from app.services.tts.performance_voices import performance_speaker_for_sentence
from app.services.tts_service import TTSService

MAX_IMPORT_BYTES = 500 * 1024 * 1024


class PerformanceBundleService:
    def __init__(
        self,
        store: ScriptStore | None = None,
        tts: TTSService | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self.store = store or ScriptStore()
        self.tts = tts or TTSService()
        base = data_dir or MediaDatabase().data_dir
        self.bundle_root = base / "performance_bundles"
        self.bundle_root.mkdir(parents=True, exist_ok=True)

    def bundle_dir(self, script_id: str) -> Path:
        safe = script_id.replace("/", "").replace("..", "")
        return self.bundle_root / safe

    def _require_ready_script(self, script: ProductionScript) -> None:
        if not script.beats:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Script has no beats")
        missing = [b.order + 1 for b in script.beats if b.dramaturgy is None]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dramaturgie fehlt für Abschnitt(e): {missing}",
            )

    async def _render_beat_audio(
        self,
        beat: ScriptBeat,
        audio_dir: Path,
    ) -> list[PerformanceAudioEntry]:
        entries: list[PerformanceAudioEntry] = []
        prefix = f"{beat.order:03d}"

        for index, turn in enumerate(beat.discussion_turns):
            spoken = spoken_discussion_text(turn.content)
            src = await self.tts.synthesize(spoken, turn.speaker, profile="dramaturg")
            ext = src.suffix.lstrip(".")
            rel = f"audio/{prefix}-discussion-{index}.{ext}"
            dest = audio_dir.parent / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            entries.append(
                PerformanceAudioEntry(
                    beat_id=beat.id,
                    beat_order=beat.order,
                    kind="discussion",
                    turn_index=index,
                    speaker=turn.speaker,
                    path=rel,
                    extension=ext,
                )
            )

        if beat.text.strip():
            sentences = split_sentences(beat.text)
            pool = beat.dramaturgy.performance_speakers if beat.dramaturgy else None
            for sentence_index, sentence in enumerate(sentences):
                speaker = performance_speaker_for_sentence(
                    beat.speaker,
                    sentence_index,
                    beat.order,
                    pool=pool or None,
                )
                src = await self.tts.synthesize(sentence, speaker, profile="performance")
                ext = src.suffix.lstrip(".")
                rel = f"audio/{prefix}-performance-{sentence_index}.{ext}"
                dest = audio_dir.parent / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
                entries.append(
                    PerformanceAudioEntry(
                        beat_id=beat.id,
                        beat_order=beat.order,
                        kind="performance",
                        turn_index=sentence_index,
                        speaker=speaker,
                        path=rel,
                        extension=ext,
                    )
                )

        return entries

    async def render_and_save(self, script_id: str) -> PerformanceManifest:
        script = self.store.get(script_id)
        self._require_ready_script(script)
        if not self.tts.is_available():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="TTS nicht verfügbar — Export benötigt Vertonung",
            )

        bundle_dir = self.bundle_dir(script_id)
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        (bundle_dir / "audio").mkdir(parents=True)

        audio_files: list[PerformanceAudioEntry] = []
        for beat in script.beats:
            audio_files.extend(await self._render_beat_audio(beat, bundle_dir / "audio"))

        manifest = PerformanceManifest(
            exported_at=datetime.now(UTC),
            tts_provider=self.tts.resolve_provider(),
            script=script.model_copy(update={"has_rendered_audio": True}),
            audio_files=audio_files,
        )
        (bundle_dir / "manifest.json").write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

        script.has_rendered_audio = True
        self.store.save(script)
        return manifest

    def build_zip_bytes(self, script_id: str) -> tuple[bytes, str]:
        bundle_dir = self.bundle_dir(script_id)
        if not (bundle_dir / "manifest.json").exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Kein Aufführungs-Bundle — zuerst exportieren/rendern",
            )
        manifest = PerformanceManifest.model_validate_json(
            (bundle_dir / "manifest.json").read_text(encoding="utf-8")
        )
        filename = _safe_filename(manifest.script.title)

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in bundle_dir.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(bundle_dir).as_posix())
        return buffer.getvalue(), filename

    def audio_path(self, script_id: str, beat_id: str, asset: str) -> Path:
        bundle_dir = self.bundle_dir(script_id)
        manifest = self._load_manifest(bundle_dir)
        beat = next((b for b in manifest.script.beats if b.id == beat_id), None)
        if beat is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Beat not found")

        entry = self._find_audio_entry(manifest, beat_id, asset)
        if entry is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio not found")

        path = (bundle_dir / entry.path).resolve()
        if not str(path).startswith(str(bundle_dir.resolve())):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid audio path")
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file missing")
        return path

    @staticmethod
    def _find_audio_entry(
        manifest: PerformanceManifest, beat_id: str, asset: str
    ) -> PerformanceAudioEntry | None:
        if asset.startswith("performance-"):
            try:
                sentence_index = int(asset.removeprefix("performance-"))
            except ValueError:
                return None
            return next(
                (
                    e
                    for e in manifest.audio_files
                    if e.beat_id == beat_id
                    and e.kind == "performance"
                    and e.turn_index == sentence_index
                ),
                None,
            )
        if asset == "performance":
            legacy = next(
                (
                    e
                    for e in manifest.audio_files
                    if e.beat_id == beat_id
                    and e.kind == "performance"
                    and e.turn_index is None
                ),
                None,
            )
            if legacy is not None:
                return legacy
            return next(
                (e for e in manifest.audio_files if e.beat_id == beat_id and e.kind == "performance"),
                None,
            )
        if asset.startswith("discussion-"):
            try:
                turn_index = int(asset.removeprefix("discussion-"))
            except ValueError:
                return None
            return next(
                (
                    e
                    for e in manifest.audio_files
                    if e.beat_id == beat_id
                    and e.kind == "discussion"
                    and e.turn_index == turn_index
                ),
                None,
            )
        return None

    def import_zip(self, data: bytes) -> ProductionScript:
        if len(data) > MAX_IMPORT_BYTES:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="ZIP too large")

        buffer = BytesIO(data)
        if not zipfile.is_zipfile(buffer):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ZIP file")
        buffer.seek(0)

        with zipfile.ZipFile(buffer) as archive:
            manifest_name = self._find_manifest_name(archive)
            if not manifest_name:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="manifest.json missing")
            manifest = PerformanceManifest.model_validate_json(archive.read(manifest_name))

            if manifest.format_version != PERFORMANCE_FORMAT_VERSION:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported bundle version")

            self._require_ready_script(manifest.script)

            new_id = str(uuid4())
            bundle_dir = self.bundle_dir(new_id)
            if bundle_dir.exists():
                shutil.rmtree(bundle_dir)
            bundle_dir.mkdir(parents=True)

            for name in archive.namelist():
                if name.endswith("/") or name == manifest_name:
                    continue
                if ".." in Path(name).parts:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path in ZIP")
                target = (bundle_dir / name).resolve()
                if not str(target).startswith(str(bundle_dir.resolve())):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid path in ZIP")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))

            imported_script = manifest.script.model_copy(
                update={"id": new_id, "has_rendered_audio": True, "status": "ready"}
            )
            imported_manifest = manifest.model_copy(update={"script": imported_script})
            (bundle_dir / "manifest.json").write_text(
                imported_manifest.model_dump_json(indent=2),
                encoding="utf-8",
            )
            self.store.save(imported_script)
            return imported_script

    @staticmethod
    def _find_manifest_name(archive: zipfile.ZipFile) -> str | None:
        names = archive.namelist()
        if "manifest.json" in names:
            return "manifest.json"
        candidates = [n for n in names if n.endswith("/manifest.json") or n.endswith("manifest.json")]
        return candidates[0] if len(candidates) == 1 else None

    def _load_manifest(self, bundle_dir: Path) -> PerformanceManifest:
        path = bundle_dir / "manifest.json"
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Performance bundle not found")
        return PerformanceManifest.model_validate_json(path.read_text(encoding="utf-8"))


def _safe_filename(title: str) -> str:
    slug = re.sub(r"[^\w\-]+", "_", title.strip(), flags=re.UNICODE).strip("_")
    slug = slug[:80] or "auffuehrung"
    return f"{slug}.tmshow.zip"


_bundle: PerformanceBundleService | None = None


def get_performance_bundle_service() -> PerformanceBundleService:
    global _bundle
    if _bundle is None:
        _bundle = PerformanceBundleService()
    return _bundle
