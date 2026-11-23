"""End-to-end: the demo generator's known effects are recovered by the analyses."""

from datetime import date

import pytest

from cadence_tracker import demo
from cadence_tracker.analysis import cadence_goal, questions
from cadence_tracker.ingest.pipeline import ingest_parsed, reclassify
from cadence_tracker.storage import repository as repo


@pytest.fixture()
def demo_conn(conn):
    for activity in demo.generate(weeks=20, seed=3, end=date(2026, 11, 1)):
        ingest_parsed(conn, activity, origin="demo")
    reclassify(conn)
    return conn


def test_questions_recover_simulated_effects(demo_conn):
    acts = repo.load_activities(demo_conn)
    results = {q.key: q for q in questions.all_questions(acts, repo.load_splits(demo_conn))}
    assert results["trend"].verdict == "up"
    assert results["same_pace"].verdict == "up"
    hr = results["hr_same_pace"].effect
    assert hr.ci_low < -0.5 and hr.ci_high < 0  # simulated: -0.8 bpm/month
    assert results["fatigue"].verdict == "down"


def test_goal_status_and_classification(demo_conn):
    acts = repo.load_activities(demo_conn)
    types = set(acts["session_type"])
    assert {"ef", "long", "intervals", "tempo", "trail"} <= types
    settings = repo.load_settings(demo_conn)
    settings.cadence_target_spm = 172
    settings.cadence_goal_start = "2026-07-01"
    runs = acts[acts["session_type"].isin(["ef", "long"]) & (acts["sub_sport"] == "road")]
    ctx = questions.splits_context(repo.load_splits(demo_conn), runs)
    df, b, ref = cadence_goal.annotate(runs, ctx)
    status = cadence_goal.goal_status(df, b, ref, settings)
    assert 4 < b < 14  # simulated: 9 steps/min per m/s
    assert status.current > status.baseline
    assert status.trend.slope_per_month > 0
    # Projection: the optimistic date comes before the central one, itself before the pessimistic one.
    if status.eta and status.eta_slow:
        assert status.eta_fast <= status.eta <= status.eta_slow
