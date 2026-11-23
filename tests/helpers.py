"""Builders for synthetic activity files used by the tests."""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd
from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.activity_message import ActivityMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.messages.session_message import SessionMessage
from fit_tool.profile.profile_type import FileType, Manufacturer, Sport, SubSport

from cadence_tracker.models import SAMPLE_COLUMNS, ParsedActivity

START = dt.datetime(2026, 9, 1, 7, 0, tzinfo=dt.UTC)


def _ms(value: dt.datetime) -> int:
    return round(value.timestamp() * 1000)


def build_fit(
    *,
    start: dt.datetime = START,
    seconds: int = 1200,
    speed: float = 3.0,
    strides: float = 85.0,
    hr: int = 140,
    sport: Sport = Sport.RUNNING,
    sub_sport: SubSport = SubSport.GENERIC,
    with_cadence: bool = True,
    utc_offset_h: int = 2,
) -> bytes:
    """A minimal but valid FIT activity (records + session + activity)."""
    builder = FitFileBuilder(auto_define=True, min_string_size=50)
    file_id = FileIdMessage()
    file_id.type = FileType.ACTIVITY
    file_id.manufacturer = Manufacturer.GARMIN.value
    file_id.product = 0
    file_id.serial_number = 1234
    file_id.time_created = _ms(start)
    builder.add(file_id)
    for i in range(seconds):
        rec = RecordMessage()
        rec.timestamp = _ms(start + dt.timedelta(seconds=i))
        rec.position_lat = 45.0 + i * speed / 111_111
        rec.position_long = 5.0
        rec.distance = speed * i
        rec.enhanced_speed = speed
        rec.enhanced_altitude = 200.0
        rec.heart_rate = hr
        if with_cadence:
            rec.cadence = int(strides)
            rec.fractional_cadence = strides - int(strides)
        builder.add(rec)
    end = start + dt.timedelta(seconds=seconds)
    session = SessionMessage()
    session.timestamp = _ms(end)
    session.start_time = _ms(start)
    session.total_elapsed_time = float(seconds)
    session.total_timer_time = float(seconds)
    session.total_distance = speed * (seconds - 1)
    session.sport = sport
    session.sub_sport = sub_sport
    builder.add(session)
    activity = ActivityMessage()
    activity.timestamp = _ms(end)
    activity.local_timestamp = int((end + dt.timedelta(hours=utc_offset_h)).timestamp()) - 631065600
    activity.num_sessions = 1
    builder.add(activity)
    return builder.build().to_bytes()


def build_gpx(
    *, start: dt.datetime = START, seconds: int = 1200, speed: float = 3.0, cad: int = 85, hr: int = 140
) -> bytes:
    points = []
    for i in range(0, seconds, 2):
        t = (start + dt.timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lat = 45.0 + i * speed / 111_111
        points.append(
            f'<trkpt lat="{lat:.7f}" lon="5.0"><ele>200</ele><time>{t}</time>'
            f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{hr}</gpxtpx:hr><gpxtpx:cad>{cad}</gpxtpx:cad>"
            f"</gpxtpx:TrackPointExtension></extensions></trkpt>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?><gpx version="1.1" creator="test" '
        'xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">'
        f"<trk><name>Sortie test</name><type>running</type><trkseg>{''.join(points)}</trkseg></trk></gpx>"
    ).encode()


def build_tcx(
    *, start: dt.datetime = START, seconds: int = 1200, speed: float = 3.0, cad: int = 86, hr: int = 141
) -> bytes:
    points = []
    for i in range(seconds):
        t = (start + dt.timedelta(seconds=i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        points.append(
            f"<Trackpoint><Time>{t}</Time><DistanceMeters>{speed * i:.1f}</DistanceMeters>"
            f"<HeartRateBpm><Value>{hr}</Value></HeartRateBpm>"
            f"<Extensions><ns3:TPX><ns3:Speed>{speed}</ns3:Speed><ns3:RunCadence>{cad}</ns3:RunCadence></ns3:TPX></Extensions>"
            f"</Trackpoint>"
        )
    t0 = start.strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        '<?xml version="1.0"?><TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2" '
        'xmlns:ns3="http://www.garmin.com/xmlschemas/ActivityExtension/v2"><Activities><Activity Sport="Running">'
        f'<Id>{t0}</Id><Lap StartTime="{t0}"><TotalTimeSeconds>{seconds}</TotalTimeSeconds>'
        f"<DistanceMeters>{speed * seconds}</DistanceMeters><Intensity>Active</Intensity><Track>{''.join(points)}</Track></Lap>"
        "</Activity></Activities></TrainingCenterDatabase>"
    ).encode()


def parsed_activity(
    *,
    start: dt.datetime = START,
    seconds: int = 3600,
    speed=3.0,
    cadence=170.0,
    hr=140.0,
    name: str | None = None,
    source_id: str = "x1",
) -> ParsedActivity:
    """In-memory activity with per-second arrays (scalars are broadcast)."""
    t = np.arange(seconds)
    speed = np.broadcast_to(np.asarray(speed, dtype=float), t.shape)
    samples = pd.DataFrame(
        {
            "t_s": t,
            "distance_m": np.cumsum(speed),
            "speed_mps": speed,
            "cadence_raw": np.broadcast_to(np.asarray(cadence, dtype=float), t.shape),
            "heart_rate": np.broadcast_to(np.asarray(hr, dtype=float), t.shape),
            "altitude_m": 200.0,
        }
    ).reindex(columns=SAMPLE_COLUMNS)
    return ParsedActivity(
        source="test",
        source_id=source_id,
        start_time_utc=start,
        sport="running",
        samples=samples,
        cadence_unit="steps",
        name=name,
    )
