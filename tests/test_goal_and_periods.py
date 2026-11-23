"""F04 / F07 — period aggregation and goal projection."""

import pandas as pd

from cadence_tracker.analysis import stats
from cadence_tracker.analysis.cadence_goal import eta_from


def _runs():
    dates = pd.to_datetime(["2026-01-05", "2026-01-07", "2026-01-20", "2026-02-03"])
    return pd.DataFrame(
        {
            "id": range(4),
            "start_local": dates,
            "distance_km": [10, 5, 8, 12],
            "duration_h": [1, 0.5, 0.8, 1.2],
            "running_s": [3600, 1800, 2880, 4320],
            "avg_speed_mps": [2.8, 2.8, 2.8, 2.8],
            "hr_mean": [140, 150, 145, 140],
            "cadence_median": [164, 166, 165, 168],
            "cadence_mean": [164, 166, 165, 168],
            "stride_m": [1.0, 1.0, 1.0, 1.0],
            "family": ["A", "B", "A", "A"],
        }
    )


def test_aggregate_by_month_and_week():
    month = stats.aggregate_by_period(_runs(), "month")
    assert month["n"].tolist() == [3, 1] and month["km"].tolist() == [23, 12]
    jan = month.iloc[0]
    assert abs(jan["hr"] - (140 * 3600 + 150 * 1800 + 145 * 2880) / (3600 + 1800 + 2880)) < 1e-9  # time-weighted
    assert jan["km::A"] == 18 and jan["km::B"] == 5
    # Cadence = average over running seconds, not a median of whole-number medians.
    assert abs(jan["cadence"] - (164 * 3600 + 166 * 1800 + 165 * 2880) / (3600 + 1800 + 2880)) < 1e-9
    week = stats.aggregate_by_period(_runs(), "week")
    assert week["period"].iloc[0] == pd.Timestamp("2026-01-05")  # weeks start on Monday


def test_eta():
    end = pd.Timestamp("2026-11-01")
    assert str(eta_from(165, 170, 1.0, end))[:7] == "2027-04"  # 5 months at +1 step/min per month
    assert eta_from(165, 170, 0.0, end) is None  # flat rhythm: never
    assert eta_from(165, 175, 0.1, end) is None  # beyond 3 years: no date


def test_median_of_medians_is_stuck_but_weighted_mean_is_not():
    """Watches record whole steps: per-run medians are integers (real data, 19/11/2026)."""
    a = pd.DataFrame({"cadence_mean": [165.4, 164.7, 165.9], "running_s": [3000, 2000, 4000]})
    b = pd.DataFrame({"cadence_mean": [165.6, 165.2, 166.3], "running_s": [3000, 2000, 4000]})
    assert stats.weighted_mean(a["cadence_mean"], a["running_s"]) != stats.weighted_mean(
        b["cadence_mean"], b["running_s"]
    )
