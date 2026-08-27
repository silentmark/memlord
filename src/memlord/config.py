from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMLORD_", env_file=".env", extra="ignore")

    db_url: str = "postgresql+asyncpg://postgres:postgres@localhost/memlord"
    db_echo: bool = False

    model_dir: Path = Path("src/memlord/onnx")
    # Output dimension of the embedding model. Must match the column type in the
    # database; the vector-dimension migration keeps the two in sync.
    embedding_dim: int = Field(384, gt=0)
    # "onnx" runs the bundled model in-process; "http" delegates to an
    # OpenAI-compatible /v1/embeddings endpoint.
    embedding_provider: Literal["onnx", "http"] = "onnx"
    embedding_url: str | None = None
    embedding_model: str = "default"
    embedding_api_key: str | None = None
    embedding_timeout: float = Field(30.0, gt=0)
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str = "http://localhost:8000"
    rrf_k: int = 60
    default_limit: int = 10
    sim_threshold: float = Field(0.25, ge=0.0, le=1.0)
    dedup_threshold: float = Field(0.85, ge=0.0, le=1.0)
    oauth_jwt_secret: str = "memlord-dev-secret-please-change"

    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: EmailStr | None = None
    smtp_tls: bool = True

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


settings = Settings()
