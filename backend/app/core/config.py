from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AI Debate API"
    app_env: str = "dev"
    app_debug: bool = False
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/aidebatte"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    tts_provider: str = "auto"
    tts_voice_openai: str = "Samantha"
    tts_voice_anthropic: str = "Flo"
    tts_edge_voice_openai: str = "de-DE-ConradNeural"
    tts_edge_voice_anthropic: str = "de-DE-KatjaNeural"

    director_enabled: bool = True
    director_autopilot_default: bool = True
    director_log_path: str = "logs/director.log"
    director_data_dir: str = "data"
    osc_host: str = "127.0.0.1"
    osc_port: int = 7000
    osc_dry_run: bool = False


settings = Settings()
