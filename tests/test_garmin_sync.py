"""F01 — Garmin Personal API sync with a fake client (no network)."""

import io
import zipfile
from datetime import timedelta

from cadence_tracker.ingest import garmin
from cadence_tracker.storage import repository as repo
from tests.helpers import START, build_fit


class HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


class FakeClient:
    def __init__(self, activities, fail_download_with=None):
        self.activities = activities
        self.downloads = []
        self.fail = fail_download_with

    def search_activities(self, start=0, limit=20, start_date=None, end_date=None):
        return self.activities[start : start + limit]

    def download_activity(self, activity_id):
        if self.fail:
            code, self.fail = self.fail, None
            raise HttpError(code)
        self.downloads.append(activity_id)
        index = int(activity_id) - 100
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(f"{activity_id}_ACTIVITY.fit", build_fit(start=START + timedelta(days=index), seconds=600))
        return buf.getvalue()


def _items(n, type_key="running"):
    return [
        {
            "activityId": 100 + i,
            "activityName": f"Run {i}",
            "activityType": {"typeKey": type_key},
            "startTimeGMT": f"2026-09-{i + 1:02d} 07:00:00",
        }
        for i in range(n)
    ]


def test_sync_imports_running_activities_once(conn):
    client = FakeClient(_items(3) + _items(1, "cycling"))
    report = garmin.sync(conn, client_factory=lambda **_: client, sleep=lambda s: None)
    assert report.running == 3 and report.imported == 3
    assert repo.load_activities(conn)["name"].tolist() == ["Run 0", "Run 1", "Run 2"]
    report2 = garmin.sync(conn, client_factory=lambda **_: client, sleep=lambda s: None)
    assert report2.downloaded == 0 and report2.already_synced == 3
    assert repo.get_sync_state(conn, garmin.SOURCE)["last_activity_start"] == "2026-09-03"


def test_rate_limit_is_retried(conn):
    client = FakeClient(_items(1), fail_download_with=429)
    waits = []
    report = garmin.sync(conn, client_factory=lambda **_: client, sleep=waits.append)
    assert report.imported == 1 and 30 in waits


def test_interrupted_sync_keeps_previous_cursor(conn):
    client = FakeClient(_items(2), fail_download_with=403)
    report = garmin.sync(conn, client_factory=lambda **_: client, sleep=lambda s: None)
    assert report.stopped_early
    assert not repo.get_sync_state(conn, garmin.SOURCE).get("last_activity_start")
