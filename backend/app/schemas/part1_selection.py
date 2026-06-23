from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.director.cues.cue_models import OscCommand, ProjectorTarget
from app.schemas.discussion import DiscussionTurn

PerformancePart = Literal["part1_baerenklau", "part2_delphin_to_mole"]
PreviewMedium = Literal["sound", "music", "video", "light"]

MIN_FINAL_SOUNDS = 6
MIN_FINAL_VIDEOS = 6
MIN_FINAL_LIGHTS = 6
MIN_FINAL_MUSIC = 1

PREVIEW_DURATION_SOUND_SEC = 3.0
PREVIEW_DURATION_MUSIC_SEC = 3.0
PREVIEW_DURATION_VIDEO_SEC = 2.0
PREVIEW_DURATION_LIGHT_SEC = 3.0


class MediaSelectionLists(BaseModel):
    sounds: list[str] = Field(default_factory=list)
    music: list[str] = Field(default_factory=list)
    videos: list[str] = Field(default_factory=list)
    lights: list[str] = Field(default_factory=list)


class Part1BaerenklauSelection(BaseModel):
    part: Literal[1] = 1
    scene: Literal["Bärenklau"] = "Bärenklau"
    script_id: str
    beat_id: str
    selected_by: list[Literal["Claude", "ChatGPT"]] = Field(default_factory=lambda: ["Claude", "ChatGPT"])
    final_sounds: list[str] = Field(default_factory=list)
    final_music: list[str] = Field(default_factory=list)
    final_videos: list[str] = Field(default_factory=list)
    final_lights: list[str] = Field(default_factory=list)
    dramaturgical_reading: str = ""
    cue_strategy: str = ""
    discussion_turns: list[DiscussionTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PreviewCue(BaseModel):
    mode: Literal["preview"] = "preview"
    part: Literal[1] = 1
    target_scene: Literal["Bärenklau"] = "Bärenklau"
    medium: PreviewMedium
    medium_id: str
    projector: ProjectorTarget | None = None
    duration_sec: float = Field(gt=0)
    osc_commands: list[OscCommand] = Field(default_factory=list)
