"""TCX and GPX parsers (fallback formats: Strava/Garmin exports, other apps).

Coordinates are used only to compute a missing distance and are dropped right
away: no position ever leaves this module (docs/adr/0004-aucune-donnee-gps.md).

Both are XML. Namespaces vary between exporters, so lookups use the `{*}`
wildcard. Cadence unit is declared 'unknown' and resolved by
`units.cadence_to_spm` from the values themselves.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from cadence_tracker.models import (
    LAP_COLUMNS,
    SAMPLE_COLUMNS,
    ParsedActivity,
    normalize_sport,
    normalize_sub_sport,
)
from cadence_tracker.units import haversine_m


def _parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    text = text.strip().replace("Z", "+00:00")
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _float(element: ET.Element | None, path: str) -> float | None:
    if element is None:
        return None
    node = element.find(path)
    if node is None or node.text is None:
        return None
    try:
        return float(node.text.strip())
    except ValueError:
        return None


def _finalize(points: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(points)
    df = df.dropna(subset=["ts"]).sort_values("ts")
    start = df["ts"].iloc[0]
    df["t_s"] = (df["ts"] - start).dt.total_seconds().round().astype(int)
    df = df.drop(columns=["ts"]).drop_duplicates("t_s", keep="last")
    return df.reindex(columns=SAMPLE_COLUMNS).reset_index(drop=True)


def _gps_distance(points: list[dict]) -> None:
    """Fill a missing distance from coordinates, then forget the coordinates.

    Coordinates live only in this function's local variables: the returned
    samples never contain a position (docs/adr/0004-aucune-donnee-gps.md).
    """
    has_distance = any(p["distance_m"] is not None for p in points)
    coords = [(p.pop("_lat", None), p.pop("_lon", None)) for p in points]
    if has_distance or not any(lat is not None for lat, _ in coords):
        return
    lat = pd.Series([c[0] for c in coords], dtype=float).ffill()
    lon = pd.Series([c[1] for c in coords], dtype=float).ffill()
    step = haversine_m(lat.shift(), lon.shift(), lat, lon)
    total = np.nancumsum(np.nan_to_num(step, nan=0.0))
    for point, distance in zip(points, total, strict=True):
        point["distance_m"] = float(distance)
    del lat, lon, coords


def parse_tcx(data: bytes, *, source: str = "tcx_file", source_id: str | None = None) -> list[ParsedActivity]:
    root = ET.fromstring(data)
    activities: list[ParsedActivity] = []
    for act in root.findall(".//{*}Activity"):
        points: list[dict] = []
        laps: list[dict] = []
        for lap in act.findall("{*}Lap"):
            lap_start = _parse_time(lap.get("StartTime"))
            laps.append(
                {
                    "start": lap_start,
                    "duration_s": _float(lap, "{*}TotalTimeSeconds"),
                    "distance_m": _float(lap, "{*}DistanceMeters"),
                    "heart_rate": _float(lap, "{*}AverageHeartRateBpm/{*}Value"),
                    "intensity": (lap.findtext("{*}Intensity") or "").lower() or None,
                }
            )
            for tp in lap.findall(".//{*}Trackpoint"):
                ext = tp.find("{*}Extensions")
                cadence = _float(ext, ".//{*}RunCadence") if ext is not None else None
                if cadence is None:
                    cadence = _float(tp, "{*}Cadence")
                points.append(
                    {
                        "ts": _parse_time(tp.findtext("{*}Time")),
                        "distance_m": _float(tp, "{*}DistanceMeters"),
                        "speed_mps": _float(ext, ".//{*}Speed") if ext is not None else None,
                        "cadence_raw": cadence,
                        "heart_rate": _float(tp, "{*}HeartRateBpm/{*}Value"),
                        "altitude_m": _float(tp, "{*}AltitudeMeters"),
                        "_lat": _float(tp, "{*}Position/{*}LatitudeDegrees"),
                        "_lon": _float(tp, "{*}Position/{*}LongitudeDegrees"),
                    }
                )
        points = [p for p in points if p["ts"] is not None]
        if not points:
            continue
        start = min(p["ts"] for p in points)
        _gps_distance(points)
        samples = _finalize(points)
        lap_df = pd.DataFrame(
            [
                {
                    "lap_index": i,
                    "start_s": (lap["start"] - start).total_seconds() if lap["start"] else None,
                    "duration_s": lap["duration_s"],
                    "distance_m": lap["distance_m"],
                    "speed_mps": (lap["distance_m"] / lap["duration_s"])
                    if lap["distance_m"] and lap["duration_s"]
                    else None,
                    "heart_rate": lap["heart_rate"],
                    "cadence_spm": None,
                    "intensity": {"resting": "rest"}.get(lap["intensity"], lap["intensity"]),
                }
                for i, lap in enumerate(laps)
            ],
            columns=LAP_COLUMNS,
        )
        sport_attr = act.get("Sport") or ""
        notes = act.findtext("{*}Notes")
        creator = act.findtext("{*}Creator/{*}Name")
        activities.append(
            ParsedActivity(
                source=source,
                source_id=source_id,
                start_time_utc=start,
                sport=normalize_sport(sport_attr) if sport_attr.lower() != "other" else "running",
                sub_sport=normalize_sub_sport(notes),
                cadence_unit="unknown",
                samples=samples,
                laps=lap_df if not lap_df.empty else None,
                name=notes.strip()[:120] if notes else None,
                device=creator,
                summary={
                    "distance_m": sum(lap["distance_m"] or 0 for lap in laps) or None,
                    "timer_s": sum(lap["duration_s"] or 0 for lap in laps) or None,
                },
            )
        )
    return activities


def parse_gpx(data: bytes, *, source: str = "gpx_file", source_id: str | None = None) -> list[ParsedActivity]:
    root = ET.fromstring(data)
    activities: list[ParsedActivity] = []
    for trk in root.findall(".//{*}trk"):
        points: list[dict] = []
        for pt in trk.findall(".//{*}trkpt"):
            ext = pt.find("{*}extensions")
            hr = cad = None
            if ext is not None:
                hr = _float(ext, ".//{*}hr")
                cad = _float(ext, ".//{*}cad")
                if cad is None:
                    cad = _float(ext, ".//{*}cadence")
            points.append(
                {
                    "ts": _parse_time(pt.findtext("{*}time")),
                    "distance_m": None,
                    "speed_mps": None,
                    "cadence_raw": cad,
                    "heart_rate": hr,
                    "altitude_m": _float(pt, "{*}ele"),
                    "_lat": float(pt.get("lat")) if pt.get("lat") else None,
                    "_lon": float(pt.get("lon")) if pt.get("lon") else None,
                }
            )
        points = [p for p in points if p["ts"] is not None]
        if not points:
            continue
        start = min(p["ts"] for p in points)
        _gps_distance(points)
        samples = _finalize(points)
        trk_type = (trk.findtext("{*}type") or "").strip()
        name = (trk.findtext("{*}name") or "").strip() or None
        activities.append(
            ParsedActivity(
                source=source,
                source_id=source_id,
                start_time_utc=start,
                # A GPX without <type> imported into a running tracker is assumed to be a run.
                sport=normalize_sport(trk_type) if trk_type else "running",
                sub_sport=normalize_sub_sport(f"{trk_type} {name or ''}"),
                cadence_unit="unknown",
                samples=samples,
                name=name,
            )
        )
    return activities
