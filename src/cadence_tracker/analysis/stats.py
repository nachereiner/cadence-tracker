"""Statistical building blocks: trends, correlations, adjusted effects.

The central idea (docs/specs/F05-correlations.md): a raw trend of cadence over
time can be driven by pace, terrain or session mix. We therefore estimate the
effect of time *holding confounders constant* with a multiple linear regression
(OLS). When the unit of analysis is the kilometre split, several rows belong to
the same run, so standard errors are clustered by activity.

These are associations, not causal effects: the UI always says so.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as sps

DAYS_PER_MONTH = 30.44
FRENCH_MONTHS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def months_since(dates: pd.Series, origin: pd.Timestamp | None = None) -> pd.Series:
    dates = pd.to_datetime(dates)
    origin = origin if origin is not None else dates.min()
    return (dates - origin).dt.total_seconds() / 86400 / DAYS_PER_MONTH


# ---------------------------------------------------------------------- trend
@dataclass
class Trend:
    slope_per_month: float
    ci_low: float
    ci_high: float
    p_value: float
    r2: float
    n: int
    intercept: float
    origin: pd.Timestamp

    @property
    def direction(self) -> str:
        """'up' | 'down' | 'flat' using the 95 % confidence interval."""
        if self.ci_low > 0:
            return "up"
        if self.ci_high < 0:
            return "down"
        return "flat"

    def predict(self, dates) -> np.ndarray:
        x = months_since(pd.Series(pd.to_datetime(dates)), self.origin).to_numpy()
        return self.intercept + self.slope_per_month * x


def linear_trend(dates: pd.Series, values: pd.Series, min_n: int = 6) -> Trend | None:
    df = pd.DataFrame(
        {"d": pd.to_datetime(dates).to_numpy(), "y": pd.to_numeric(values, errors="coerce").to_numpy()}
    ).dropna()
    if len(df) < min_n or df["d"].nunique() < 3:
        return None
    origin = df["d"].min()
    x = months_since(df["d"], origin).to_numpy()
    res = sps.linregress(x, df["y"].to_numpy())
    t = sps.t.ppf(0.975, len(df) - 2)
    return Trend(
        slope_per_month=float(res.slope),
        ci_low=float(res.slope - t * res.stderr),
        ci_high=float(res.slope + t * res.stderr),
        p_value=float(res.pvalue),
        r2=float(res.rvalue**2),
        n=len(df),
        intercept=float(res.intercept),
        origin=origin,
    )


def rolling_mean(
    df: pd.DataFrame, value_col: str, date_col: str = "start_local", days: int = 28, min_periods: int = 3
) -> pd.Series:
    """Time-based rolling mean over the previous `days` days (aligned on df rows)."""
    data = df[[date_col, value_col]].dropna().sort_values(date_col)
    if data.empty:
        return pd.Series(index=df.index, dtype=float)
    rolled = data.set_index(date_col)[value_col].rolling(f"{days}D", min_periods=min_periods).mean()
    return pd.Series(rolled.to_numpy(), index=data.index).reindex(df.index)


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    """Mean of `values` weighted by `weights` (NaN values ignored)."""
    ok = values.notna() & weights.notna() & (weights > 0)
    return float(np.average(values[ok], weights=weights[ok])) if ok.any() else np.nan


def window_compare(
    df: pd.DataFrame,
    col: str,
    days: int = 28,
    date_col: str = "start_local",
    stat: str = "median",
    weight: str = "running_s",
):
    """(value over the last `days`, value over the `days` before, delta).

    stat: "median", "mean", or "wmean" (mean weighted by running time: the
    average over every running second of the window).
    """
    data = (
        df[[date_col, col, weight]].dropna(subset=[date_col, col]) if stat == "wmean" else df[[date_col, col]].dropna()
    )
    if data.empty:
        return None, None, None
    end = data[date_col].max()
    cur = data[data[date_col] > end - pd.Timedelta(days=days)]
    prev = data[
        (data[date_col] <= end - pd.Timedelta(days=days)) & (data[date_col] > end - pd.Timedelta(days=2 * days))
    ]
    if stat == "wmean":

        def agg(part):
            return weighted_mean(part[col], part[weight].fillna(0).clip(lower=1))
    elif stat == "median":

        def agg(part):
            return float(part[col].median())
    else:

        def agg(part):
            return float(part[col].mean())

    current = agg(cur) if len(cur) else None
    previous = agg(prev) if len(prev) else None
    delta = current - previous if current is not None and previous is not None else None
    return current, previous, delta


def period_labels(dates: pd.Series, n: int = 4) -> pd.Series:
    """Split dates into up to `n` consecutive periods of similar size, labelled in French."""
    dates = pd.to_datetime(dates)
    if dates.nunique() < n * 3:
        n = max(1, min(n, dates.nunique() // 3))
    ranks = dates.rank(method="first")
    groups = pd.qcut(ranks, q=n, labels=False) if n > 1 else pd.Series(0, index=dates.index)
    labels = {}
    for g in sorted(pd.Series(groups).dropna().unique()):
        part = dates[groups == g]
        a, b = part.min(), part.max()
        labels[g] = f"{FRENCH_MONTHS[a.month - 1]} {a.year} – {FRENCH_MONTHS[b.month - 1]} {b.year}"
    return pd.Series(groups, index=dates.index).map(labels)


# ------------------------------------------------------------- adjusted effect
@dataclass
class AdjustedEffect:
    outcome: str
    focus: str
    controls: list[str]
    coef: float
    ci_low: float
    ci_high: float
    p_value: float
    n: int
    n_groups: int | None
    r2: float
    formula: str
    coefficients: dict[str, float] = field(default_factory=dict)

    @property
    def direction(self) -> str:
        if self.ci_low > 0:
            return "up"
        if self.ci_high < 0:
            return "down"
        return "flat"


def adjusted_effect(
    df: pd.DataFrame,
    outcome: str,
    focus: str,
    controls: Sequence[str] = (),
    categorical: Sequence[str] = (),
    cluster: str | None = None,
    min_n: int = 15,
) -> AdjustedEffect | None:
    """OLS `outcome ~ focus + controls (+ C(categorical))`, effect of `focus`.

    `cluster`: column identifying groups of non-independent rows (activity id
    for kilometre splits) -> cluster-robust standard errors.
    """
    import statsmodels.formula.api as smf

    numeric = [outcome, focus, *controls]
    cols = numeric + list(categorical) + ([cluster] if cluster else [])
    data = df[cols].copy()
    for c in numeric:
        data[c] = pd.to_numeric(data[c], errors="coerce")
    data = data.dropna()
    usable_cats = [c for c in categorical if data[c].nunique() > 1]
    if len(data) < min_n or data[focus].nunique() < 3:
        return None
    terms = [focus, *controls, *(f"C({c})" for c in usable_cats)]
    formula = f"{outcome} ~ " + " + ".join(terms)
    model = smf.ols(formula, data=data)
    try:
        if cluster and data[cluster].nunique() >= 10:
            fit = model.fit(cov_type="cluster", cov_kwds={"groups": data[cluster].astype("int64")})
        else:
            fit = model.fit()
    except (ValueError, np.linalg.LinAlgError):
        return None
    ci = fit.conf_int().loc[focus]
    return AdjustedEffect(
        outcome=outcome,
        focus=focus,
        controls=[*controls, *usable_cats],
        coef=float(fit.params[focus]),
        ci_low=float(ci.iloc[0]),
        ci_high=float(ci.iloc[1]),
        p_value=float(fit.pvalues[focus]),
        n=int(fit.nobs),
        n_groups=int(data[cluster].nunique()) if cluster else None,
        r2=float(fit.rsquared),
        formula=formula,
        coefficients={k: float(v) for k, v in fit.params.items()},
    )


def mean_ci(values: pd.Series) -> tuple[float, float, float, int] | None:
    """Mean with 95 % t-interval: (mean, low, high, n)."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    if len(v) < 3:
        return None
    mean = float(v.mean())
    half = float(sps.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)))
    return mean, mean - half, mean + half, len(v)


# ------------------------------------------------------------ period summaries
PERIOD_FREQ = {"day": "D", "week": "W-SUN", "month": "M", "year": "Y"}


def aggregate_by_period(runs: pd.DataFrame, granularity: str) -> pd.DataFrame:
    """One row per day / week / month / year: volume, and run-weighted metrics.

    Cadence, speed and heart rate are weighted by running time (= the average
    over all running seconds of the period); stride follows from speed and cadence. `km::<family>` columns
    give the volume per session family (for the stacked volume chart).
    """
    if runs.empty:
        return pd.DataFrame(columns=["period", "n", "km", "hours", "cadence", "speed", "pace", "hr", "stride"])
    df = runs.copy()
    df["period"] = df["start_local"].dt.to_period(PERIOD_FREQ[granularity]).dt.start_time
    w = df["running_s"].fillna(0).clip(lower=1)
    df["_w"] = w
    df["_speed_w"] = df["avg_speed_mps"] * w
    df["_hr_w"] = df["hr_mean"] * w
    df["_w_speed"] = w.where(df["avg_speed_mps"].notna(), 0)
    df["_w_hr"] = w.where(df["hr_mean"].notna(), 0)
    df["_cad_w"] = df["cadence_mean"] * w
    df["_w_cad"] = w.where(df["cadence_mean"].notna(), 0)
    g = df.groupby("period")
    out = pd.DataFrame(
        {
            "n": g.size(),
            "km": g["distance_km"].sum(),
            "hours": g["duration_h"].sum(),
            # Average over every running second of the period (per-run medians are
            # whole numbers: watches record whole steps, so a median of medians is stuck).
            "cadence": g["_cad_w"].sum() / g["_w_cad"].sum().replace(0, np.nan),
            "speed": g["_speed_w"].sum() / g["_w_speed"].sum().replace(0, np.nan),
            "hr": g["_hr_w"].sum() / g["_w_hr"].sum().replace(0, np.nan),
        }
    )
    out["stride"] = out["speed"] / (out["cadence"] / 60)
    for col in ("hr_ref", "efficiency"):
        if col in df:
            out[col] = g[col].median()
    out["pace"] = 1000 / out["speed"]
    if "family" in df:
        fam = df.pivot_table(index="period", columns="family", values="distance_km", aggfunc="sum")
        for family in fam.columns:
            out[f"km::{family}"] = fam[family]
    return out.reset_index()
