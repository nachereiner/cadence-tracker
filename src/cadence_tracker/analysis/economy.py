"""Running economy at comparable conditions: heart rate at a reference pace.

Raw efficiency (speed / HR) depends on pace and terrain as much as on fitness:
a slower or hillier run lowers it even when fitness improves. Here each run's
heart rate is brought back to a reference pace on flat ground:

    HR_ref = mean over its km splits of [HR - b_v x (v - v_ref) - b_g x grade]

where b_v (bpm per m/s) and b_g (bpm per % of grade) are estimated *within*
runs (splits demeaned by activity), so they are not polluted by differences
between days. The first kilometre is skipped (heart-rate lag).

See docs/specs/F04-tableau-de-bord.md ("FC à allure de référence").
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

MIN_SPLITS = 3


@dataclass
class HrModel:
    per_speed: float  # bpm per m/s
    per_grade: float  # bpm per % of grade
    ref_speed: float  # m/s
    n_splits: int


def fit_hr_model(splits_ctx: pd.DataFrame, ref_speed: float | None = None) -> HrModel | None:
    df = splits_ctx.dropna(subset=["heart_rate", "speed_mps", "grade_pct"])
    df = df[(df["km"] > 1) & (df["sub_sport"] != "treadmill")]
    df = df[df.groupby("activity_id")["km"].transform("size") >= MIN_SPLITS]
    if len(df) < 30:
        return None
    cols = ["heart_rate", "speed_mps", "grade_pct"]
    centred = df[cols] - df.groupby("activity_id")[cols].transform("mean")
    x = centred[["speed_mps", "grade_pct"]].to_numpy()
    coef, *_ = np.linalg.lstsq(x, centred["heart_rate"].to_numpy(), rcond=None)
    ref = ref_speed if ref_speed is not None else float(df["speed_mps"].median())
    return HrModel(per_speed=float(coef[0]), per_grade=float(coef[1]), ref_speed=ref, n_splits=len(df))


def hr_at_reference(splits_ctx: pd.DataFrame, model: HrModel) -> pd.Series:
    """Heart rate of each run at the reference pace on flat ground (index: activity id)."""
    df = splits_ctx.dropna(subset=["heart_rate", "speed_mps", "grade_pct"])
    df = df[df["km"] > 1]
    adjusted = (
        df["heart_rate"] - model.per_speed * (df["speed_mps"] - model.ref_speed) - model.per_grade * df["grade_pct"]
    )
    out = adjusted.groupby(df["activity_id"]).agg(["mean", "size"])
    return out.loc[out["size"] >= MIN_SPLITS, "mean"]
