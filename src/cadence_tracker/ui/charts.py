"""Plotly figure builders (pure functions: data in, figure out).

Visual rules (docs/specs/F04-tableau-de-bord.md, "Règles visuelles"):
* palette validated for colour-vision deficiency, light and dark variants;
* at most 3 categorical colours in a scatter; ordered periods use 3 distinct hues
  (blue -> pink -> amber), the most recent always amber;
* thin marks (2 px lines, >= 8 px markers ringed with the surface colour),
  hairline solid grid, no dual axis; model lines (trends) are dashed;
* every chart has hover tooltips; period summaries are in the hover of the
  evolution chart (they replace the former weekly/monthly tables).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from cadence_tracker.analysis.stats import Trend, period_labels
from cadence_tracker.units import format_pace

# "Piste de nuit" chart palette (docs/specs/F11-identite-visuelle.md).
# Categorical c1-c3 (also used, in another order, for periods) pass scripts/validate_palette.js against
# the card surface #122036 (all-pairs, dark mode). `s1` (bright race-clock amber)
# is reserved for single-series charts: it marks "your value".
NIGHT = {
    "surface": "#0B1624",  # page background, also used as marker ring
    "ink": "#EAF0F7",  # chalk: rolling means, emphasis lines
    "ink2": "#9FB0C6",  # mist: secondary lines and text
    "muted": "#7D90A8",  # axis labels
    "grid": "#1B2C45",
    "axis": "#24385A",
    "s1": "#FFB020",
    "c1": "#C28400",  # amber (validated categorical step)
    "c2": "#3B8EE6",  # lane blue
    "c3": "#D9628F",  # bib pink
    "model": "#9FB0C6",  # trend / model lines (dashed)
    "target": "#EAF0F7",  # goal line (dotted)
    # Ordered periods, oldest -> most recent. A one-hue amber ramp was too hard to
    # tell apart (normal-vision ΔE 10.6 < 15); no 4-colour set passes all pairs,
    # hence 3 periods with the validated categorical hues, the latest in amber.
    "periods": ["#3B8EE6", "#D9628F", "#C28400"],
    "area": "rgba(159,176,198,0.14)",
    "good": "#45C98A",
    "hover": "#1A2B45",
    # Comparison lines, validated in this order (adjacent pairs, dark surface).
    "lines": ["#C28400", "#3B8EE6", "#D9628F", "#9085E9", "#199E70"],
}
PALETTES = {"dark": NIGHT}

FAMILY_ORDER = ["Endurance & sorties longues", "Qualité (seuil, fractionné)", "Trail & autres"]
FAMILY_SLOT = dict(zip(FAMILY_ORDER, ["c1", "c2", "c3"], strict=True))
FAMILY_SYMBOL = dict(zip(FAMILY_ORDER, ["circle", "diamond", "triangle-up"], strict=True))
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
DISPLAY = "'DIN Alternate', 'DIN Condensed', 'Avenir Next Condensed', sans-serif"


def layout(fig: go.Figure, P: dict, height: int = 380, legend: bool = True) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=12, r=12, t=40 if legend else 16, b=12),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=P["ink2"], size=13),
        hoverlabel=dict(font=dict(family=FONT, size=13, color=P["ink"]), bgcolor=P["hover"], bordercolor=P["axis"]),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None, font=dict(color=P["ink2"])
        ),
        showlegend=legend,
        dragmode="zoom",
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=P["axis"],
        tickcolor=P["axis"],
        ticks="outside",
        zeroline=False,
        tickfont=dict(color=P["muted"]),
        automargin=True,
    )
    fig.update_yaxes(
        gridcolor=P["grid"],
        gridwidth=1,
        zeroline=False,
        linecolor=P["axis"],
        tickfont=dict(color=P["muted"]),
        automargin=True,
        title_standoff=8,
    )
    return fig


FR_MONTHS_LONG = [
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
]
FR_MONTHS_SHORT = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."]


def french_month_axis(fig: go.Figure, dates, row=None, col=None) -> None:
    """Plotly ships English month names only: place one French label per month."""
    d = pd.to_datetime(pd.Series(dates)).dropna()
    if d.empty:
        return
    months = pd.date_range(d.min().to_period("M").to_timestamp(), d.max(), freq="MS")
    if len(months) == 0:
        return
    step = max(1, int(np.ceil(len(months) / 8)))
    months = months[::step]
    text = [
        f"{FR_MONTHS_SHORT[m.month - 1]} {m:%y}" if (i == 0 or m.month == 1) else FR_MONTHS_SHORT[m.month - 1]
        for i, m in enumerate(months)
    ]
    fig.update_xaxes(tickvals=list(months), ticktext=text, row=row, col=col)


def pace_ticks(values: pd.Series, max_ticks: int = 6) -> tuple[list[float], list[str]]:
    """Readable min/km ticks: the smallest round step giving at most `max_ticks` ticks."""
    v = pd.to_numeric(values, errors="coerce").dropna()
    v = v[(v > 120) & (v < 1200)]
    if v.empty:
        return [], []
    lo, hi = v.quantile(0.01), v.quantile(0.99)
    step = next((s for s in (10, 15, 20, 30, 60, 120) if (hi - lo) / s <= max_ticks - 1), 180)
    ticks = np.arange(np.floor(lo / step) * step, np.ceil(hi / step) * step + 1, step)
    return ticks.tolist(), [format_pace(t) for t in ticks]


def apply_pace_axis(fig, values, axis: str = "y", row=None, col=None) -> None:
    tickvals, ticktext = pace_ticks(values)
    kwargs = dict(tickvals=tickvals, ticktext=ticktext, autorange="reversed")
    if axis == "y":
        fig.update_yaxes(row=row, col=col, **kwargs)
    else:
        fig.update_xaxes(row=row, col=col, **kwargs)


def _marker(color: str, P: dict, size: int = 9, symbol: str = "circle", opacity: float = 0.85) -> dict:
    return dict(color=color, size=size, symbol=symbol, opacity=opacity, line=dict(color=P["surface"], width=1.5))


def _hover_activity(df: pd.DataFrame) -> tuple[np.ndarray, str]:
    custom = np.column_stack(
        [
            df["start_local"].dt.strftime("%d/%m/%Y"),
            df["title"],
            df["type_label"],
            df["distance_km"].map(lambda v: f"{v:.1f}".replace(".", ",")),
            df["pace_s_km"].map(format_pace),
            df["cadence_mean"].map(lambda v: f"{v:.1f}".replace(".", ",") if pd.notna(v) else "–"),
            df["hr_mean"].map(lambda v: f"{v:.0f}" if pd.notna(v) else "–"),
            df["id"],
        ]
    )
    template = (
        "<b>%{customdata[1]}</b><br>%{customdata[0]}, %{customdata[2]}<br>"
        "%{customdata[3]} km à %{customdata[4]} /km<br>Cadence %{customdata[5]} pas/min, FC %{customdata[6]} bpm"
        "<extra></extra>"
    )
    return custom, template


# ------------------------------------------------------------------ dashboard
METRICS = {
    "cadence_mean": ("Cadence moyenne, hors marche et arrêts", "pas/min", False),
    "pace_s_km": ("Allure moyenne", "min/km", True),
    "hr_mean": ("FC moyenne", "bpm", False),
    "stride_m": ("Longueur de pas", "m", False),
    "hr_ref": ("FC à allure de référence, sur le plat", "bpm", False),
    "efficiency": ("Efficacité brute (vitesse / FC)", "m/min par bpm", False),
}
# Plotly period of a bar/point, used to centre it on its week/month/year.
X_PERIOD = {"day": 86_400_000, "week": 7 * 86_400_000, "month": "M1", "year": "M12"}


def _runs_trace(fig, data: pd.DataFrame, col: str, P: dict, opacity: float, row=None, legend: bool = True) -> None:
    """One point per run, coloured and shaped by session family."""
    for family in FAMILY_ORDER:
        part = data[data["family"] == family]
        if part.empty:
            continue
        custom, template = _hover_activity(part)
        fig.add_trace(
            go.Scatter(
                x=part["start_local"],
                y=part[col],
                mode="markers",
                name=family,
                legendgroup=family,
                showlegend=legend,
                marker=_marker(P[FAMILY_SLOT[family]], P, symbol=FAMILY_SYMBOL[family], opacity=opacity),
                customdata=custom,
                hovertemplate=template,
            ),
            row=row,
            col=1 if row else None,
        )


def _period_hover(table: pd.DataFrame, granularity: str) -> tuple[np.ndarray, str]:
    def label(ts):
        if granularity == "week":
            return f"Semaine du {ts:%d/%m/%Y}"
        if granularity == "month":
            return f"{FR_MONTHS_LONG[ts.month - 1]} {ts.year}"
        if granularity == "year":
            return f"{ts.year}"
        return f"{ts:%d/%m/%Y}"

    def num(v, d=0):
        return "–" if pd.isna(v) else f"{v:.{d}f}".replace(".", ",")

    custom = np.column_stack(
        [
            table["period"].map(label),
            table["n"],
            table["km"].map(lambda v: num(v, 1)),
            table["hours"].map(lambda h: f"{int(h)}h{int(round(h % 1 * 60)):02d}"),
            table["cadence"].map(lambda v: num(v, 1)),
            table["speed"].map(lambda v: format_pace(1000 / v) if pd.notna(v) and v > 0 else "–"),
            table["hr"].map(num),
            table["stride"].map(lambda v: num(v, 2)),
        ]
    )
    template = (
        "<b>%{customdata[0]}</b><br>%{customdata[1]} sorties, %{customdata[2]} km en %{customdata[3]}<br>"
        "Cadence %{customdata[4]} pas/min, allure %{customdata[5]} /km<br>FC %{customdata[6]} bpm, "
        "pas %{customdata[7]} m<extra></extra>"
    )
    return custom, template


def evolution(
    runs: pd.DataFrame,
    table: pd.DataFrame,
    col: str,
    granularity: str,
    P: dict,
    rolling: pd.Series | None = None,
    trend: Trend | None = None,
    target: float | None = None,
    height: int = 640,
) -> go.Figure:
    """Central chart: the chosen indicator (top) and the volume by session family (bottom).

    `runs`: one row per run; `table`: per-period aggregates (stats.aggregate_by_period),
    whose hover replaces the former weekly and monthly tables.
    """
    label, unit, is_pace = METRICS.get(col, (col, "", False))
    data = runs.dropna(subset=[col]).sort_values("start_local")
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.68, 0.32],
        vertical_spacing=0.07,
        subplot_titles=(f"{label} ({unit})", "Volume (km)"),
    )
    aggregated = granularity != "day"
    _runs_trace(fig, data, col, P, opacity=0.35 if aggregated else 0.85, row=1)
    if aggregated and not table.empty:
        agg_col = {"cadence_mean": "cadence", "pace_s_km": "pace", "hr_mean": "hr", "stride_m": "stride"}.get(col, col)
        custom, template = _period_hover(table, granularity)
        name = {"week": "Par semaine", "month": "Par mois", "year": "Par année"}[granularity]
        fig.add_trace(
            go.Scatter(
                x=table["period"],
                y=table[agg_col],
                mode="lines+markers",
                name=name,
                xperiod=X_PERIOD[granularity],
                xperiodalignment="middle",
                line=dict(color=P["ink"], width=2.5),
                marker=dict(size=7, color=P["ink"], line=dict(color=P["surface"], width=1.5)),
                customdata=custom,
                hovertemplate=template,
                connectgaps=False,
            ),
            row=1,
            col=1,
        )
    elif rolling is not None:
        r = pd.DataFrame({"x": data["start_local"], "y": rolling.reindex(data.index)}).dropna()
        fig.add_trace(
            go.Scatter(
                x=r["x"],
                y=r["y"],
                mode="lines",
                name="Moyenne glissante 4 semaines",
                line=dict(color=P["ink"], width=2.5, shape="spline", smoothing=0.6),
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )
    if trend is not None and len(data) > 1:
        xs = pd.to_datetime([data["start_local"].min(), data["start_local"].max()])
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=trend.predict(xs),
                mode="lines",
                name="Tendance linéaire",
                line=dict(color=P["model"], width=2, dash="dash"),
                hoverinfo="skip",
            ),
            row=1,
            col=1,
        )
    if target:
        fig.add_hline(
            y=target,
            row=1,
            col=1,
            line=dict(color=P["target"], width=1.5, dash="dot"),
            annotation_text=f"Objectif {target:.0f}",
            annotation_position="top left",
            annotation_font_color=P["ink2"],
        )
    # Volume, stacked by session family (same colours as the points).
    if not table.empty:
        for family in FAMILY_ORDER:
            km_col = f"km::{family}"
            if km_col not in table or table[km_col].fillna(0).sum() == 0:
                continue
            fig.add_trace(
                go.Bar(
                    x=table["period"],
                    y=table[km_col],
                    name=family,
                    legendgroup=family,
                    showlegend=False,
                    xperiod=X_PERIOD[granularity],
                    xperiodalignment="middle",
                    marker=dict(color=P[FAMILY_SLOT[family]], line=dict(width=0)),
                    hovertemplate=f"{family}<br>%{{y:.1f}} km<extra></extra>",
                ),
                row=2,
                col=1,
            )
    layout(fig, P, height)
    fig.update_layout(barmode="stack", bargap=0.15, hovermode="closest")
    fig.update_annotations(font=dict(size=13, color=P["ink2"]), x=0, xanchor="left")
    if is_pace:
        apply_pace_axis(fig, pd.concat([data[col], table.get("pace", pd.Series(dtype=float))]), row=1, col=1)
    dates = data["start_local"] if not data.empty else table["period"]
    if granularity == "year":
        years = sorted({d.year for d in pd.to_datetime(dates)})
        fig.update_xaxes(
            tickvals=[pd.Timestamp(year=y, month=7, day=1) for y in years],
            ticktext=[str(y) for y in years],
            row=2,
            col=1,
        )
    else:
        french_month_axis(fig, dates, row=2, col=1)
    return fig


def runs_over_time(
    runs: pd.DataFrame,
    col: str,
    P: dict,
    rolling: pd.Series | None = None,
    trend: Trend | None = None,
    height: int = 380,
) -> go.Figure:
    """Single-panel version (one point per run), used by the questions page."""
    label, unit, _ = METRICS.get(col, (col, "", False))
    data = runs.dropna(subset=[col]).sort_values("start_local")
    fig = go.Figure()
    _runs_trace(fig, data, col, P, opacity=0.85)
    if rolling is not None:
        r = pd.DataFrame({"x": data["start_local"], "y": rolling.reindex(data.index)}).dropna()
        fig.add_trace(
            go.Scatter(
                x=r["x"],
                y=r["y"],
                mode="lines",
                name="Moyenne glissante 4 semaines",
                line=dict(color=P["ink"], width=2.5, shape="spline", smoothing=0.6),
                hoverinfo="skip",
            )
        )
    if trend is not None and len(data) > 1:
        xs = pd.to_datetime([data["start_local"].min(), data["start_local"].max()])
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=trend.predict(xs),
                mode="lines",
                name="Tendance linéaire",
                line=dict(color=P["model"], width=2, dash="dash"),
                hoverinfo="skip",
            )
        )
    layout(fig, P, height)
    fig.update_yaxes(title=dict(text=f"{label} ({unit})", font=dict(color=P["muted"])))
    french_month_axis(fig, data["start_local"])
    return fig


# ---------------------------------------------------------------- correlations
def scatter_by_period(
    df: pd.DataFrame,
    x: str,
    y: str,
    P: dict,
    x_label: str,
    y_label: str,
    n_periods: int = 3,
    pace_x: bool = False,
    pace_y: bool = False,
    height: int = 420,
    hover_extra: str = "",
) -> go.Figure:
    """Scatter coloured by consecutive periods (`P["periods"]`) with one fitted line per period.

    If the lines of later periods sit above earlier ones, y increased at equal x.
    """
    data = df.dropna(subset=[x, y]).copy()
    fig = go.Figure()
    if data.empty:
        return layout(fig, P, height)
    data["period"] = period_labels(data["start_local"], n_periods)
    order = data.groupby("period")["start_local"].min().sort_values().index.tolist()
    # Right-aligned so that the most recent period is always amber.
    colors = P["periods"][-len(order) :]
    for color, period in zip(colors, order, strict=True):
        part = data[data["period"] == period]
        fig.add_trace(
            go.Scatter(
                x=part[x],
                y=part[y],
                mode="markers",
                name=period,
                legendgroup=period,
                marker=dict(color=color, size=7, opacity=0.55, line=dict(width=0)),
                hovertemplate=f"{period}<br>{x_label} : %{{x:.1f}}<br>{y_label} : %{{y:.1f}}{hover_extra}<extra></extra>",
            )
        )
        if len(part) >= 8 and part[x].nunique() > 2:
            slope, intercept = np.polyfit(part[x], part[y], 1)
            xs = np.quantile(part[x], [0.05, 0.95])
            fig.add_trace(
                go.Scatter(
                    x=xs,
                    y=intercept + slope * xs,
                    mode="lines",
                    legendgroup=period,
                    showlegend=False,
                    line=dict(color=color, width=3),
                    hoverinfo="skip",
                )
            )
    layout(fig, P, height)
    fig.update_xaxes(title=dict(text=x_label, font=dict(color=P["muted"])))
    fig.update_yaxes(title=dict(text=y_label, font=dict(color=P["muted"])))
    if pace_x:
        apply_pace_axis(fig, data[x], axis="x")
    if pace_y:
        apply_pace_axis(fig, data[y], axis="y")
    return fig


def value_over_time_with_zero(df: pd.DataFrame, col: str, P: dict, y_label: str, height: int = 320) -> go.Figure:
    """Per-activity value over time with a zero reference (drift / fatigue)."""
    data = df.dropna(subset=[col]).sort_values("start_local")
    fig = go.Figure()
    if not data.empty:
        custom, template = _hover_activity(data)
        fig.add_trace(
            go.Scatter(
                x=data["start_local"],
                y=data[col],
                mode="markers",
                name=y_label,
                marker=_marker(P["s1"], P),
                customdata=custom,
                hovertemplate=template.replace("<extra></extra>", f"<br>{y_label} : %{{y:+.1f}}<extra></extra>"),
            )
        )
    fig.add_hline(y=0, line=dict(color=P["axis"], width=1.5))
    layout(fig, P, height, legend=False)
    fig.update_yaxes(title=dict(text=y_label, font=dict(color=P["muted"])))
    french_month_axis(fig, data["start_local"])
    return fig


# ------------------------------------------------------------------ comparison
def compare_overlay(runs: list[tuple[pd.DataFrame, str]], P: dict, smoothing: int = 30, height: int = 660) -> go.Figure:
    """Up to 5 runs overlaid on a distance axis (cadence, pace, HR)."""
    panels = [("Cadence (pas/min)", "cadence_spm"), ("Allure (min/km)", "pace"), ("FC (bpm)", "heart_rate")]
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=[p[0] for p in panels])
    all_pace = []
    for (g, label), color in zip(runs, P["lines"], strict=False):
        d = g[g["moving"]].copy()
        km = d["distance_m"] / 1000
        cad = d["cadence_spm"].where(d["running"]).rolling(smoothing, center=True, min_periods=1).mean()
        pace = 1000 / d["speed_mps"].rolling(smoothing, center=True, min_periods=1).mean()
        pace = pace.where(pace < 900)
        all_pace.append(pace)
        hr = d["heart_rate"].rolling(max(1, smoothing // 3), center=True, min_periods=1).mean()
        for row, series in enumerate((cad, pace, hr), start=1):
            fig.add_trace(
                go.Scatter(
                    x=km,
                    y=series,
                    mode="lines",
                    name=label,
                    legendgroup=label,
                    showlegend=row == 1,
                    line=dict(color=color, width=2),
                    customdata=series.map(format_pace) if row == 2 else None,
                    hovertemplate=(
                        f"{label} : %{{customdata}} /km<extra></extra>"
                        if row == 2
                        else f"{label} : %{{y:.0f}}<extra></extra>"
                    ),
                ),
                row=row,
                col=1,
            )
    if all_pace:
        apply_pace_axis(fig, pd.concat(all_pace), row=2, col=1)
    layout(fig, P, height)
    fig.update_layout(hovermode="x unified", hoversubplots="axis")
    fig.update_annotations(font=dict(size=13, color=P["ink2"]), x=0, xanchor="left")
    fig.update_xaxes(title=dict(text="Distance (km)", font=dict(color=P["muted"])), row=3, col=1)
    return fig


# ------------------------------------------------------------------ goal view
def goal_projection(runs: pd.DataFrame, rolling: pd.Series, status, P: dict, height: int = 460) -> go.Figure:
    """Adjusted cadence of the runs considered, 4-week mean, trend, and projection to the goal."""
    from cadence_tracker.analysis.stats import DAYS_PER_MONTH

    fig = go.Figure()
    data = runs.dropna(subset=["cadence_adjusted"]).sort_values("start_local")
    _runs_trace(fig, data, "cadence_adjusted", P, opacity=0.75)
    r = pd.DataFrame({"x": data["start_local"], "y": rolling.reindex(data.index)}).dropna()
    if not r.empty:
        fig.add_trace(
            go.Scatter(
                x=r["x"],
                y=r["y"],
                mode="lines",
                name="Moyenne glissante 4 semaines",
                line=dict(color=P["ink"], width=2.5, shape="spline", smoothing=0.6),
                hovertemplate="Moyenne 4 sem. : %{y:.1f}<extra></extra>",
            )
        )
    trend = status.trend
    if trend is not None and status.current is not None and status.last_date is not None:
        xs = pd.to_datetime([trend.origin, status.last_date])
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=trend.predict(xs),
                mode="lines",
                name="Tendance depuis le début",
                line=dict(color=P["model"], width=2, dash="dash"),
                hoverinfo="skip",
            )
        )
        # Projection from today's level, with the 95 % interval of the rhythm as a cone.
        horizon_end = pd.Timestamp(status.eta) if status.eta else status.last_date + pd.Timedelta(days=183)
        horizon_end = max(horizon_end, status.last_date + pd.Timedelta(days=60))
        months = (horizon_end - status.last_date).days / DAYS_PER_MONTH
        x_proj = [status.last_date, horizon_end]
        hi = [status.current, status.current + trend.ci_high * months]
        lo = [status.current, status.current + trend.ci_low * months]
        fig.add_trace(
            go.Scatter(
                x=x_proj + x_proj[::-1],
                y=hi + lo[::-1],
                mode="lines",
                fill="toself",
                fillcolor="rgba(255,176,32,0.12)",
                line=dict(width=0),
                name="Fourchette (IC 95 %)",
                hoverinfo="skip",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=x_proj,
                y=[status.current, status.current + trend.slope_per_month * months],
                mode="lines",
                name="Projection",
                line=dict(color=P["s1"], width=2.5, dash="dash"),
                hovertemplate="Projection : %{y:.1f} pas/min<extra></extra>",
            )
        )
    if status.target:
        fig.add_hline(
            y=status.target,
            line=dict(color=P["target"], width=1.5, dash="dot"),
            annotation_text=f"Objectif {status.target:.0f} pas/min",
            annotation_position="top left",
            annotation_font_color=P["ink2"],
        )
    if status.eta:
        fig.add_vline(x=pd.Timestamp(status.eta).value / 1e6, line=dict(color=P["s1"], width=1.5, dash="dot"))
        fig.add_annotation(
            x=pd.Timestamp(status.eta),
            y=status.target,
            text=f"vers {FR_MONTHS_LONG[status.eta.month - 1]} {status.eta.year}",
            showarrow=False,
            yshift=14,
            font=dict(color=P["s1"], size=13),
        )
    layout(fig, P, height)
    fig.update_yaxes(title=dict(text="Cadence ajustée à l'allure de référence (pas/min)", font=dict(color=P["muted"])))
    if not data.empty:  # keep the scale readable even if the uncertainty cone is wide
        top = max(data["cadence_adjusted"].max(), status.target or 0) + 4
        fig.update_yaxes(range=[data["cadence_adjusted"].min() - 4, top])
    end = pd.Timestamp(status.eta) if status.eta else (data["start_local"].max() if not data.empty else None)
    french_month_axis(
        fig, pd.concat([data["start_local"], pd.Series([end])]) if end is not None else data["start_local"]
    )
    return fig
