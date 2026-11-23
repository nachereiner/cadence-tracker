"""FIT file parser (Garmin and most watches; also what the Garmin API returns).

Uses `fitdecode`. Running cadence in FIT `record` messages is in strides per
minute (`cadence`, plus optional `fractional_cadence`); it is converted to steps
per minute later by `units.cadence_to_spm`.

A FIT file may contain several sessions (multisport). One `ParsedActivity` is
produced per session; the pipeline later ignores non-running ones.

GPS positions are never read (docs/adr/0004-aucune-donnee-gps.md).
"""

from __future__ import annotations

import io
import logging
from datetime import UTC, datetime, timedelta

import fitdecode
import pandas as pd

from cadence_tracker.models import (
    LAP_COLUMNS,
    SAMPLE_COLUMNS,
    ParsedActivity,
    normalize_sport,
    normalize_sub_sport,
)

log = logging.getLogger(__name__)


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _val(frame: fitdecode.FitDataMessage, *names: str):
    """First non-null value among field names (e.g. enhanced_speed, speed)."""
    for name in names:
        if frame.has_field(name):
            value = frame.get_value(name, fallback=None)
            if value is not None:
                return value
    return None


def parse_fit(data: bytes, *, source: str = "fit_file", source_id: str | None = None) -> list[ParsedActivity]:
    records: list[dict] = []
    sessions: list[dict] = []
    laps: list[dict] = []
    device: str | None = None
    workout_name: str | None = None
    utc_offset_s: int | None = None
    sport_msg: dict = {}

    reader = fitdecode.FitReader(
        io.BytesIO(data),
        check_crc=fitdecode.CrcCheck.WARN,
        error_handling=fitdecode.ErrorHandling.WARN,
    )
    with reader as fit:
        for frame in fit:
            if not isinstance(frame, fitdecode.FitDataMessage):
                continue
            name = frame.name
            if name == "record":
                ts = _utc(_val(frame, "timestamp"))
                if ts is None:
                    continue
                cadence = _val(frame, "cadence")
                fractional = _val(frame, "fractional_cadence")
                if cadence is not None and fractional is not None:
                    cadence = float(cadence) + float(fractional)
                records.append(
                    {
                        "ts": ts,
                        "distance_m": _val(frame, "distance"),
                        "speed_mps": _val(frame, "enhanced_speed", "speed"),
                        "cadence_raw": cadence,
                        "heart_rate": _val(frame, "heart_rate"),
                        "altitude_m": _val(frame, "enhanced_altitude", "altitude"),
                        # Positions are deliberately never read (FIT files carry their own distance).
                    }
                )
            elif name == "session":
                sessions.append(
                    {
                        "start": _utc(_val(frame, "start_time")),
                        "sport": _val(frame, "sport"),
                        "sub_sport": _val(frame, "sub_sport"),
                        "elapsed_s": _val(frame, "total_elapsed_time"),
                        "timer_s": _val(frame, "total_timer_time"),
                        "distance_m": _val(frame, "total_distance"),
                        "ascent_m": _val(frame, "total_ascent"),
                        "descent_m": _val(frame, "total_descent"),
                        "avg_hr": _val(frame, "avg_heart_rate"),
                        "max_hr": _val(frame, "max_heart_rate"),
                    }
                )
            elif name == "lap":
                cadence = _val(frame, "avg_running_cadence", "avg_cadence")
                fractional = _val(frame, "avg_fractional_cadence")
                if cadence is not None and fractional is not None:
                    cadence = float(cadence) + float(fractional)
                laps.append(
                    {
                        "start": _utc(_val(frame, "start_time")),
                        "duration_s": _val(frame, "total_timer_time", "total_elapsed_time"),
                        "distance_m": _val(frame, "total_distance"),
                        "speed_mps": _val(frame, "enhanced_avg_speed", "avg_speed"),
                        "heart_rate": _val(frame, "avg_heart_rate"),
                        "cadence_raw": cadence,
                        "intensity": _val(frame, "intensity"),
                    }
                )
            elif name == "activity":
                ts = _val(frame, "timestamp")
                local = _val(frame, "local_timestamp")
                if ts is not None and local is not None:
                    if isinstance(local, int):  # raw FIT epoch seconds
                        local = datetime(1989, 12, 31, tzinfo=UTC) + timedelta(seconds=local)
                    delta = (_utc(local) - _utc(ts)).total_seconds()
                    utc_offset_s = int(round(delta / 900.0)) * 900  # nearest 15 min
            elif name == "file_id" and device is None:
                manufacturer = _val(frame, "manufacturer")
                product = _val(frame, "garmin_product", "product_name", "product")
                device = " ".join(str(x) for x in (manufacturer, product) if x not in (None, 0))
            elif name == "workout":
                workout_name = _val(frame, "wkt_name") or workout_name
            elif name == "sport":
                sport_msg = {"sport": _val(frame, "sport"), "sub_sport": _val(frame, "sub_sport")}

    if not records:
        return []

    rec = pd.DataFrame(records).sort_values("ts")
    if not sessions:
        # Truncated files may miss the session message: fall back to the sport message.
        sessions = [{"start": rec["ts"].iloc[0], **sport_msg}]

    activities: list[ParsedActivity] = []
    for index, session in enumerate(sessions):
        start = session.get("start") or rec["ts"].iloc[0]
        end = start + timedelta(seconds=float(session.get("elapsed_s") or 0)) if session.get("elapsed_s") else None
        window = rec[rec["ts"] >= start - timedelta(seconds=1)]
        if end is not None and len(sessions) > 1:
            window = window[window["ts"] <= end + timedelta(seconds=1)]
        if window.empty:
            continue
        samples = window.copy()
        samples["t_s"] = (samples["ts"] - start).dt.total_seconds().round().astype(int)
        samples = samples.drop(columns=["ts"]).drop_duplicates("t_s", keep="last")
        samples = samples.reindex(columns=SAMPLE_COLUMNS).reset_index(drop=True)

        session_laps = _laps_frame([lap for lap in laps if lap["start"] is not None], start, end)
        sport = normalize_sport(str(session.get("sport") or sport_msg.get("sport") or ""))
        sub = normalize_sub_sport(str(session.get("sub_sport") or sport_msg.get("sub_sport") or ""))
        sid = source_id if len(sessions) == 1 or source_id is None else f"{source_id}#{index}"
        activities.append(
            ParsedActivity(
                source=source,
                source_id=sid,
                start_time_utc=start,
                sport=sport,
                sub_sport=sub,
                cadence_unit="strides",
                samples=samples,
                laps=session_laps,
                utc_offset_s=utc_offset_s,
                workout_name=workout_name,
                device=device or None,
                summary={
                    k: session.get(k)
                    for k in ("elapsed_s", "timer_s", "distance_m", "ascent_m", "descent_m", "avg_hr", "max_hr")
                },
            )
        )
    return activities


def _laps_frame(laps: list[dict], start: datetime, end: datetime | None) -> pd.DataFrame | None:
    rows = []
    for lap in laps:
        if lap["start"] < start - timedelta(seconds=1):
            continue
        if end is not None and lap["start"] > end:
            continue
        rows.append(
            {
                "lap_index": len(rows),
                "start_s": (lap["start"] - start).total_seconds(),
                "duration_s": lap["duration_s"],
                "distance_m": lap["distance_m"],
                "speed_mps": lap["speed_mps"],
                "heart_rate": lap["heart_rate"],
                # Lap cadence is in strides/min like records: doubled when plausible.
                "cadence_spm": (
                    lap["cadence_raw"] * 2 if lap["cadence_raw"] and lap["cadence_raw"] < 130 else lap["cadence_raw"]
                ),
                "intensity": str(lap["intensity"]) if lap["intensity"] is not None else None,
            }
        )
    return pd.DataFrame(rows, columns=LAP_COLUMNS) if rows else None
