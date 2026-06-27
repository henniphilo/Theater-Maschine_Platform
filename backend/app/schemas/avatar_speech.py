from typing import Literal

from pydantic import BaseModel, Field

AvatarRole = Literal["delphin", "baerenklau", "lamm", "petya", "wolf"]


class AvatarSpeechCue(BaseModel):
    id: str = Field(min_length=1, max_length=32)
    avatar: AvatarRole
    text: str = Field(min_length=1)
    video_clip_id: str = Field(min_length=1)
    scene_ref: str | None = None
    duration_ms: int | None = Field(default=None, ge=0)


class AvatarSpeechCatalog(BaseModel):
    version: int = 1
    cues: list[AvatarSpeechCue] = Field(default_factory=list)
