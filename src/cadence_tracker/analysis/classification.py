"""Rule-based session classification (always overridable by the user).

Order of precedence (first match wins):

1. keywords in the activity / workout name ("fractionné", "seuil", "EF"...);
2. terrain: trail sub-sport or ascent >= `trail_min_ascent_m_per_km`;
3. structured workouts (laps marked active/rest): long reps (>= 6 min) -> tempo,
   short reps (>= 3, >= 30 s each) -> intervals; else repeated accelerations
   while running (speed CV and number of fast blocks, stops excluded) -> intervals;
4. tempo/threshold: mean HR >= `tempo_min_hr_pct` x HRmax for >= 15 min;
5. long run: duration or distance above thresholds;
6. endurance (EF): mean HR <= `ef_max_hr_pct` x HRmax (or easy pace if no HR);
7. other.

Each result comes with a human-readable reason shown in the UI.
See docs/specs/F06-classification.md.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from cadence_tracker.config import Settings

SESSION_TYPES: dict[str, str] = {
    "ef": "Endurance fondamentale",
    "long": "Sortie longue",
    "intervals": "Fractionné / VMA",
    "tempo": "Seuil / tempo",
    "trail": "Trail",
    "other": "Autre",
}

# Intensity words win over "trail": a plan session named "TRAIL-S2-1-Endurance
# Fondamentale" is an easy run (the terrain is a separate dimension: sub_sport).
_KEYWORDS: list[tuple[str, str]] = [
    (
        "tempo",
        r"\bseuil\b|tempo|threshold|allure ?(sp[ée]cifique|semi|marathon|21|42|10|5)|\bas ?(10|21|42)\b|semi-marathon|marathon",
    ),
    ("intervals", r"fractionn|\bvma\b|interval|\bfrac\b|\d+\s*x\s*\d+|pyramide|cotes|côtes|hill repeat|\bforce\b"),
    ("long", r"sortie longue|\bsl\b|long run"),
    ("ef", r"\bef\b|endurance|footing|easy|recup|récup|recovery|facile|\bbase\b"),
    ("trail", r"\btrail\b"),
]


def _fold(text: str) -> str:
    """Lowercase and strip accents for keyword matching."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _join(names) -> str:
    """Concatenate the names that are real strings (NULL columns come back as NaN)."""
    return " ".join(n for n in names if isinstance(n, str) and n)


def keyword_type(*names: str | None) -> str | None:
    text = _fold(_join(names))
    if not text:
        return None
    for code, pattern in _KEYWORDS:
        if re.search(_fold(pattern), text):
            return code
    return None


def estimate_hr_max(activities: pd.DataFrame) -> float | None:
    """Highest 30-second HR peak observed (robust to single-sample spikes)."""
    if activities.empty or "hr_peak" not in activities:
        return None
    peaks = activities["hr_peak"].dropna()
    peaks = peaks[(peaks > 120) & (peaks < 225)]
    return float(peaks.max()) if len(peaks) else None


def _num(row: Mapping[str, Any], key: str) -> float | None:
    value = row.get(key)
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if np.isfinite(value) else None


def classify(
    row: Mapping[str, Any], settings: Settings, hr_max: float | None, easy_speed: float | None = None
) -> tuple[str, str]:
    """Return (session type code, reason) for one activity row (activities + metrics)."""
    by_name = keyword_type(row.get("name"), row.get("workout_name"))
    if by_name:
        return by_name, f"Mot-clé dans le nom « {_join([row.get('name'), row.get('workout_name')])} »"

    ascent_km = _num(row, "ascent_per_km")
    if row.get("sub_sport") == "trail":
        return "trail", "Activité enregistrée en mode trail"
    if ascent_km is not None and ascent_km >= settings.trail_min_ascent_m_per_km:
        return "trail", f"Dénivelé {ascent_km:.0f} m/km ≥ {settings.trail_min_ascent_m_per_km:.0f}"

    active, rest = _num(row, "n_active_laps") or 0, _num(row, "n_rest_laps") or 0
    if active >= 2 and rest >= 1:
        rep_min = (_num(row, "active_lap_mean_s") or 0) / 60
        if rep_min >= 6:
            return "tempo", f"Séance structurée en blocs longs ({active:.0f} × {rep_min:.0f} min)"
        if active >= 3 and rep_min >= 0.5:  # strides (< 30 s) are not an interval session
            return "intervals", f"Séance structurée ({active:.0f} répétitions, {rest:.0f} récupérations)"
    cv = _num(row, "speed_cv")
    blocks = _num(row, "fast_blocks") or 0
    if cv is not None and cv >= settings.interval_min_speed_cv and blocks >= settings.interval_min_fast_blocks:
        return "intervals", f"Accélérations répétées ({blocks:.0f} blocs rapides, variabilité {cv:.2f})"

    hr = _num(row, "hr_mean")
    hr_pct = hr / hr_max if hr and hr_max else None
    running_min = (_num(row, "running_s") or 0) / 60
    if hr_pct is not None and hr_pct >= settings.tempo_min_hr_pct and running_min >= 15:
        return "tempo", f"FC moyenne {hr_pct:.0%} FCmax ≥ {settings.tempo_min_hr_pct:.0%}"

    duration_min = (_num(row, "elapsed_s") or 0) / 60
    distance_km = (_num(row, "distance_m") or 0) / 1000
    if duration_min >= settings.long_run_min_duration_min or distance_km >= settings.long_run_min_distance_km:
        return "long", f"{distance_km:.1f} km / {duration_min:.0f} min"

    if hr_pct is not None:
        if hr_pct <= settings.ef_max_hr_pct:
            return "ef", f"FC moyenne {hr_pct:.0%} FCmax ≤ {settings.ef_max_hr_pct:.0%}"
        return "other", f"FC moyenne {hr_pct:.0%} FCmax (entre EF et seuil)"
    speed = _num(row, "avg_speed_mps")
    if speed is not None and easy_speed is not None and speed <= easy_speed:
        return "ef", "Pas de FC : allure ≤ allure habituelle"
    return "other", "Pas assez d'informations"


def classify_all(activities: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Return a frame (id, session_type_auto, classification_reason)."""
    if activities.empty:
        return pd.DataFrame(columns=["id", "session_type_auto", "classification_reason"])
    hr_max = settings.hr_max or estimate_hr_max(activities)
    speeds = activities["avg_speed_mps"].dropna()
    easy_speed = float(speeds.median() * 1.02) if len(speeds) else None
    rows = []
    for row in activities.to_dict("records"):
        code, reason = classify(row, settings, hr_max, easy_speed)
        rows.append({"id": row["id"], "session_type_auto": code, "classification_reason": reason})
    return pd.DataFrame(rows)
