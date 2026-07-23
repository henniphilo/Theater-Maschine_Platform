from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_DEFAULT_ASSET_MIME_TYPES = [
    "application/json",
    "audio/aiff",
    "audio/mpeg",
    "audio/mp3",
    "audio/wav",
    "audio/x-aiff",
    "audio/x-wav",
    "image/jpeg",
    "image/png",
    "image/webp",
    "text/csv",
    "text/markdown",
    "text/plain",
    "text/x-markdown",
    "application/csv",
    "video/mp4",
    "video/quicktime",
    "video/webm",
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Debate API"
    app_env: str = "dev"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = [
        "http://localhost:3003",
        "http://localhost:3000",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:3000",
    ]

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aidebatte"
    redis_url: str = "redis://localhost:6379/0"

    # Asset object storage (MVP: local filesystem under storage_root)
    storage_root: str = "storage"
    asset_max_upload_bytes: int = 100 * 1024 * 1024
    asset_allowed_mime_types: list[str] = list(_DEFAULT_ASSET_MIME_TYPES)
    asset_preview_text_chars: int = 4000

    # Optional HMAC key for sealing Device.configuration (never commit real values).
    # When unset, configs are stored as a plain sealed envelope and still redacted from APIs.
    device_config_key: str | None = None

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    tts_provider: str = "auto"
    tts_voice_openai: str = "Petra (Premium)"
    tts_voice_anthropic: str = "Viktor (Enhanced)"
    tts_voice_ai_a: str = "Anna"
    tts_voice_ai_b: str = "Martin"
    tts_voice_narrator: str = "Alex"
    tts_voice_inszenierung_ai_a: str = "Eddy"
    tts_voice_inszenierung_ai_b: str = "Sandy"
    tts_voice_inszenierung_narrator: str = "Helena"
    tts_edge_voice_openai: str = "de-DE-ConradNeural"
    tts_edge_voice_anthropic: str = "de-DE-KatjaNeural"
    tts_edge_voice_ai_a: str = "de-DE-KillianNeural"
    tts_edge_voice_ai_b: str = "de-DE-SeraphinaMultilingualNeural"
    tts_edge_voice_narrator: str = "de-DE-AmalaNeural"
    tts_edge_voice_inszenierung_ai_a: str = "de-DE-FlorianMultilingualNeural"
    tts_edge_voice_inszenierung_ai_b: str = "de-DE-SeraphinaMultilingualNeural"
    tts_edge_voice_inszenierung_narrator: str = "de-DE-KatjaNeural"

    director_enabled: bool = True
    director_dramaturgy_mode: Literal["llm", "rules"] = "llm"
    director_execute_mode: Literal["immediate", "sequenced"] = "sequenced"
    director_osc_queue: bool = True
    director_autopilot_default: bool = True
    director_log_path: str = "logs/director.log"
    director_data_dir: str = "data"
    osc_host: str = "127.0.0.1"
    osc_port: int = 7000
    osc_dry_run: bool = False
    osc_log_commands: bool = True
    osc_log_path: str = "logs/osc.log"
    signal_trace_path: str = "logs/signal_trace.jsonl"
    signal_trace_enabled: bool | None = None
    light_output: Literal["tcp", "osc", "mirror"] = "tcp"
    light_osc_mirror: bool = False
    light_tcp_host: str = "10.101.90.112"
    light_tcp_port: int = 3032
    light_tcp_protocol: str = "1.0"
    light_tcp_handshake: Literal["none", "json"] = "none"
    light_tcp_timeout: float = 5.0
    light_tcp_connect_delay: float = 0.5
    light_tcp_read_ack: bool = False
    light_tcp_ack_timeout: float = 2.0
    light_osc_send_delay: float = 0.0
    light_osc_host: str | None = None
    light_osc_port: int = 3032
    light_osc_tcp_format: Literal["json", "binary"] = "binary"
    light_osc_tcp_framing: Literal["length_prefix", "raw", "slip"] = "length_prefix"
    technik_hold_interval_seconds: float = 2.0
    dramaturgy_discussion_rounds_default: int = 1
    dramaturgy_discussion_rounds_max: int = 2
    dramaturgy_discussion_max_tokens: int = 400
    dramaturgy_media_package_max_tokens: int = 1200
    dramaturgy_decision_max_tokens: int = 1200
    dramaturgy_rules_excerpt_chars: int = 3500
    teil2_dramaturgy_chunk_size: int = 12
    teil2_atmosphere_use_llm: bool = False
    teil2_use_analyse_llm: bool = False
    teil2_prepare_model: str = "gpt-4o-mini"
    dramaturgy_whole_text_max_chars: int = 8000
    dramaturgy_statements_per_dramaturg: int = 2
    dramaturgy_statement_max_chars: int = 450
    dramaturgy_media_package_max_chars: int = 1800
    part1_workshop_preview_hardware: bool = False
    sound_output: Literal["osc", "midi", "both"] = "midi"
    sound_osc_mirror: bool = False
    sound_midi_port: str | None = None
    sound_midi_channel: int = 1
    sound_midi_note_base: int = 36
    sound_midi_default_velocity: int = 100
    sound_midi_auto_note: bool = False
    sound_midi_map_path: str = "data/sound_midi_map.json"
    sound_cues_path: str = "data/sound_cues.json"
    video_cues_path: str = "data/video_cues.json"
    visual_output: Literal["pixera", "touchdesigner", "both"] = "pixera"
    pixera_osc_host: str | None = None
    pixera_osc_port: int | None = None
    # Avatar-video completion gate (QLab test now; Pixera stage later — docs/avatar_done_gate.md)
    avatar_done_gate_enabled: bool = False
    avatar_done_osc_host: str = "127.0.0.1"
    avatar_done_osc_port: int = 8991
    avatar_done_timeout_grace_ms: int = 2000
    uvicorn_access_log: bool = False
    app_log_level: str = "warning"

    def light_desk_host(self) -> str:
        if self.light_output == "tcp":
            return self.light_tcp_host
        return self.light_osc_host or self.light_tcp_host

    def light_desk_port(self) -> int:
        if self.light_output == "tcp":
            return self.light_tcp_port
        return self.light_osc_port

    def light_uses_desk(self) -> bool:
        return self.light_output in ("tcp", "osc")

    def light_uses_preview_osc(self) -> bool:
        """QLab relay / TouchDesigner mirror (/light/set_scene on OSC_HOST:OSC_PORT)."""
        return self.light_output == "mirror" or self.light_osc_mirror

    @field_validator("asset_allowed_mime_types", mode="before")
    @classmethod
    def parse_allowed_mime_types(cls, value: object) -> object:
        if isinstance(value, str):
            parts = [part.strip() for part in value.split(",") if part.strip()]
            return parts
        return value

    def resolved_storage_root(self) -> Path:
        path = Path(self.storage_root)
        if not path.is_absolute():
            # Prefer repo root when running from backend/ (run-native.sh cwd).
            cwd = Path.cwd()
            if cwd.name == "backend" and (cwd.parent / "frontend").is_dir():
                path = cwd.parent / path
            else:
                path = cwd / path
        return path.resolve()

    def allowed_mime_type_set(self) -> frozenset[str]:
        return frozenset(self.asset_allowed_mime_types)


settings = Settings()
