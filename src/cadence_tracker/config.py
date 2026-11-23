"""Paths and analysis settings.

Two kinds of configuration exist:

* **Paths** (where the database, raw files and backups live). They come from
  environment variables so the same code can run on the real database or on the
  demo database (`CTRACK_DB`).
* **Analysis settings** (thresholds used by metrics and classification). They are
  user-editable from the UI and persisted in the `settings` table of the database
  (see `storage.repository.load_settings`). Defaults live in `Settings` below.

See docs/specs/F09-parametres.md.
"""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

# Repository root: src/cadence_tracker/config.py -> parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[2]

KEYRING_SERVICE = "cadence-tracker"
KEYRING_GARMIN_KEY = "garmin-personal-api-key"


def data_dir() -> Path:
    """Directory holding the database and its backups."""
    return Path(os.environ.get("CTRACK_DATA_DIR", PROJECT_ROOT / "data")).expanduser()


def db_path() -> Path:
    """SQLite database in use (`CTRACK_DB` overrides the default)."""
    env = os.environ.get("CTRACK_DB")
    return Path(env).expanduser() if env else data_dir() / "cadence.db"


def demo_db_path() -> Path:
    return data_dir() / "demo.db"


def backups_dir() -> Path:
    return data_dir() / "backups"


def garmin_token_cache() -> Path:
    """Bearer-token cache of the Garmin Personal API (created with 0600 permissions)."""
    return Path("~/.config/cadence-tracker/garmin-bearer-token.json").expanduser()


@dataclass
class Settings:
    """User-tunable analysis parameters (persisted as JSON in the database)."""

    # Heart rate. None -> estimated from the data (highest per-activity HR peak).
    hr_max: int | None = None

    # A sample counts as "running" (vs walking / stopped) above both thresholds.
    min_run_speed_mps: float = 1.8  # ~9:15 min/km
    min_run_cadence_spm: float = 130.0

    # Classification thresholds (see analysis/classification.py).
    ef_max_hr_pct: float = 0.80
    tempo_min_hr_pct: float = 0.86
    long_run_min_duration_min: float = 80.0
    long_run_min_distance_km: float = 16.0
    trail_min_ascent_m_per_km: float = 25.0
    interval_min_speed_cv: float = 0.10  # on running seconds (stops excluded)
    interval_min_fast_blocks: int = 4  # efforts held >= 30 s

    # Cadence goal (see analysis/cadence_goal.py).
    cadence_target_spm: float | None = None
    cadence_goal_start: str | None = None  # ISO date
    natural_session_types: list[str] = field(default_factory=lambda: ["ef", "long"])

    # Garmin sync: earliest date fetched on a full sync (None -> everything).
    garmin_history_start: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Settings:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
