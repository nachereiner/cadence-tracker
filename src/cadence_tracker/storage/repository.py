"""Data access functions. All SQL lives here; callers get pandas DataFrames.

Keeping SQL in one module makes the schema easy to evolve and lets the UI and
the analysis code stay storage-agnostic.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from cadence_tracker.config import Settings
from cadence_tracker.privacy import ALLOWED_SAMPLE_COLUMNS

# Metrics the application reads (explicit list: legacy GPS columns are never loaded).
METRIC_COLUMNS = [
    "metrics_version",
    "computed_at",
    "elapsed_s",
    "moving_s",
    "running_s",
    "distance_m",
    "avg_speed_mps",
    "cadence_mean",
    "cadence_median",
    "cadence_p10",
    "cadence_p90",
    "cadence_std",
    "hr_mean",
    "hr_peak",
    "ascent_m",
    "descent_m",
    "ascent_per_km",
    "stride_m",
    "efficiency",
    "decoupling_pct",
    "cadence_first_half",
    "cadence_second_half",
    "cadence_drift_spm_h",
    "cadence_fatigue_spm_h",
    "speed_cv",
    "fast_blocks",
    "n_active_laps",
    "n_rest_laps",
    "active_lap_mean_s",
    "has_hr",
    "has_cadence",
    "has_altitude",
    "session_type_auto",
    "classification_reason",
]
ANNOTATION_FIELDS = {"session_type_manual", "excluded", "notes", "name"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


# --------------------------------------------------------------------- settings
def load_settings(conn: sqlite3.Connection) -> Settings:
    row = conn.execute("SELECT value FROM settings WHERE key = 'analysis'").fetchone()
    return Settings.from_dict(json.loads(row["value"])) if row else Settings()


def save_settings(conn: sqlite3.Connection, settings: Settings) -> None:
    with conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES('analysis', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (json.dumps(settings.to_dict()),),
        )


def get_flag(conn: sqlite3.Connection, key: str) -> Any:
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return json.loads(row["value"]) if row else None


def set_flag(conn: sqlite3.Connection, key: str, value: Any) -> None:
    with conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, json.dumps(value)),
        )


# ------------------------------------------------------------------- seen files
def raw_file_known(conn: sqlite3.Connection, sha256: str) -> bool:
    return conn.execute("SELECT 1 FROM seen_files WHERE sha256 = ?", (sha256,)).fetchone() is not None


def record_seen_file(conn, *, sha256, original_name, fmt, size_bytes, source, source_id) -> None:
    """Remember that a file was imported (hash only: the file itself is never kept)."""
    conn.execute(
        "INSERT OR IGNORE INTO seen_files(sha256, original_name, fmt, size_bytes, source, source_id, first_seen_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (sha256, original_name, fmt, size_bytes, source, source_id, now_iso()),
    )


# ------------------------------------------------------------------- activities
def find_by_source(conn, source: str, source_id: str | None) -> sqlite3.Row | None:
    if source_id is None:
        return None
    return conn.execute("SELECT * FROM activities WHERE source = ? AND source_id = ?", (source, source_id)).fetchone()


def source_id_seen(conn, source: str, source_id: str) -> bool:
    """True if this source id was already imported (as an activity or a seen file)."""
    if find_by_source(conn, source, source_id) is not None:
        return True
    row = conn.execute("SELECT 1 FROM seen_files WHERE source = ? AND source_id = ?", (source, source_id)).fetchone()
    return row is not None


def find_overlapping(conn, start_utc: datetime, elapsed_s: float, tolerance_s: int = 120) -> list[sqlite3.Row]:
    """Activities starting within ±tolerance of `start_utc` (same run, other source)."""
    lo = (start_utc - pd.Timedelta(seconds=tolerance_s)).isoformat()
    hi = (start_utc + pd.Timedelta(seconds=tolerance_s)).isoformat()
    rows = conn.execute(
        "SELECT a.*, m.has_cadence, m.has_hr, "
        "(SELECT COUNT(*) FROM samples s WHERE s.activity_id = a.id) AS n_samples "
        "FROM activities a LEFT JOIN activity_metrics m ON m.activity_id = a.id "
        "WHERE a.start_time_utc BETWEEN ? AND ?",
        (lo, hi),
    ).fetchall()
    out = []
    for row in rows:
        other = row["elapsed_s"] or 0
        if not elapsed_s or not other or abs(other - elapsed_s) <= 0.15 * max(other, elapsed_s) + 60:
            out.append(row)
    return out


def insert_activity(conn, values: dict[str, Any]) -> int:
    values = {**values, "imported_at": now_iso(), "updated_at": now_iso()}
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    cur = conn.execute(f"INSERT INTO activities({cols}) VALUES ({marks})", list(values.values()))
    return int(cur.lastrowid)


def update_activity_data(conn, activity_id: int, values: dict[str, Any]) -> None:
    """Replace source-derived columns (never the user annotations)."""
    values = {k: v for k, v in values.items() if k not in ANNOTATION_FIELDS - {"name"}}
    values["updated_at"] = now_iso()
    sets = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE activities SET {sets} WHERE id = ?", [*values.values(), activity_id])


def update_annotations(conn, activity_id: int, **fields: Any) -> None:
    unknown = set(fields) - ANNOTATION_FIELDS
    if unknown:
        raise ValueError(f"Not annotation fields: {unknown}")
    if not fields:
        return
    fields["updated_at"] = now_iso()
    sets = ", ".join(f"{k} = ?" for k in fields)
    with conn:
        conn.execute(f"UPDATE activities SET {sets} WHERE id = ?", [*fields.values(), activity_id])


def delete_activity(conn, activity_id: int) -> None:
    with conn:
        conn.execute("DELETE FROM activities WHERE id = ?", (activity_id,))


def replace_samples(conn, activity_id: int, samples: pd.DataFrame) -> None:
    cols = ["t_s", "distance_m", "speed_mps", "cadence_spm", "heart_rate", "altitude_m"]  # never any position
    df = samples.reindex(columns=cols)
    df = df.astype(object).where(df.notna(), None)
    conn.execute("DELETE FROM samples WHERE activity_id = ?", (activity_id,))
    conn.executemany(
        f"INSERT INTO samples(activity_id, {', '.join(cols)}) VALUES (?{', ?' * len(cols)})",
        [(activity_id, *row) for row in df.itertuples(index=False, name=None)],
    )


def _replace_table(conn, table: str, activity_id: int, df: pd.DataFrame | None, cols: list[str]) -> None:
    conn.execute(f"DELETE FROM {table} WHERE activity_id = ?", (activity_id,))
    if df is None or df.empty:
        return
    data = df.reindex(columns=cols)
    data = data.astype(object).where(data.notna(), None)
    conn.executemany(
        f"INSERT INTO {table}(activity_id, {', '.join(cols)}) VALUES (?{', ?' * len(cols)})",
        [(activity_id, *row) for row in data.itertuples(index=False, name=None)],
    )


def replace_laps(conn, activity_id: int, laps: pd.DataFrame | None) -> None:
    cols = ["lap_index", "start_s", "duration_s", "distance_m", "speed_mps", "heart_rate", "cadence_spm", "intensity"]
    _replace_table(conn, "laps", activity_id, laps, cols)


def replace_splits(conn, activity_id: int, splits: pd.DataFrame | None) -> None:
    cols = [
        "km",
        "distance_m",
        "duration_s",
        "speed_mps",
        "cadence_spm",
        "heart_rate",
        "elev_gain_m",
        "grade_pct",
        "elapsed_end_s",
    ]
    _replace_table(conn, "splits", activity_id, splits, cols)


def upsert_metrics(conn, activity_id: int, metrics: dict[str, Any]) -> None:
    metrics = {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in metrics.items()}
    metrics = {"activity_id": activity_id, **metrics, "computed_at": now_iso()}
    cols = ", ".join(metrics)
    marks = ", ".join("?" for _ in metrics)
    updates = ", ".join(f"{k} = excluded.{k}" for k in metrics if k != "activity_id")
    conn.execute(
        f"INSERT INTO activity_metrics({cols}) VALUES ({marks}) ON CONFLICT(activity_id) DO UPDATE SET {updates}",
        list(metrics.values()),
    )


def set_classification(conn, activity_id: int, session_type: str, reason: str) -> None:
    conn.execute(
        "UPDATE activity_metrics SET session_type_auto = ?, classification_reason = ? WHERE activity_id = ?",
        (session_type, reason, activity_id),
    )


# ------------------------------------------------------------------------ reads
def load_activities(conn, include_excluded: bool = True) -> pd.DataFrame:
    """One row per activity: identity, annotations and computed metrics."""
    sql = (
        "SELECT a.id, a.source, a.source_id, a.name, a.workout_name, a.device, a.sport, a.sub_sport, "
        "a.start_time_utc, a.utc_offset_s, a.session_type_manual, a.excluded, a.notes, "
        f"{', '.join('m.' + c for c in METRIC_COLUMNS)} FROM activities a LEFT JOIN activity_metrics m ON m.activity_id = a.id"
    )
    if not include_excluded:
        sql += " WHERE a.excluded = 0"
    df = pd.read_sql_query(sql + " ORDER BY a.start_time_utc", conn)
    if df.empty:
        return df
    df["start_utc"] = pd.to_datetime(df["start_time_utc"], utc=True, format="ISO8601")
    offset = pd.to_timedelta(df["utc_offset_s"].fillna(0), unit="s")
    # Local wall-clock time, naive (used for display and weekly/monthly grouping).
    df["start_local"] = (df["start_utc"] + offset).dt.tz_localize(None)
    df["date"] = df["start_local"].dt.normalize()
    df["session_type"] = df["session_type_manual"].fillna(df["session_type_auto"]).fillna("other")
    df["excluded"] = df["excluded"].astype(bool)
    return df


def load_samples(conn, activity_id: int) -> pd.DataFrame:
    """Samples of one run: explicit columns only, never a GPS position (privacy.py)."""
    cols = ", ".join(ALLOWED_SAMPLE_COLUMNS)
    return pd.read_sql_query(
        f"SELECT {cols} FROM samples WHERE activity_id = ? ORDER BY t_s", conn, params=(activity_id,)
    )


def load_laps(conn, activity_id: int) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM laps WHERE activity_id = ? ORDER BY lap_index", conn, params=(activity_id,))


def load_splits(conn, activity_ids: list[int] | None = None) -> pd.DataFrame:
    sql = "SELECT * FROM splits"
    params: tuple = ()
    if activity_ids is not None:
        if not activity_ids:
            return pd.DataFrame(columns=["activity_id", "km"])
        sql += f" WHERE activity_id IN ({', '.join('?' for _ in activity_ids)})"
        params = tuple(int(i) for i in activity_ids)
    return pd.read_sql_query(sql + " ORDER BY activity_id, km", conn, params=params)


def activity_ids(conn) -> list[int]:
    return [r[0] for r in conn.execute("SELECT id FROM activities ORDER BY start_time_utc")]


def get_activity_row(conn, activity_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM activities WHERE id = ?", (activity_id,)).fetchone()


# ----------------------------------------------------------------- import / sync
def log_import(conn, origin: str, status: str, activity_id: int | None = None, message: str | None = None) -> None:
    conn.execute(
        "INSERT INTO import_log(at, origin, status, activity_id, message) VALUES (?,?,?,?,?)",
        (now_iso(), origin, status, activity_id, message),
    )


def recent_imports(conn, limit: int = 100) -> pd.DataFrame:
    return pd.read_sql_query("SELECT * FROM import_log ORDER BY id DESC LIMIT ?", conn, params=(limit,))


def get_sync_state(conn, source: str) -> dict[str, Any]:
    row = conn.execute("SELECT * FROM sync_state WHERE source = ?", (source,)).fetchone()
    return dict(row) if row else {}


def set_sync_state(conn, source: str, last_activity_start: str | None, details: dict | None = None) -> None:
    with conn:
        conn.execute(
            "INSERT INTO sync_state(source, last_sync_at, last_activity_start, details) VALUES (?,?,?,?) "
            "ON CONFLICT(source) DO UPDATE SET last_sync_at = excluded.last_sync_at, "
            "last_activity_start = COALESCE(excluded.last_activity_start, sync_state.last_activity_start), "
            "details = excluded.details",
            (source, now_iso(), last_activity_start, json.dumps(details or {})),
        )


def counts(conn) -> dict[str, int]:
    return {
        "activities": conn.execute("SELECT COUNT(*) FROM activities").fetchone()[0],
        "samples": conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0],
        "seen_files": conn.execute("SELECT COUNT(*) FROM seen_files").fetchone()[0],
    }
