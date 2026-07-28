"""
Central configuration via environment variables.
Uses pydantic-settings for typed validation.
"""

from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Environment ───────────────────────────────────────────
    # Deployment environment: "development", "staging", or "production".
    # Controls debug mode, CORS strictness, and other environment-specific
    # behaviour. Staging is a pre-production instance for validation.
    ENVIRONMENT: str = "development"
    # Debug mode. If not set explicitly, derived from ENVIRONMENT:
    #   development → True, staging/production → False.
    DEBUG: Optional[bool] = None

    @model_validator(mode="after")
    def _validate_environment(self):
        if self.DEBUG is None:
            self.DEBUG = self.ENVIRONMENT == "development"
        return self

    # ── Server ──────────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    # API version prefix. All routes are registered under this path.
    # Increment the version number for breaking changes.
    API_PREFIX: str = "/api/v1"
    # Allowed CORS origins for the Tauri frontend and dev servers.
    # In development the Vite dev server runs on localhost:1420;
    # Tauri uses tauri://localhost / https://tauri.localhost.
    # For production deployments, set CORS_ORIGINS to a
    # comma-separated list of exact origins (e.g. "https://app.example.com").
    # Never use "*" with allow_credentials=True.
    CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://localhost:8000",
        "tauri://localhost",
        "https://tauri.localhost",
    ]

    # ── LiteLLM ─────────────────────────────────────────────
    LITELLM_API_KEY: str = ""
    LITELLM_MODEL: str = "openai/gpt-4o"
    LITELLM_FALLBACK_MODEL: str = "anthropic/claude-3-haiku"
    LITELLM_MAX_TOKENS: int = 4096
    LITELLM_TEMPERATURE: float = 0.2

    # ── Vector Store ─────────────────────────────────────────
    VECTOR_STORE_PROVIDER: str = "pgvector"  # pinecone | pgvector | qdrant
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""
    PINECONE_INDEX_NAME: str = "legis-agent"

    # ── PostgreSQL / pgvector ────────────────────────────────
    DATABASE_URL: str = "postgresql+psycopg2://user:password@localhost:5432/legisagent"

    # ── Embeddings ───────────────────────────────────────────
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    EMBEDDING_PROVIDER: str = "auto"  # auto | fastembed | openai | mock
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200

    # ── Langfuse (Observability) ─────────────────────────────
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # ── Security ──────────────────────────────────────────────
    # Enable header-based auth (X-User-Id, X-User-Role) for development only.
    # In production, only Bearer token auth is allowed.
    ENABLE_HEADER_AUTH: bool = False
    # Default admin password for first-run setup.
    # If empty, a random 24-char password is generated and logged.
    ADMIN_PASSWORD: str = ""

    # ── HTTPS / TLS ────────────────────────────────────────────
    # Enforce HTTP→HTTPS redirect. Disabled by default because the
    # backend runs as a local server for the Tauri desktop app.
    # Enable when deploying the API publicly behind TLS.
    ENFORCE_HTTPS: bool = False
    # Path to TLS certificate file (PEM format) for uvicorn.
    # Only needed if the API handles TLS directly (not behind a reverse proxy).
    SSL_CERTFILE: str = ""
    # Path to TLS private key file (PEM format) for uvicorn.
    SSL_KEYFILE: str = ""

    # ── Upload limits ─────────────────────────────────────────
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB

    # ── Alerting / Monitoring ───────────────────────────────────
    # Webhook URL for sending production alerts (Slack, Discord, etc.).
    # If empty, alerts are logged but not sent externally.
    # Example: "https://hooks.slack.com/services/T00/B00/xxxx"
    ALERT_WEBHOOK_URL: str = ""
    # Minimum interval (seconds) between alerts of the same type
    # to avoid notification spam.
    ALERT_COOLDOWN_SECONDS: int = 300
    # Error-rate threshold: trigger alert when N errors accumulate
    # within a window. 0 disables error-rate alerts.
    ALERT_ERROR_THRESHOLD: int = 10
    # Circuit breaker open triggers an alert when true.
    ALERT_ON_CIRCUIT_OPEN: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
