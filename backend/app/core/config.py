from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Debate API"
    app_env: str = "dev"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3003"]

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aidebatte"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    tts_provider: str = "auto"
    tts_voice_openai: str = "Samantha"
    tts_voice_anthropic: str = "Flo"
    tts_voice_narrator: str = "Alex"
    tts_edge_voice_openai: str = "de-DE-ConradNeural"
    tts_edge_voice_anthropic: str = "de-DE-KatjaNeural"
    tts_edge_voice_narrator: str = "de-DE-AmalaNeural"

    director_enabled: bool = True
    director_dramaturgy_mode: Literal["llm", "rules"] = "llm"
    director_execute_mode: Literal["immediate", "sequenced"] = "sequenced"
    director_autopilot_default: bool = True
    director_log_path: str = "logs/director.log"
    director_data_dir: str = "data"
    osc_host: str = "127.0.0.1"
    osc_port: int = 7000
    osc_dry_run: bool = False
    osc_log_commands: bool = True
    osc_log_path: str = "logs/osc.log"
    light_output: Literal["tcp", "osc"] = "tcp"
    light_osc_mirror: bool = True
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


settings = Settings()
