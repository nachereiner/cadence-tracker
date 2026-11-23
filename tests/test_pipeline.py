"""F02 — storage, deduplication, idempotent re-imports, annotations preserved."""

from fit_tool.profile.profile_type import Sport

from cadence_tracker.ingest.files import iter_raw_bytes
from cadence_tracker.ingest.pipeline import import_many, import_raw, recompute_all
from cadence_tracker.storage import repository as repo
from tests.helpers import build_fit, build_gpx


def _import(conn, name, data):
    return import_many(conn, iter_raw_bytes(name, data))


def test_import_then_reimport_is_idempotent(conn):
    data = build_fit()
    [first] = _import(conn, "run.fit", data)
    assert first.status == "imported"
    [again] = _import(conn, "copy-of-run.fit", data)
    assert again.status == "already_imported"
    assert repo.counts(conn)["activities"] == 1
    df = repo.load_activities(conn)
    assert abs(df["cadence_median"].iloc[0] - 170) < 0.5
    assert df["session_type_auto"].iloc[0] is not None


def test_same_run_from_another_source_is_a_duplicate(conn):
    _import(conn, "run.fit", build_fit())
    [dup] = _import(conn, "run.gpx", build_gpx())  # same start time, same run
    assert dup.status == "duplicate"
    assert repo.counts(conn)["activities"] == 1


def test_richer_version_replaces_data_but_keeps_annotations(conn):
    [first] = _import(conn, "run_no_cadence.fit", build_fit(with_cadence=False))
    repo.update_annotations(conn, first.activity_id, notes="chaussures neuves", session_type_manual="long")
    [second] = _import(conn, "run.fit", build_fit(strides=88))
    assert second.status == "updated" and second.activity_id == first.activity_id
    df = repo.load_activities(conn)
    assert len(df) == 1
    assert df["notes"].iloc[0] == "chaussures neuves" and df["session_type"].iloc[0] == "long"
    assert abs(df["cadence_median"].iloc[0] - 176) < 0.5


def test_non_running_activities_are_skipped(conn):
    [res] = _import(conn, "bike.fit", build_fit(sport=Sport.CYCLING))
    assert res.status == "skipped"
    assert repo.counts(conn)["activities"] == 0


def test_same_source_id_is_not_imported_twice(conn):
    [raw] = list(iter_raw_bytes("a.fit", build_fit()))
    import_raw(conn, raw, source="garmin_api", source_id="42")
    [raw2] = list(iter_raw_bytes("b.fit", build_fit(strides=80)))  # different bytes, same Garmin id
    [res] = import_raw(conn, raw2, source="garmin_api", source_id="42")
    assert res.status == "duplicate"
    assert repo.source_id_seen(conn, "garmin_api", "42")


def test_recompute_after_settings_change(conn):
    _import(conn, "run.fit", build_fit(speed=1.7))  # slow jog: below the default running speed
    before = repo.load_activities(conn)["running_s"].iloc[0]
    settings = repo.load_settings(conn)
    settings.min_run_speed_mps = 1.5
    repo.save_settings(conn, settings)
    recompute_all(conn)
    after = repo.load_activities(conn)["running_s"].iloc[0]
    assert before < 60 and after > 1000


def test_source_category_overrides_file_type_and_skips_are_logged(conn):
    [raw] = list(iter_raw_bytes("hike.fit", build_fit(sport=Sport.HIKING)))
    [skipped] = import_raw(conn, raw, source="fit_file")
    assert skipped.status == "skipped"
    assert "skipped" in repo.recent_imports(conn)["status"].tolist()
    [raw2] = list(iter_raw_bytes("hike2.fit", build_fit(sport=Sport.HIKING, strides=84)))
    [res] = import_raw(conn, raw2, source="garmin_api", source_id="7", sport="running", sub_sport="trail")
    assert res.status == "imported"
    assert repo.load_activities(conn)["sub_sport"].iloc[0] == "trail"
