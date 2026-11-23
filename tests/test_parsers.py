"""F01 — file parsers and format detection."""

import gzip
import io
import zipfile

from fit_tool.profile.profile_type import SubSport

from cadence_tracker.ingest.files import detect_format, iter_raw_bytes, parse_raw
from cadence_tracker.ingest.fit import parse_fit
from cadence_tracker.ingest.xml_formats import parse_gpx, parse_tcx
from cadence_tracker.units import cadence_to_spm
from tests.helpers import START, build_fit, build_gpx, build_tcx


def test_fit_parsing_reads_channels_and_metadata():
    [activity] = parse_fit(build_fit(seconds=300, strides=86.5, sub_sport=SubSport.TRAIL))
    s = activity.samples
    assert activity.sport == "running" and activity.sub_sport == "trail"
    assert activity.start_time_utc == START
    assert activity.utc_offset_s == 7200
    assert len(s) == 300 and s["t_s"].iloc[-1] == 299
    assert abs(s["cadence_raw"].median() - 86.5) < 0.01  # strides + fractional part
    # The FIT file contains GPS positions, but they are never read (ADR 0004).
    assert not {"lat", "lon"} & set(s.columns)
    assert s["speed_mps"].median() == 3.0
    assert activity.cadence_unit == "strides"


def test_cadence_unit_normalisation():
    import pandas as pd

    strides = pd.Series([85.0, 86.0, 0.0])
    assert cadence_to_spm(strides, "strides").tolist() == [170.0, 172.0, 0.0]
    # Already in steps although declared as strides: not doubled.
    assert cadence_to_spm(pd.Series([170.0, 172.0]), "strides").tolist() == [170.0, 172.0]
    assert cadence_to_spm(pd.Series([88.0]), "unknown").tolist() == [176.0]
    assert cadence_to_spm(pd.Series([176.0]), "unknown").tolist() == [176.0]


def test_gpx_with_garmin_extensions():
    [activity] = parse_gpx(build_gpx(seconds=600))
    s = activity.samples
    assert activity.sport == "running" and activity.name == "Sortie test"
    assert s["heart_rate"].iloc[0] == 140 and s["cadence_raw"].iloc[0] == 85
    assert s["distance_m"].iloc[-1] > 1700  # derived from GPS, in memory only
    assert not {"lat", "lon", "_lat", "_lon"} & set(s.columns)


def test_tcx_parsing():
    [activity] = parse_tcx(build_tcx(seconds=300))
    s = activity.samples
    assert s["cadence_raw"].iloc[0] == 86 and s["speed_mps"].iloc[0] == 3.0 and s["heart_rate"].iloc[0] == 141
    assert activity.laps is not None and activity.laps["intensity"].iloc[0] == "active"


def test_archives_are_expanded_recursively():
    fit = build_fit(seconds=120)
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("run.fit", fit)
        z.writestr("notes.txt", "ignored")
    outer = io.BytesIO()
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("export/part1.zip", inner.getvalue())
        z.writestr("activities/123.gpx.gz", gzip.compress(build_gpx(seconds=120)))
    raws = list(iter_raw_bytes("export.zip", outer.getvalue()))
    assert sorted(r.fmt for r in raws) == ["fit", "gpx"]
    assert all(parse_raw(r) for r in raws)


def test_detect_format_by_content():
    assert detect_format("noname", build_fit(seconds=10)) == "fit"
    assert detect_format("x.xml", build_tcx(seconds=10)) == "tcx"
    assert detect_format("x", build_gpx(seconds=10)) == "gpx"
    assert detect_format("x.txt", b"hello") is None
