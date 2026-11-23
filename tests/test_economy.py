"""F04 — heart rate at a reference pace recovers a fitness trend hidden by pace changes."""

import numpy as np
import pandas as pd

from cadence_tracker.analysis import economy, stats


def test_hr_at_reference_recovers_fitness_trend():
    rng = np.random.default_rng(4)
    rows = []
    for run in range(60):
        month = run / 3
        run_speed = 2.7 - 0.01 * month + rng.normal(0, 0.15)  # runs get slower over time
        for km in range(1, 9):
            v = run_speed + rng.normal(0, 0.1)
            grade = rng.normal(0, 2)
            hr = 140 + 20 * (v - 2.7) + 1.5 * grade - 0.4 * month + rng.normal(0, 1.5)
            rows.append(
                {
                    "activity_id": run,
                    "km": km,
                    "speed_mps": v,
                    "grade_pct": grade,
                    "heart_rate": hr,
                    "sub_sport": "road",
                    "start_local": pd.Timestamp("2025-01-01") + pd.Timedelta(days=10 * run),
                }
            )
    ctx = pd.DataFrame(rows)
    model = economy.fit_hr_model(ctx, ref_speed=2.7)
    assert abs(model.per_speed - 20) < 2 and abs(model.per_grade - 1.5) < 0.3
    hr = economy.hr_at_reference(ctx, model)
    dates = ctx.groupby("activity_id")["start_local"].first().loc[hr.index]
    trend = stats.linear_trend(dates, hr)
    assert abs(trend.slope_per_month - (-0.4)) < 0.1  # simulated fitness gain
    # Raw HR is flattered by the slower pace: its apparent improvement is larger.
    raw = ctx[ctx.km > 1].groupby("activity_id")["heart_rate"].mean()
    assert stats.linear_trend(dates, raw.loc[hr.index]).slope_per_month < trend.slope_per_month
