"""Runtime configuration.

All settings come from environment variables (prefix-free names documented in `.env.example`).
Two modes exist:

* ``local``: the desktop executable. Single local owner, no password, API bound to loopback,
  SQLite in the user data directory. A secret key is generated on first start and stored there.
* ``cloud``: the hosted web app. Email and password accounts, JWT, PostgreSQL recommended.
  A strong ``SECRET_KEY`` must be provided.
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_data_dir() -> Path:
    """Platform-appropriate per-user data directory for the desktop build."""
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "MDOS"
    if os.uname().sysname == "Darwin":  # pragma: no cover - platform specific
        return Path.home() / "Library" / "Application Support" / "MDOS"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "mdos"


class Settings(BaseSettings):
    # Empty values (``SECRET_KEY=``) count as unset, so a copied .env.example never sets a blank secret.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)

    mdos_mode: Literal["local", "cloud"] = "local"
    mdos_data_dir: Path = Field(default_factory=default_data_dir)
    database_url: str | None = None
    secret_key: str | None = None
    access_token_minutes: int = 12 * 60
    # Cloud sign-up. Unset: only the first account may register (it becomes the workspace owner), so a fresh
    # server cannot be claimed by strangers later or use your Claude key. true: anyone who can reach the
    # server can create their own isolated workspace. false: closed.
    allow_registration: bool | None = None

    anthropic_api_key: str | None = None
    mdos_llm_model: str = "claude-opus-5-5"
    mdos_llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "medium"
    mdos_llm_fallbacks: bool = True
    mdos_llm_timeout_seconds: float = 120.0
    mdos_llm_max_input_chars: int = 60_000

    max_upload_mb: int = 25
    max_json_mb: int = 5  # any request that is not a file upload
    max_rows: int = 100_000
    max_cols: int = 500

    # Browser origins allowed to call the API from another domain. Empty: the app serves its own UI (and the Vite
    # dev server proxies /api), so no cross-origin access is granted.
    cors_origins: str = ""
    # Cloud mode: host names the server answers to (set your public domain). "*" disables the check.
    allowed_hosts: str = "localhost,127.0.0.1"
    # Session cookie Secure flag: None means "when the request arrived over HTTPS" (behind a TLS proxy).
    cookie_secure: bool | None = None
    # Desktop: a per-launch key the browser must present once to open a session (set by the launcher).
    mdos_local_key: str | None = None
    # Interactive API docs at /api/docs (loads Swagger UI from a CDN). Off unless a developer turns it on.
    enable_api_docs: bool = False
    execution_mode: Literal["thread", "sync"] = "thread"

    rate_limit_auth_per_minute: int = 10
    rate_limit_agents_per_minute: int = 30
    rate_limit_uploads_per_minute: int = 30

    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def is_local(self) -> bool:
        return self.mdos_mode == "local"

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.mdos_data_dir / 'mdos.db').as_posix()}"

    @property
    def storage_dir(self) -> Path:
        return self.mdos_data_dir / "files"

    @property
    def api_docs_enabled(self) -> bool:
        return self.enable_api_docs

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)

    def resolved_secret_key(self) -> str:
        """Return the JWT signing key.

        Cloud mode refuses to start without an explicit strong key. Local mode generates one
        on first start and keeps it in the data directory so sessions survive restarts.
        """
        if self.secret_key:
            if self.mdos_mode == "cloud" and len(self.secret_key) < 32:
                raise RuntimeError("SECRET_KEY must be at least 32 characters in cloud mode.")
            return self.secret_key
        if self.mdos_mode == "cloud":
            raise RuntimeError("SECRET_KEY is required in cloud mode.")
        key_file = self.mdos_data_dir / "secret.key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip()
        self.mdos_data_dir.mkdir(parents=True, exist_ok=True)
        key = secrets.token_urlsafe(48)
        key_file.write_text(key, encoding="utf-8")
        try:
            key_file.chmod(0o600)
        except OSError:  # pragma: no cover - Windows
            pass
        return key


@lru_cache
def get_settings() -> Settings:
    return Settings()
