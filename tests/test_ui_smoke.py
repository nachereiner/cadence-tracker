"""Every page renders without exception on the demo data (headless Streamlit)."""

from datetime import date

import pytest
from streamlit.testing.v1 import AppTest

from cadence_tracker import demo
from cadence_tracker.ingest.pipeline import ingest_parsed, reclassify

SCRIPT = """
import streamlit as st
from cadence_tracker.ui import common
from cadence_tracker.ui.views import {view}
from cadence_tracker.ui import theme
theme.inject()
common.PAGES.update({{k: st.Page(lambda: None, title=k, url_path=k) for k in ["compare", "dashboard", "settings"]}})
{view}.render()
"""


@pytest.fixture(scope="module")
def demo_db(tmp_path_factory):
    import os

    from cadence_tracker.storage import db

    folder = tmp_path_factory.mktemp("ui")
    os.environ["CTRACK_DATA_DIR"] = str(folder)
    os.environ.pop("CTRACK_DB", None)
    conn = db.connect()
    for activity in demo.generate(weeks=14, seed=5, end=date.today()):
        ingest_parsed(conn, activity, origin="demo")
    reclassify(conn)
    conn.close()
    yield folder
    os.environ.pop("CTRACK_DATA_DIR", None)


@pytest.mark.parametrize("view", ["dashboard", "correlations", "goal", "activities", "compare", "reglages"])
def test_page_renders(demo_db, view):
    at = AppTest.from_string(SCRIPT.format(view=view), default_timeout=120)
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_empty_database_shows_onboarding(tmp_path, monkeypatch):
    monkeypatch.setenv("CTRACK_DATA_DIR", str(tmp_path))
    at = AppTest.from_string(SCRIPT.format(view="dashboard"), default_timeout=60)
    at.run()
    assert not at.exception
    assert any("Aucune sortie pour l" in i.value for i in at.info)


@pytest.mark.parametrize("granularity", ["day", "week", "month", "year"])
@pytest.mark.parametrize("mode", ["road", "trail"])
def test_dashboard_modes_and_granularities(demo_db, mode, granularity):
    at = AppTest.from_string(SCRIPT.format(view="dashboard"), default_timeout=120)
    at.session_state["f_mode"] = mode
    at.session_state["dash_gran"] = granularity
    at.run()
    assert not at.exception, [e.message for e in at.exception]


def test_compare_three_runs(demo_db):
    import sqlite3

    ids = [
        r[0]
        for r in sqlite3.connect(demo_db / "cadence.db").execute(
            "SELECT id FROM activities WHERE sub_sport = 'road' ORDER BY start_time_utc DESC LIMIT 3"
        )
    ]
    at = AppTest.from_string(SCRIPT.format(view="compare"), default_timeout=120)
    at.session_state["cmp_runs_road"] = ids
    at.run()
    assert not at.exception, [e.message for e in at.exception]
    assert len(at.get("plotly_chart")) == 1


def test_goal_page_with_a_target(demo_db):
    from cadence_tracker.storage import db, repository

    conn = db.connect(demo_db / "cadence.db")
    settings = repository.load_settings(conn)
    settings.cadence_target_spm = 172
    settings.cadence_goal_start = "2026-09-01"
    repository.save_settings(conn, settings)
    at = AppTest.from_string(SCRIPT.format(view="goal"), default_timeout=120)
    at.run()
    assert not at.exception
    html_blocks = " ".join(e.proto.body for e in at.get("html"))
    assert "Objectif" in html_blocks and "ct-lane-track" in html_blocks


def test_dashboard_heart_rate_at_reference_pace(demo_db):
    at = AppTest.from_string(SCRIPT.format(view="dashboard"), default_timeout=120)
    at.session_state["dash_metric"] = "hr_ref"
    at.run()
    assert not at.exception
    assert any("ramenée à" in c.value for c in at.caption)
