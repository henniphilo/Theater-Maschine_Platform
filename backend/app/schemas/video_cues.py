from pydantic import BaseModel, Field, field_validator


class VideoProjectorEntry(BaseModel):
    id: str = Field(min_length=1, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")
    pixera_prefix: str = Field(min_length=1, max_length=80)
    name: str = Field(default="", max_length=80)
    description: str = Field(default="", max_length=300)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()


class VideoClipEntry(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z][a-z0-9_]*$")
    pixera_name: str = Field(min_length=1, max_length=80)
    label: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    tags: list[str] = Field(default_factory=list)
    moods: list[str] = Field(default_factory=list)
    intensity_min: float = Field(default=0.0, ge=0.0, le=1.0)
    intensity_max: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return value.strip().lower()


class VideoCueCatalog(BaseModel):
    version: int = 1
    osc_address: str = "/pixera/args/cue/apply"
    projectors: list[VideoProjectorEntry] = Field(default_factory=list)
    clips: list[VideoClipEntry] = Field(default_factory=list)
