"""GPS data policy (docs/adr/0004-aucune-donnee-gps.md).

The application never reads, displays or exports GPS positions:

* parsers never return positions (FIT positions are not even read);
* new samples are stored without position;
* every query lists its columns explicitly (`ALLOWED_*` below), so legacy GPS
  columns kept at rest in an old database are never loaded by the app.

`purge_gps()` is the opt-in, irreversible erasure of legacy GPS data
(`ctrack purge-gps`): it drops the columns and rewrites the database file.
"""

from __future__ import annotations

import sqlite3

# Columns the application is allowed to read.
ALLOWED_SAMPLE_COLUMNS = ["activity_id", "t_s", "distance_m", "speed_mps", "cadence_spm", "heart_rate", "altitude_m"]
GPS_COLUMNS = {"samples": ["lat", "lon"], "activity_metrics": ["start_lat", "start_lon", "has_gps"]}


def gps_columns_present(conn: sqlite3.Connection) -> dict[str, list[str]]:
    found = {}
    for table, columns in GPS_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        present = [c for c in columns if c in existing]
        if present:
            found[table] = present
    return found


def purge_gps(conn: sqlite3.Connection) -> dict[str, list[str]]:
    """Irreversibly erase legacy GPS data: drop the columns, then rewrite the file."""
    removed = gps_columns_present(conn)
    with conn:
        for table, columns in removed.items():
            for column in columns:
                conn.execute(f"ALTER TABLE {table} DROP COLUMN {column}")
        conn.execute("DROP TABLE IF EXISTS raw_files")  # paths of the archived original files
    conn.execute("VACUUM")  # deleted values must not survive in free pages
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return removed
