"""F03 — per-activity metrics, running detection, splits, drift."""

import numpy as np

from cadence_tracker.analysis.metrics import compute_metrics
from cadence_tracker.config import Settings
from cadence_tracker.ingest.pipeline import clean_samples
from tests.helpers import parsed_activity


def _metrics(activity):
    return compute_metrics(clean_samples(activity), Settings())


def test_steady_run_metrics():
    m, splits = _metrics(parsed_activity(seconds=3600, speed=3.0, cadence=170, hr=140))
    assert abs(m["cadence_median"] - 170) < 1e-6
    assert abs(m["avg_speed_mps"] - 3.0) < 0.01
    assert abs(m["stride_m"] - 3.0 / (170 / 60)) < 0.01
    assert abs(m["efficiency"] - 3.0 * 60 / 140) < 0.01
    # 3600 s at 3 m/s = 10.8 km: 10 full kilometres + a partial 800 m split
    assert len(splits) == 11 and abs(splits["speed_mps"].iloc[0] - 3.0) < 0.05
    assert abs(splits["distance_m"].iloc[-1] - 800) < 10


def test_walk_breaks_are_excluded_from_cadence():
    seconds = 1800
    speed = np.full(seconds, 3.0)
    cadence = np.full(seconds, 172.0)
    speed[600:900] = 1.3  # walking
    cadence[600:900] = 110.0
    m, _ = _metrics(parsed_activity(seconds=seconds, speed=speed, cadence=cadence))
    assert abs(m["cadence_mean"] - 172) < 0.5
    assert m["running_s"] < 1550


def test_cadence_fatigue_is_measured_at_constant_pace():
    seconds = 5400
    t = np.arange(seconds)
    speed = 3.0 + 0.3 * np.sin(t / 400)  # pace varies
    cadence = 170 + 9 * (speed - 3.0) - 3.0 * t / 3600  # -3 steps/min per hour at constant pace
    m, _ = _metrics(parsed_activity(seconds=seconds, speed=speed, cadence=cadence))
    assert abs(m["cadence_fatigue_spm_h"] - (-3.0)) < 0.3


def test_treadmill_without_speed_uses_cadence():
    """Wrist-only treadmill run: speed ~0, cadence present -> still a run."""
    seconds = 1500
    m, _ = _metrics(parsed_activity(seconds=seconds, speed=np.full(seconds, 0.05), cadence=166))
    assert m["running_s"] > 1400 and abs(m["cadence_median"] - 166) < 0.5
    assert np.isnan(m.get("avg_speed_mps", np.nan))


def test_interval_signature_ignores_stops():
    seconds = 2400
    t = np.arange(seconds)
    steady = np.full(seconds, 3.0)
    steady[(t % 300) < 40] = 0.0  # traffic lights every 5 min
    m_stops, _ = _metrics(parsed_activity(seconds=seconds, speed=steady, cadence=np.where(steady > 0, 168, 0)))
    reps = np.where((t // 120) % 2 == 0, 4.2, 2.6)  # 2 min fast / 2 min slow
    reps[:600] = 2.8
    m_reps, _ = _metrics(parsed_activity(seconds=seconds, speed=reps, cadence=165))
    assert m_stops["speed_cv"] < 0.05 and m_stops.get("fast_blocks", 0) <= 1
    assert m_reps["speed_cv"] > 0.10 and m_reps["fast_blocks"] >= 5
