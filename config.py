"""
Lead-Ops · Configuration
========================
Centralised configuration loader.

Reads environment variables from a ``.env`` file (via python-dotenv)
and exposes them as a validated ``Settings`` dataclass.

Usage::

    from config import settings

    print(settings.HF_TOKEN)
    print(settings.API_BASE_URL)
    print(settings.TAVILY_API_KEY)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# ── Load .env ─────────────────────────────────────────────────────────────────
_ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(_ENV_PATH)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _require(name: str) -> str:
    """Return an env-var value or exit with a clear error."""
    value = os.getenv(name)
    if not value:
        print(
            f"[Lead-Ops Config] ERROR: Required environment variable "
            f"'{name}' is not set.\n"
            f"  → Create a .env file in the project root or export it "
            f"in your shell.\n"
            f"  → See .env.example for the expected format.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def _optional(name: str, default: str = "") -> str:
    """Return an env-var value or a default."""
    return os.getenv(name, default)


# ── Settings ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Settings:
    """
    Application-wide settings.

    Required variables will cause a hard exit if missing,
    making misconfiguration obvious at startup rather than at runtime.
    """

    # ── Required ──────────────────────────────────────────────────────────
    HF_TOKEN: str = field(default_factory=lambda: _require("HF_TOKEN"))
    API_BASE_URL: str = field(default_factory=lambda: _require("API_BASE_URL"))
    TAVILY_API_KEY: str = field(default_factory=lambda: _require("TAVILY_API_KEY"))

    # ── Optional ──────────────────────────────────────────────────────────
    DATABASE_URL: str = field(
        default_factory=lambda: _optional("DATABASE_URL", "sqlite:///lead_ops.db"),
    )
    LOG_LEVEL: str = field(
        default_factory=lambda: _optional("LOG_LEVEL", "INFO"),
    )

    # ── Derived ───────────────────────────────────────────────────────────
    PROJECT_ROOT: Path = field(
        default_factory=lambda: Path(__file__).resolve().parent,
    )


# ── Singleton ─────────────────────────────────────────────────────────────────
# Import this everywhere:  from config import settings
settings = Settings()
