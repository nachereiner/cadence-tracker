"""Cadence goal: where you are, how fast you progress, when you will get there.

Definitions (docs/specs/F07-objectif-cadence.md):

* the runs taken into account are chosen by the caller (Objectif page filter:
  endurance and long runs by default);
* the cadence of a run is its **mean over running seconds** (watches record whole
  steps, so per-run medians are whole numbers and too coarse to follow progress);
* it is **pace-adjusted** to a reference speed, because cadence rises with
  speed: adjusted = mean cadence + b x (reference speed - run speed), where b
  (steps/min per m/s) is estimated *within* runs from kilometre splits;
* the **rhythm** is the linear trend of the adjusted cadence since the goal
  start, measured over at least the last 12 weeks (a 3-week-old goal would
  give a meaningless slope); its 95 % interval gives an optimistic and a
  pessimistic arrival date.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

from cadence_tracker.analysis import stats
from cadence_tracker.config import Settings

DEFAULT_SPEED_SLOPE = 8.0  # steps/min per m/s, typical value when data is scarce
MAX_HORIZON_MONTHS = 36  # beyond this, an arrival date is not meaningful
MIN_TREND_DAYS = 84  # the rhythm is measured over at least 12 weeks


def speed_slope(splits_ctx: pd.DataFrame) -> float:
    """Within-run slope of cadence vs speed (activity-demeaned splits)."""
    if splits_ctx is None or splits_ctx.empty:
        return DEFAULT_SPEED_SLOPE
    df = splits_ctx.dropna(subset=["cadence_spm", "speed_mps"])
    df = df[df.groupby("activity_id")["km"].transform("size") >= 3]
    if len(df) < 30:
        return DEFAULT_SPEED_SLOPE
    x = df["speed_mps"] - df.groupby("activity_id")["speed_mps"].transform("mean")
    y = df["cadence_spm"] - df.groupby("activity_id")["cadence_spm"].transform("mean")
    if float((x**2).sum()) < 1e-6:
        return DEFAULT_SPEED_SLOPE
    return float(np.clip((x * y).sum() / (x**2).sum(), 0.0, 25.0))


def annotate(runs: pd.DataFrame, splits_ctx: pd.DataFrame) -> tuple[pd.DataFrame, float, float | None]:
    """Add `cadence_adjusted` (cadence at the reference speed) to the given runs."""
    df = runs.copy()
    b = speed_slope(splits_ctx)
    ref = df["avg_speed_mps"].median() if not df.empty else np.nan
    ref = float(ref) if pd.notna(ref) else None
    if ref is None:
        df["cadence_adjusted"] = df["cadence_mean"]
    else:
        df["cadence_adjusted"] = df["cadence_mean"] + b * (ref - df["avg_speed_mps"])
    return df, b, ref


@dataclass
class GoalStatus:
    target: float | None
    baseline: float | None
    current: float | None
    progress_pct: float | None
    trend: stats.Trend | None
    eta: date | None  # at the central rhythm
    eta_fast: date | None  # at the upper bound of the 95 % interval
    eta_slow: date | None  # at the lower bound (None: may never be reached)
    last_date: pd.Timestamp | None
    reference_speed: float | None
    speed_slope: float
    n_runs: int

    @property
    def reached(self) -> bool:
        return bool(self.target and self.current is not None and self.current >= self.target)


def eta_from(current: float, target: float, slope_per_month: float, end: pd.Timestamp) -> date | None:
    """Date at which `target` is reached at a constant rhythm (None if never / too far)."""
    if slope_per_month <= 0:
        return None
    months = (target - current) / slope_per_month
    if months > MAX_HORIZON_MONTHS:
        return None
    return (end + pd.Timedelta(days=months * stats.DAYS_PER_MONTH)).date()


def goal_status(df: pd.DataFrame, b: float, ref: float | None, settings: Settings) -> GoalStatus:
    runs = df.dropna(subset=["cadence_adjusted"]).sort_values("start_local")
    target = settings.cadence_target_spm
    baseline = current = progress = trend = end = None
    eta = eta_fast = eta_slow = None
    if not runs.empty:
        start = pd.Timestamp(settings.cadence_goal_start) if settings.cadence_goal_start else runs["start_local"].min()
        before = runs[(runs["start_local"] < start) & (runs["start_local"] >= start - pd.Timedelta(days=28))]
        after = runs[(runs["start_local"] >= start) & (runs["start_local"] < start + pd.Timedelta(days=28))]
        base_set = before if len(before) >= 3 else after
        baseline = float(base_set["cadence_adjusted"].median()) if len(base_set) else None
        end = runs["start_local"].max()
        recent = runs[runs["start_local"] > end - pd.Timedelta(days=28)]
        current = float(recent["cadence_adjusted"].median()) if len(recent) else None
        window_start = min(start - pd.Timedelta(days=28), end - pd.Timedelta(days=MIN_TREND_DAYS))
        since = runs[runs["start_local"] >= window_start]
        trend = stats.linear_trend(since["start_local"], since["cadence_adjusted"])
        if target and baseline is not None and current is not None and target != baseline:
            progress = (current - baseline) / (target - baseline) * 100
        if target and current is not None and trend and current < target:
            eta = eta_from(current, target, trend.slope_per_month, end)
            eta_fast = eta_from(current, target, trend.ci_high, end)
            eta_slow = eta_from(current, target, trend.ci_low, end)
    return GoalStatus(
        target=target,
        baseline=baseline,
        current=current,
        progress_pct=progress,
        trend=trend,
        eta=eta,
        eta_fast=eta_fast,
        eta_slow=eta_slow,
        last_date=end,
        reference_speed=ref,
        speed_slope=b,
        n_runs=len(runs),
    )
