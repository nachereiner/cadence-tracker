"""ADR 0004 / F08 — GPS data is never stored by new imports, never read by the app,
never exported; legacy GPS stays at rest unless the user erases it on purpose."""

import datetime as dt
import sqlite3
import struct

from cadence_tracker import config
from cadence_tracker.backup import backup
from cadence_tracker.ingest.files import iter_raw_bytes
from cadence_tracker.ingest.pipeline import import_many
from cadence_tracker.privacy import gps_columns_present, purge_gps
from cadence_tracker.storage import db
from cadence_tracker.storage import repository as repo
from tests.helpers import build_fit, build_gpx

GPS = {"lat", "lon", "start_lat", "start_lon", "has_gps"}
LAT, LON = 45.1234567, 5.7654321


def _legacy_db(path):
    """A v2 database (before ADR 0004) holding GPS positions."""
    legacy = sqlite3.connect(path)
    for version, sql in db._migrations():
        if version <= 2:
            legacy.executescript(sql)
    legacy.execute("PRAGMA user_version = 2")
    legacy.execute(
        "INSERT INTO activities(id, source, sport, start_time_utc, imported_at, updated_at) "
        "VALUES (1, 'test', 'running', '2026-01-01T00:00:00+00:00', 'x', 'x')"
    )
    legacy.execute(
        "INSERT INTO activity_metrics(activity_id, metrics_version, computed_at, start_lat, start_lon) VALUES (1, 2, 'x', ?, ?)",
        (LAT, LON),
    )
    legacy.executemany(
        "INSERT INTO samples(activity_id, t_s, lat, lon, cadence_spm) VALUES (1, ?, ?, ?, 170)",
        [(t, LAT, LON) for t in range(2000)],
    )
    legacy.commit()
    legacy.close()


def test_new_imports_store_no_position_and_no_file(conn, data_dir):
    results = import_many(conn, iter_raw_bytes("run.fit", build_fit()))
    results += import_many(conn, iter_raw_bytes("run.gpx", build_gpx(start=dt.datetime(2026, 9, 3, 7, tzinfo=dt.UTC))))
    assert {r.status for r in results} == {"imported"}
    present = gps_columns_present(conn)
    for table, columns in present.items():  # legacy columns may exist, but stay empty
        for column in columns:
            assert conn.execute(f"SELECT COUNT({column}) FROM {table}").fetchone()[0] == 0, (table, column)
    # Only the database lives in the data folder: original files are never written.
    assert {p.name for p in data_dir.iterdir()} <= {"cadence.db", "cadence.db-wal", "cadence.db-shm"}
    assert conn.execute("SELECT MAX(distance_m) FROM samples").fetchone()[0] > 1000  # GPX distance still computed


def test_legacy_gps_is_kept_at_rest_but_never_read(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_db(path)
    conn = db.connect(path)  # migration 003 is non-destructive
    assert conn.execute("SELECT COUNT(lat) FROM samples").fetchone()[0] == 2000  # still at rest
    assert not GPS & set(repo.load_samples(conn, 1).columns)
    assert not GPS & set(repo.load_activities(conn).columns)


def test_purge_gps_erases_the_bytes_on_demand(tmp_path):
    path = tmp_path / "legacy.db"
    _legacy_db(path)
    marker_lat, marker_lon = struct.pack(">d", LAT), struct.pack(">d", LON)
    assert marker_lat in path.read_bytes()
    conn = db.connect(path)
    removed = purge_gps(conn)
    assert removed == {"samples": ["lat", "lon"], "activity_metrics": ["start_lat", "start_lon", "has_gps"]}
    assert conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0] == 2000  # cadence kept
    assert not GPS & set(repo.load_samples(conn, 1).columns)
    conn.close()
    for file in tmp_path.iterdir():
        raw = file.read_bytes()
        assert marker_lat not in raw and marker_lon not in raw, file.name
    # The app keeps working after the purge (explicit column lists).
    conn = db.connect(path)
    assert len(repo.load_activities(conn)) == 1


def test_backup_of_new_data_contains_no_gps(conn, data_dir):
    import_many(conn, iter_raw_bytes("run.fit", build_fit()))
    snapshot = sqlite3.connect(backup(config.db_path()))
    assert snapshot.execute("SELECT COUNT(*) FROM activities").fetchone()[0] == 1
    assert snapshot.execute("SELECT COUNT(lat) FROM samples").fetchone()[0] == 0


def test_no_export_entry_point():
    import importlib.util

    from cadence_tracker.cli import app

    assert importlib.util.find_spec("cadence_tracker.export") is None
    assert "export" not in {c.name for c in app.registered_commands}
