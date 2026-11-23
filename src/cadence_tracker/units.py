"""Unit conversions and display formatting."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def cadence_to_spm(raw: pd.Series, unit: str) -> pd.Series:
    """Convert a raw cadence channel to steps per minute (both feet).

    FIT files (and Garmin TCX/GPX exports) store running cadence as *strides* per
    minute, i.e. one foot (~80-95). Most apps display steps per minute (~160-190).
    Some devices or exporters already write steps. We therefore decide from the
    declared unit and check it against the data:

    * declared 'strides' -> x2, unless values already look like steps (median > 130);
    * declared 'steps'   -> unchanged;
    * 'unknown'          -> x2 when the median of positive values is below 120.

    See docs/specs/F03-normalisation-metriques.md ("Cadence").
    """
    values = pd.to_numeric(raw, errors="coerce").astype(float)
    positive = values[values > 0]
    if positive.empty:
        return values
    median = float(positive.median())
    if unit == "steps":
        factor = 1.0
    elif unit == "strides":
        factor = 1.0 if median > 130 else 2.0
    else:
        factor = 2.0 if median < 120 else 1.0
    return values * factor


def speed_to_pace_s_per_km(speed_mps: float | None) -> float | None:
    if speed_mps is None or not np.isfinite(speed_mps) or speed_mps <= 0:
        return None
    return 1000.0 / speed_mps


def format_pace(seconds_per_km: float | None) -> str:
    """310.0 -> '5:10'"""
    if seconds_per_km is None or not np.isfinite(seconds_per_km) or seconds_per_km <= 0:
        return "–"
    total = int(round(seconds_per_km))
    return f"{total // 60}:{total % 60:02d}"


def format_pace_from_speed(speed_mps: float | None) -> str:
    return format_pace(speed_to_pace_s_per_km(speed_mps))


def format_duration(seconds: float | None) -> str:
    """3725 -> '1h02', 1500 -> '25 min'"""
    if seconds is None or not np.isfinite(seconds):
        return "–"
    minutes = int(round(seconds / 60))
    if minutes < 60:
        return f"{minutes} min"
    return f"{minutes // 60}h{minutes % 60:02d}"


def format_distance_km(meters: float | None, decimals: int = 1) -> str:
    if meters is None or not np.isfinite(meters):
        return "–"
    return f"{meters / 1000:.{decimals}f} km".replace(".", ",")


def haversine_m(lat1, lon1, lat2, lon2):
    """Vectorized great-circle distance in meters."""
    lat1, lon1, lat2, lon2 = (np.radians(np.asarray(x, dtype=float)) for x in (lat1, lon1, lat2, lon2))
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * 6_371_000 * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def is_number(value) -> bool:
    return value is not None and isinstance(value, (int, float)) and math.isfinite(value)
