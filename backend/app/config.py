"""Runtime settings (pydantic-settings, read from environment / .env).

Every external key is OPTIONAL: absent -> the corresponding adapter runs in mock
mode, so the whole LangGraph pipeline runs end-to-end with no credentials. Drop
the keys into backend/.env to light up the live services with zero code change.
"""
from __future__ import annotations

import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_HERE = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
_REPO = os.path.dirname(_BACKEND)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=os.path.join(_BACKEND, ".env"), extra="ignore")

    # --- external services (optional -> mock mode when unset) ---
    anthropic_api_key: str | None = None
    kiri_api_key: str | None = None
    kiri_webhook_secret: str | None = None
    kiri_base_url: str = "https://api.kiriengine.app/api/v1"
    public_url: str | None = None          # where KIRI posts webhooks (ngrok in dev)
    claude_model: str = "claude-opus-4-8"

    # --- KIRI mock: which local mesh to feed as "reconstruction output" ---
    mock_mesh_path: str = os.path.join(_REPO, "data", "model-mobile 2.stl")

    # --- storage ---
    data_dir: str = os.path.join(_BACKEND, "artifacts")
    checkpoint_db: str = os.path.join(_BACKEND, "checkpoints.sqlite")

    # --- frontend dev origin for CORS ---
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    @property
    def kiri_live(self) -> bool:
        return bool(self.kiri_api_key)

    @property
    def claude_live(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
