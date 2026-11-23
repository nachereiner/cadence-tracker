"""F05 / F11 — colours of the period scatter (Corrélations)."""

import numpy as np
import pandas as pd

from cadence_tracker.ui import charts

P = charts.NIGHT


def _kms(n_days: int, freq: str = "D") -> pd.DataFrame:
    rng = np.random.default_rng(0)
    dates = pd.date_range("2026-01-01", periods=n_days, freq=freq)
    return pd.DataFrame(
        {
            "start_local": dates,
            "pace_s_km": rng.uniform(330, 420, n_days),
            "cadence_spm": rng.uniform(160, 172, n_days),
        }
    )


def _marker_colors(fig) -> list[str]:
    return [t.marker.color for t in fig.data if t.mode == "markers"]


def test_periods_use_three_distinct_hues_latest_amber():
    fig = charts.scatter_by_period(_kms(90), "pace_s_km", "cadence_spm", P, "Allure", "Cadence")
    colors = _marker_colors(fig)
    assert colors == ["#3B8EE6", "#D9628F", "#C28400"]  # oldest -> most recent


def test_fewer_periods_keep_the_latest_in_amber():
    fig = charts.scatter_by_period(_kms(8, freq="10D"), "pace_s_km", "cadence_spm", P, "Allure", "Cadence")
    colors = _marker_colors(fig)
    assert len(colors) == 2
    assert colors[-1] == "#C28400"
    # each fitted line takes its period's colour
    line_colors = {t.line.color for t in fig.data if t.mode == "lines"}
    assert line_colors <= set(colors)
