"""Source-independent representation of an activity, produced by every parser.

All importers (FIT, TCX, GPX, Garmin API, demo generator) convert their input into
a `ParsedActivity`. The ingestion pipeline (`ingest/pipeline.py`) only knows this
structure, so adding a new source never touches storage or analysis code.

See docs/architecture.md ("Modèle pivot").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import pandas as pd

# Columns of `ParsedActivity.samples` (one row per recorded instant).
# Privacy by design (docs/adr/0004-aucune-donnee-gps.md): there is NO position
# column. Parsers may read coordinates only to compute a missing distance, in
# memory, and must never return them.
SAMPLE_COLUMNS = [
    "t_s",  # int, seconds since activity start
    "distance_m",  # cumulative distance
    "speed_mps",
    "cadence_raw",  # cadence as found in the file (unit given by cadence_unit)
    "heart_rate",
    "altitude_m",
]

# Columns of `ParsedActivity.laps`.
LAP_COLUMNS = [
    "lap_index",
    "start_s",
    "duration_s",
    "distance_m",
    "speed_mps",
    "heart_rate",
    "cadence_spm",
    "intensity",  # 'active' | 'rest' | 'warmup' | 'cooldown' | 'recovery' | None
]

CadenceUnit = Literal["strides", "steps", "unknown"]

# Sports considered as running. Everything else is ignored at import.
RUNNING_SPORTS = {"running"}
SUB_SPORT_LABELS = {
    "road": "Route",
    "trail": "Trail",
    "treadmill": "Tapis",
    "track": "Piste",
}


@dataclass
class ParsedActivity:
    source: str  # 'fit_file' | 'tcx_file' | 'gpx_file' | 'garmin_api' | 'demo'
    start_time_utc: datetime  # timezone-aware (UTC)
    sport: str  # normalized: 'running', 'cycling', ... or 'unknown'
    samples: pd.DataFrame  # columns: SAMPLE_COLUMNS (missing channels -> NaN)
    sub_sport: str = "road"  # normalized: 'road' | 'trail' | 'treadmill' | 'track'
    cadence_unit: CadenceUnit = "unknown"
    source_id: str | None = None
    utc_offset_s: int | None = None
    name: str | None = None
    workout_name: str | None = None
    device: str | None = None
    laps: pd.DataFrame | None = None
    # Totals computed by the device (more accurate than our recomputation for
    # ascent, for instance). Keys: elapsed_s, timer_s, distance_m, ascent_m,
    # descent_m, avg_hr, max_hr.
    summary: dict[str, Any] = field(default_factory=dict)


def normalize_sub_sport(value: str | None) -> str:
    """Map FIT/TCX/GPX/Garmin sub-sport names to our 4 terrain categories."""
    v = (value or "").lower()
    if "trail" in v or "mountain" in v or "ultra" in v:
        return "trail"
    if "treadmill" in v or "indoor" in v or "virtual" in v:
        return "treadmill"
    if "track" in v:
        return "track"
    return "road"


def normalize_sport(value: str | None) -> str:
    v = (value or "").lower().strip()
    if v in {"running", "run", "trail_running", "trail run", "9"} or "run" in v:
        return "running"
    if not v:
        return "unknown"
    return v
