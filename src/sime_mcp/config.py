"""Configuration and local privacy defaults."""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

load_dotenv()

SIME_ORIGIN = "https://agenda.sime.md"
SIME_START_URL = f"{SIME_ORIGIN}/ords/r/agenda/main/main-page"
MOLDOVA_TZ = ZoneInfo("Europe/Chisinau")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class Settings(BaseModel):
    data_dir: Path = Field(default_factory=lambda: Path("~/.local/share/sime-mcp").expanduser())
    profile_dir: Path | None = None
    cache_enabled: bool = False
    cache_ttl_seconds: int = Field(default=900, ge=0)
    browser_headless: bool = True
    browser_timeout_ms: int = Field(default=30_000, ge=1000)

    @field_validator("data_dir", "profile_dir", mode="before")
    @classmethod
    def expand_path(cls, value: str | Path | None) -> Path | None:
        return Path(value).expanduser().resolve() if value is not None else None

    @property
    def browser_profile(self) -> Path:
        return self.profile_dir or self.data_dir / "browser-profile"

    @property
    def database_path(self) -> Path:
        return self.data_dir / "cache.sqlite3"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            data_dir=os.getenv("SIME_DATA_DIR", "~/.local/share/sime-mcp"),
            profile_dir=os.getenv("SIME_PROFILE_DIR") or None,
            cache_enabled=_env_bool("SIME_CACHE_ENABLED", False),
            cache_ttl_seconds=int(os.getenv("SIME_CACHE_TTL_SECONDS", "900")),
            browser_headless=_env_bool("SIME_BROWSER_HEADLESS", True),
            browser_timeout_ms=int(os.getenv("SIME_BROWSER_TIMEOUT_MS", "30000")),
        )


def make_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        path.chmod(0o700)
