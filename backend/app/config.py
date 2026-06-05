"""
Application configuration via environment variables / .env file.

Design principle for desktop packaging:
  - Port defaults to 0 (OS auto-assign) so Electron can spawn this backend
    without port conflicts — the actual port is printed to stdout on startup.
  - All filesystem paths resolve relative to the executable when bundled,
    or relative to the project root in dev mode.
"""
from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Server ────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 0                       # 0 = OS auto-assign (desktop packaging)
    log_level: str = "INFO"
    cors_origins: list[str] = ["*"]

    # ── Data directory (writable) ─────────────────────────────
    # In desktop mode, this is set relative to the user's app data.
    # In dev mode, defaults to ./data under project root.
    data_dir: str = ""

    @property
    def resolved_data_dir(self) -> Path:
        """Resolve the writable data directory."""
        if self.data_dir:
            return Path(self.data_dir)
        return Path(__file__).resolve().parent.parent.parent / "data"

    # ── Models directory (read-only resources) ─────────────────
    models_dir: str = ""

    @property
    def resolved_models_dir(self) -> Path:
        """Resolve the ASR models directory."""
        if self.models_dir:
            return Path(self.models_dir)
        return Path(__file__).resolve().parent.parent.parent / "models"

    # ── ASR ───────────────────────────────────────────────────
    asr_model_path: str = ""            # defaults to models_dir/sherpa-onnx-paraformer
    asr_encoder: str = ""
    asr_decoder: str = ""
    asr_tokens: str = ""
    asr_sample_rate: int = 16000
    asr_feature_dim: int = 80

    # ── Translation ───────────────────────────────────────────
    nmt_model_path: str = "Helsinki-NLP/opus-mt-en-zh"
    llm_provider: str = "openai"        # "openai" | "anthropic" | "deepseek"
    llm_model: str = "gpt-4o"
    llm_api_key: str = ""
    llm_base_url: str = ""
    enable_correction: bool = True

    # ── Audio ─────────────────────────────────────────────────
    audio_chunk_ms: int = 200
    audio_buffer_size: int = 100        # ring buffer capacity (chunks)
    vad_threshold: float = 0.5
    min_speech_duration: float = 0.3
    min_silence_duration: float = 0.5

    # ── Database ──────────────────────────────────────────────
    @property
    def database_url(self) -> str:
        db_dir = self.resolved_data_dir
        db_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{db_dir}/translations.db"

    # ── Redis (optional, for multi-worker scenarios) ──────────
    redis_url: str = ""

    # ── Session ───────────────────────────────────────────────
    session_timeout_seconds: int = 3600
    max_concurrent_sessions: int = 50


@lru_cache()
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
