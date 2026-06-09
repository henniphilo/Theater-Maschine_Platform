from dataclasses import dataclass, field
from pathlib import Path
import json

from pydantic import BaseModel, Field

from app.core.config import settings


class VideoAsset(BaseModel):
    id: str
    type: str = "video"
    path: str
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    intensity_min: float = 0.0
    intensity_max: float = 1.0
    duration: float = 0.0
    loopable: bool = True
    preferred_blend: str = "slow_fade"


class SoundAsset(BaseModel):
    id: str
    type: str = "sound"
    path: str
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    intensity_min: float = 0.0
    intensity_max: float = 1.0


class LightScene(BaseModel):
    id: str
    description: str = ""
    moods: list[str] = Field(default_factory=list)
    intensity_min: float = 0.0
    intensity_max: float = 1.0
    dmx: dict[str, int] = Field(default_factory=dict)
    fade_time: float = 4.0


@dataclass
class DramaturgyRules:
    keyword_tags: dict[str, list[str]] = field(default_factory=dict)
    mood_keywords: dict[str, list[str]] = field(default_factory=dict)
    intensity_boosters: list[str] = field(default_factory=list)
    min_cue_interval_seconds: dict[str, float] = field(default_factory=dict)


class MediaDatabase:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or self._resolve_data_dir()
        self.videos: list[VideoAsset] = []
        self.sounds: list[SoundAsset] = []
        self.light_scenes: list[LightScene] = []
        self.rules = DramaturgyRules()
        self.reload()

    @staticmethod
    def _resolve_data_dir() -> Path:
        configured = Path(settings.director_data_dir)
        if configured.is_absolute():
            return configured

        module_root = Path(__file__).resolve()
        search_roots = [
            module_root.parents[3],  # /app in Docker, backend/ locally
            module_root.parents[4],  # repo root locally
            Path.cwd(),
        ]
        for root in search_roots:
            candidate = root / configured
            if candidate.exists():
                return candidate
        return Path.cwd() / configured

    def reload(self) -> None:
        media_path = self.data_dir / "media.json"
        light_path = self.data_dir / "light_scenes.json"
        rules_path = self.data_dir / "dramaturgy_rules.json"

        media_data = json.loads(media_path.read_text(encoding="utf-8"))
        light_data = json.loads(light_path.read_text(encoding="utf-8"))
        rules_data = json.loads(rules_path.read_text(encoding="utf-8"))

        self.videos = [VideoAsset.model_validate(v) for v in media_data.get("videos", [])]
        self.sounds = [SoundAsset.model_validate(s) for s in media_data.get("sounds", [])]
        self.light_scenes = [LightScene.model_validate(s) for s in light_data.get("scenes", [])]
        self.rules = DramaturgyRules(
            keyword_tags=rules_data.get("keyword_tags", {}),
            mood_keywords=rules_data.get("mood_keywords", {}),
            intensity_boosters=rules_data.get("intensity_boosters", []),
            min_cue_interval_seconds=rules_data.get("min_cue_interval_seconds", {}),
        )

    def get_video_by_tags(
        self,
        tags: list[str],
        mood: str,
        intensity: float,
        exclude_ids: list[str] | None = None,
    ) -> VideoAsset | None:
        exclude = set(exclude_ids or [])
        candidates = [
            v
            for v in self.videos
            if v.id not in exclude
            and v.intensity_min <= intensity <= v.intensity_max
            and self._matches(v.tags, v.moods, tags, mood)
        ]
        return candidates[0] if candidates else self._fallback_video(exclude, intensity)

    def get_sound_by_tags(
        self,
        tags: list[str],
        mood: str = "",
        intensity: float = 0.5,
        exclude_ids: list[str] | None = None,
    ) -> SoundAsset | None:
        exclude = set(exclude_ids or [])
        candidates = [
            s
            for s in self.sounds
            if s.id not in exclude
            and s.intensity_min <= intensity <= s.intensity_max
            and self._matches(s.tags, s.moods, tags, mood)
        ]
        return candidates[0] if candidates else self._fallback_sound(exclude, intensity)

    def get_light_scene(self, mood: str, intensity: float) -> LightScene | None:
        candidates = [
            s
            for s in self.light_scenes
            if s.intensity_min <= intensity <= s.intensity_max
            and (not mood or mood in s.moods or not s.moods)
        ]
        return candidates[0] if candidates else (self.light_scenes[0] if self.light_scenes else None)

    @staticmethod
    def _matches(
        asset_tags: list[str],
        asset_moods: list[str],
        tags: list[str],
        mood: str,
    ) -> bool:
        tag_hit = any(t in asset_tags for t in tags) or any(
            any(kw in asset_tags for kw in [t]) for t in tags
        )
        mood_hit = not mood or mood in asset_moods
        return tag_hit or mood_hit

    def _fallback_video(self, exclude: set[str], intensity: float) -> VideoAsset | None:
        for video in self.videos:
            if video.id not in exclude and video.intensity_min <= intensity <= video.intensity_max:
                return video
        return next((v for v in self.videos if v.id not in exclude), None)

    def _fallback_sound(self, exclude: set[str], intensity: float) -> SoundAsset | None:
        for sound in self.sounds:
            if sound.id not in exclude and sound.intensity_min <= intensity <= sound.intensity_max:
                return sound
        return next((s for s in self.sounds if s.id not in exclude), None)

    def register_recording(self, recording_id: str, path: str, tags: list[str]) -> VideoAsset:
        """Phase 4 stub: add live recording to in-memory catalog."""
        asset = VideoAsset(
            id=recording_id,
            path=path,
            tags=["live", "recording", *tags],
            moods=["live"],
            intensity_min=0.0,
            intensity_max=1.0,
            duration=0.0,
            loopable=False,
            preferred_blend="slow_fade",
        )
        self.videos.append(asset)
        return asset
