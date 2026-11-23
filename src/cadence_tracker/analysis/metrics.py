"""Per-activity metrics, kilometre splits and within-run cadence analysis.

Everything here is a pure function of the stored samples (+ settings), so the
whole database can be recomputed when an algorithm changes: bump
`METRICS_VERSION` and run `ctrack recompute`.

Key definitions (docs/specs/F03-normalisation-metriques.md):

* samples are resampled on a 1 Hz grid; gaps longer than `MAX_GAP_S` are pauses;
* a second is **moving** when the smoothed speed is >= 0.8 m/s;
* a second is **running** when it is moving and both speed >= `min_run_speed_mps`
  and cadence >= `min_run_cadence_spm` (walk breaks and stops are excluded from
  cadence/pace/HR statistics);
* cadence statistics use running seconds only.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from cadence_tracker.config import Settings

METRICS_VERSION = 2  # v2: speed_cv on running seconds, fast_blocks, cadence-only fallback
MAX_GAP_S = 10
WARMUP_S = 300  # ignored by drift/fatigue estimates
MOVING_SPEED_MPS = 0.8


# ---------------------------------------------------------------- preparation
def prepare(samples: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """Return a 1 Hz frame with smoothed channels and `moving`/`running` masks."""
    df = samples.sort_values("t_s").drop_duplicates("t_s", keep="last")
    df = df.set_index("t_s")
    grid = np.arange(int(df.index.min()), int(df.index.max()) + 1)
    g = df.reindex(grid)
    observed = g["distance_m"].notna() | g["speed_mps"].notna() | g["cadence_spm"].notna() | g["heart_rate"].notna()
    for col in ("speed_mps", "cadence_spm", "heart_rate", "altitude_m"):
        if col in g:
            g[col] = g[col].ffill(limit=MAX_GAP_S)
    if g["distance_m"].notna().any():
        g["distance_m"] = g["distance_m"].interpolate(limit=MAX_GAP_S, limit_area="inside").ffill()
    # Recording gaps (watch paused): seconds further than MAX_GAP_S from the last sample.
    index = pd.Series(g.index, index=g.index, dtype=float)
    last_seen = index.where(observed).ffill()
    paused = (index - last_seen) > MAX_GAP_S

    # Speed: prefer the device channel, else derive it from distance.
    if g["speed_mps"].notna().sum() < 0.2 * len(g) and g["distance_m"].notna().any():
        g["speed_mps"] = g["distance_m"].diff().clip(lower=0)
    if g["distance_m"].isna().all() and g["speed_mps"].notna().any():
        g["distance_m"] = g["speed_mps"].fillna(0).cumsum()

    g["speed_smooth"] = g["speed_mps"].rolling(9, center=True, min_periods=3).mean()
    # Speed unusable (treadmill without footpod: speed ~0 while the wrist records
    # a running cadence): drop it and detect running from cadence alone.
    speed_dead = (g["speed_smooth"] >= MOVING_SPEED_MPS).mean() < 0.10
    cadence_alive = (g["cadence_spm"] >= settings.min_run_cadence_spm).mean() >= 0.30
    if g["speed_smooth"].isna().all() or (speed_dead and cadence_alive):
        g[["speed_mps", "speed_smooth"]] = np.nan
    g["moving"] = (g["speed_smooth"] >= MOVING_SPEED_MPS) & ~paused
    if g["speed_smooth"].isna().all():  # no usable speed: rely on cadence
        g["moving"] = (g["cadence_spm"] >= 60) & ~paused
    cad_ok = g["cadence_spm"].isna() | (g["cadence_spm"] >= settings.min_run_cadence_spm)
    speed_ok = g["speed_smooth"].isna() | (g["speed_smooth"] >= settings.min_run_speed_mps)
    g["running"] = g["moving"] & cad_ok & speed_ok
    if g["altitude_m"].notna().any():
        g["altitude_smooth"] = g["altitude_m"].rolling(15, center=True, min_periods=1).mean()
    else:
        g["altitude_smooth"] = np.nan
    g.index.name = "t_s"
    return g.reset_index()


def _elevation_gain(altitude: pd.Series, threshold: float = 2.0) -> tuple[float, float]:
    """Ascent/descent with hysteresis (ignores GPS/baro noise below `threshold` m)."""
    values = altitude.dropna().to_numpy()
    if values.size < 2:
        return (np.nan, np.nan)
    up = down = 0.0
    anchor = values[0]
    for v in values[1:]:
        delta = v - anchor
        if delta >= threshold:
            up += delta
            anchor = v
        elif delta <= -threshold:
            down -= delta
            anchor = v
    return up, down


def _ols_slope(x: np.ndarray, y: np.ndarray, extra: np.ndarray | None = None) -> float:
    """Coefficient of x in y ~ 1 + x (+ extra)."""
    cols = [np.ones_like(x), x]
    if extra is not None:
        cols.append(extra)
    design = np.column_stack(cols)
    mask = np.isfinite(design).all(axis=1) & np.isfinite(y)
    if mask.sum() < len(cols) + 5:
        return np.nan
    coef, *_ = np.linalg.lstsq(design[mask], y[mask], rcond=None)
    return float(coef[1])


def _speed_variability(g: pd.DataFrame) -> dict[str, Any]:
    """Interval signature, measured on running seconds only (stops excluded).

    * speed_cv: coefficient of variation of the 30 s rolling speed;
    * fast_blocks: number of efforts held >= 30 s at a 20 s rolling speed at least
      15 % above the session median (repetitions; GPS jitter and short strides
      do not count).
    """
    speed = g["speed_mps"].where(g["running"])
    rolling = speed.dropna().rolling(30, min_periods=15).mean().dropna()
    if len(rolling) <= 120 or rolling.mean() <= 0:
        return {}
    fast = speed.rolling(20, min_periods=10).mean()
    above = (fast > 1.15 * fast.median()).fillna(False)
    segment = (above != above.shift(fill_value=False)).cumsum()
    lengths = above.groupby(segment).sum()
    return {"speed_cv": float(rolling.std() / rolling.mean()), "fast_blocks": int((lengths >= 30).sum())}


# ------------------------------------------------------------------- outputs
def minute_bins(g: pd.DataFrame, min_coverage_s: int = 30) -> pd.DataFrame:
    """1-minute aggregates of running seconds (used for drift and in the UI)."""
    run = g[g["running"]].copy()
    if run.empty:
        return pd.DataFrame(columns=["minute", "t_s", "cadence_spm", "speed_mps", "heart_rate", "altitude_m", "n"])
    run["minute"] = (run["t_s"] // 60).astype(int)
    bins = run.groupby("minute").agg(
        t_s=("t_s", "mean"),
        cadence_spm=("cadence_spm", "mean"),
        speed_mps=("speed_mps", "mean"),
        heart_rate=("heart_rate", "mean"),
        altitude_m=("altitude_smooth", "mean"),
        n=("t_s", "size"),
    )
    return bins[bins["n"] >= min_coverage_s].reset_index()


def compute_splits(g: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "km",
        "distance_m",
        "duration_s",
        "speed_mps",
        "cadence_spm",
        "heart_rate",
        "elev_gain_m",
        "grade_pct",
        "elapsed_end_s",
    ]
    mov = g[g["moving"] & g["distance_m"].notna()].copy()
    if mov.empty:
        return pd.DataFrame(columns=cols)
    mov["d"] = mov["distance_m"] - g["distance_m"].min()
    mov["km"] = (mov["d"] // 1000).astype(int) + 1
    mov["cad_run"] = mov["cadence_spm"].where(mov["running"] & (mov["cadence_spm"] > 0))
    mov["alt_step"] = mov["altitude_smooth"].diff().clip(lower=0)
    agg = mov.groupby("km").agg(
        d_end=("d", "max"),
        duration_s=("t_s", "size"),
        cadence_spm=("cad_run", "mean"),
        heart_rate=("heart_rate", "mean"),
        elev_gain_m=("alt_step", "sum"),
        alt_first=("altitude_smooth", "first"),
        alt_last=("altitude_smooth", "last"),
        elapsed_end_s=("t_s", "max"),
    )
    agg["distance_m"] = agg["d_end"].diff().fillna(agg["d_end"])
    agg = agg[agg["distance_m"] >= 200]
    agg["speed_mps"] = agg["distance_m"] / agg["duration_s"]
    agg["grade_pct"] = (agg["alt_last"] - agg["alt_first"]) / agg["distance_m"] * 100
    return agg.reset_index()[cols]


def compute_metrics(
    samples: pd.DataFrame,
    settings: Settings,
    laps: pd.DataFrame | None = None,
    summary: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Return (metrics dict for `activity_metrics`, kilometre splits)."""
    summary = summary or {}
    g = prepare(samples, settings)
    run = g[g["running"]]
    m: dict[str, Any] = {"metrics_version": METRICS_VERSION}

    m["elapsed_s"] = float(summary.get("elapsed_s") or (g["t_s"].max() - g["t_s"].min()))
    m["moving_s"] = float(g["moving"].sum())
    m["running_s"] = float(len(run))
    dist_channel = g["distance_m"].max() - g["distance_m"].min() if g["distance_m"].notna().any() else np.nan
    m["distance_m"] = float(summary.get("distance_m") or dist_channel)

    speed = run["speed_mps"].dropna()
    m["avg_speed_mps"] = float(speed.mean()) if len(speed) else np.nan

    cad = run["cadence_spm"][run["cadence_spm"] > 0].dropna()
    m["has_cadence"] = int(len(cad) > 0.5 * max(len(run), 1))
    if len(cad):
        m.update(
            cadence_mean=float(cad.mean()),
            cadence_median=float(cad.median()),
            cadence_p10=float(cad.quantile(0.10)),
            cadence_p90=float(cad.quantile(0.90)),
            cadence_std=float(cad.std()),
        )

    hr_all = g.loc[g["moving"], "heart_rate"]
    hr_all = hr_all[hr_all > 30].dropna()
    m["has_hr"] = int(len(hr_all) > 0.5 * max(m["moving_s"], 1))
    if len(hr_all):
        m["hr_mean"] = float(hr_all.mean())
        m["hr_peak"] = float(g["heart_rate"].rolling(30, min_periods=20).mean().max())

    m["has_altitude"] = int(g["altitude_m"].notna().mean() > 0.5)

    ascent, descent = summary.get("ascent_m"), summary.get("descent_m")
    if ascent is None and m["has_altitude"]:
        ascent, descent = _elevation_gain(g["altitude_smooth"])
    m["ascent_m"] = float(ascent) if ascent is not None else np.nan
    m["descent_m"] = float(descent) if descent is not None else np.nan
    if m["distance_m"] and np.isfinite(m["ascent_m"]):
        m["ascent_per_km"] = m["ascent_m"] / (m["distance_m"] / 1000)

    if np.isfinite(m["avg_speed_mps"]) and m.get("cadence_mean"):
        m["stride_m"] = m["avg_speed_mps"] / (m["cadence_mean"] / 60)

    run_hr = run[(run["heart_rate"] > 30) & run["speed_mps"].notna()]
    if len(run_hr) >= 300:
        m["efficiency"] = float(run_hr["speed_mps"].mean() * 60 / run_hr["heart_rate"].mean())
        if len(run_hr) >= 1200:
            half = len(run_hr) // 2
            ef1 = run_hr["speed_mps"].iloc[:half].mean() / run_hr["heart_rate"].iloc[:half].mean()
            ef2 = run_hr["speed_mps"].iloc[half:].mean() / run_hr["heart_rate"].iloc[half:].mean()
            m["decoupling_pct"] = float((ef1 - ef2) / ef1 * 100)

    if len(cad) >= 600:
        half = len(cad) // 2
        m["cadence_first_half"] = float(cad.iloc[:half].median())
        m["cadence_second_half"] = float(cad.iloc[half:].median())

    bins = minute_bins(g)
    bins = bins[(bins["t_s"] >= WARMUP_S) & (bins["cadence_spm"] > 0)]
    if len(bins) >= 15:
        t_h = bins["t_s"].to_numpy() / 3600.0
        y = bins["cadence_spm"].to_numpy()
        m["cadence_drift_spm_h"] = _ols_slope(t_h, y)
        m["cadence_fatigue_spm_h"] = _ols_slope(t_h, y, bins["speed_mps"].to_numpy())

    m.update(_speed_variability(g))

    if laps is not None and not laps.empty and "intensity" in laps:
        intensity = laps["intensity"].fillna("").str.lower()
        active = (intensity == "active") & (laps["duration_s"].fillna(0) < 1800)
        m["n_active_laps"] = int(active.sum())
        m["n_rest_laps"] = int(intensity.isin(["rest", "recovery"]).sum())
        if active.any():
            m["active_lap_mean_s"] = float(laps.loc[active, "duration_s"].mean())

    return m, compute_splits(g)
