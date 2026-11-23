"""F04/F05 — trends and adjusted effects recover known effects."""

import numpy as np
import pandas as pd

from cadence_tracker.analysis import stats


def test_linear_trend_slope_per_month():
    dates = pd.date_range("2026-01-01", periods=60, freq="3D")
    months = stats.months_since(pd.Series(dates))
    y = 165 + 1.5 * months + np.random.default_rng(0).normal(0, 0.5, len(dates))
    trend = stats.linear_trend(pd.Series(dates), pd.Series(y))
    assert abs(trend.slope_per_month - 1.5) < 0.1 and trend.direction == "up"


def test_adjusted_effect_removes_confounding_by_pace():
    """Cadence depends only on speed; speed rises over time -> raw trend is spurious."""
    rng = np.random.default_rng(1)
    n = 400
    t = rng.uniform(0, 10, n)
    speed = 2.8 + 0.05 * t + rng.normal(0, 0.2, n)
    cadence = 140 + 10 * speed + rng.normal(0, 1, n)
    df = pd.DataFrame({"t": t, "speed": speed, "cadence": cadence})
    raw = stats.adjusted_effect(df, "cadence", "t")
    adjusted = stats.adjusted_effect(df, "cadence", "t", ["speed"])
    assert raw.direction == "up"  # naive answer: "my cadence increases"
    assert adjusted.direction == "flat" and abs(adjusted.coef) < 0.1
