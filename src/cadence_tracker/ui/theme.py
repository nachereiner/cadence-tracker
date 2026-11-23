"""Visual identity of Cadence Tracker: tokens, global CSS and branded components.

Concept "piste de nuit": the blue athletics track at night (navy surfaces, chalk
lane lines) and the amber digits of the finish-line race clock. Amber is the one
bold colour; it marks *your current value* (hero number, main series, primary
action). Everything else stays quiet.

See docs/specs/F11-identite-visuelle.md.
"""

from __future__ import annotations

import html
from pathlib import Path

import numpy as np
import streamlit as st

ASSETS = Path(__file__).parent / "assets"
LOGO = ASSETS / "logo.svg"
MARK = ASSETS / "mark.svg"

TOKENS = {
    "night": "#0B1624",  # page background: the track at night
    "track": "#122036",  # cards, inputs
    "raised": "#1A2B45",  # hover, table header
    "lane": "#24385A",  # borders and rules: lane lines
    "chalk": "#EAF0F7",  # primary text
    "mist": "#9FB0C6",  # secondary text
    "dim": "#7D90A8",  # axis labels, captions (5:1 on track)
    "chrono": "#FFB020",  # race-clock amber, the accent
    "good": "#45C98A",
    "bad": "#FF7B72",
}

DISPLAY_FONT = "'DIN Alternate', 'DIN Condensed', 'Avenir Next Condensed', 'Arial Narrow', sans-serif"
TEXT_FONT = "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"

CSS = f"""
<style>
:root {{
  --ct-night: {TOKENS["night"]}; --ct-track: {TOKENS["track"]}; --ct-raised: {TOKENS["raised"]};
  --ct-lane: {TOKENS["lane"]}; --ct-chalk: {TOKENS["chalk"]}; --ct-mist: {TOKENS["mist"]};
  --ct-dim: {TOKENS["dim"]}; --ct-chrono: {TOKENS["chrono"]}; --ct-good: {TOKENS["good"]}; --ct-bad: {TOKENS["bad"]};
  --ct-display: {DISPLAY_FONT};
}}
.block-container {{ max-width: 1240px; padding-top: 4.75rem; }}
h1, h2, h3, h4 {{ font-family: var(--ct-display) !important; letter-spacing: -0.01em; }}
h2 {{ font-size: 1.55rem !important; font-weight: 700 !important; }}
h3 {{ font-size: 1.25rem !important; }}
[data-testid="stMetricValue"] {{ font-family: var(--ct-display); }}
[data-testid="stCaptionContainer"] {{ color: var(--ct-dim); }}
button[kind="primary"], button[data-testid="stBaseButton-primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {{ color: var(--ct-night) !important; font-weight: 600; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: var(--ct-track); }}
/* No export anywhere: hide the table toolbar (CSV download) */
[data-testid="stElementToolbar"] {{ display: none !important; }}

/* Page header */
.ct-head h1 {{ font-size: clamp(1.9rem, 4vw, 2.6rem) !important; font-weight: 700; margin: 0; padding: 0; color: var(--ct-chalk); }}
.ct-head p {{ margin: .25rem 0 0; color: var(--ct-mist); font-size: .95rem; }}

/* Hero: the race clock */
.ct-board {{ display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 14px; margin: .5rem 0 1.25rem; }}
.ct-clock-card {{ background: var(--ct-track); border: 1px solid var(--ct-lane); border-radius: 18px; padding: 22px 24px;
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px 32px; align-items: end; }}
.ct-clock-label {{ grid-column: 1 / -1; align-self: start; color: var(--ct-mist); font-size: .95rem; }}
.ct-lane a {{ color: var(--ct-chrono); text-decoration: none; }}
.ct-clock {{ font-family: var(--ct-display); color: var(--ct-chrono); line-height: .85; white-space: nowrap; }}
.ct-clock .v {{ font-size: clamp(4.2rem, 9vw, 6.4rem); font-weight: 700; letter-spacing: -0.03em; }}
.ct-clock .u {{ font-size: 1.35rem; color: var(--ct-mist); margin-left: .35rem; letter-spacing: 0; }}
.ct-delta {{ font-size: .92rem; color: var(--ct-chalk); margin-top: 10px; }}
.ct-delta .up {{ color: var(--ct-good); }} .ct-delta .down {{ color: var(--ct-bad); }} .ct-delta .flat {{ color: var(--ct-mist); }}
.ct-strip {{ min-width: 0; }}
.ct-strip img {{ width: 100%; height: 58px; display: block; }}
.ct-strip .cap, .ct-lane .cap {{ color: var(--ct-dim); font-size: .8rem; margin-top: 6px; display: flex; flex-wrap: wrap; justify-content: space-between; gap: 2px 10px; }}
.ct-lane {{ grid-column: 1 / -1; margin-top: 12px; }}
.ct-lane-track {{ position: relative; height: 22px; border-top: 1px solid var(--ct-lane); border-bottom: 1px solid var(--ct-lane); }}
.ct-lane-track .fill {{ position: absolute; left: 0; top: 8px; height: 5px; border-radius: 3px; background: var(--ct-chrono); }}
.ct-lane-track .dot {{ position: absolute; top: 4px; width: 13px; height: 13px; margin-left: -6.5px; border-radius: 50%;
  background: var(--ct-chrono); box-shadow: 0 0 0 2px var(--ct-track); }}
.ct-lane-track .finish {{ position: absolute; right: 0; top: -4px; bottom: -4px; border-right: 2px dotted var(--ct-chalk); }}
.ct-tiles {{ display: grid; grid-template-rows: repeat(3, 1fr); gap: 14px; }}
.ct-tile {{ background: var(--ct-track); border: 1px solid var(--ct-lane); border-radius: 12px; padding: 12px 16px;
  display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: baseline; gap: 2px 12px; }}
.ct-tile .l {{ color: var(--ct-mist); font-size: .88rem; }}
.ct-tile .v {{ font-family: var(--ct-display); font-size: 1.9rem; font-weight: 700; color: var(--ct-chalk); text-align: right; }}
.ct-tile .v small {{ font-size: .95rem; color: var(--ct-mist); font-weight: 400; margin-left: .2rem; }}
.ct-tile .d {{ grid-column: 1 / -1; font-size: .82rem; color: var(--ct-dim); }}
.ct-tile .d .up {{ color: var(--ct-good); }} .ct-tile .d .down {{ color: var(--ct-bad); }}
.ct-board > *, .ct-clock-card > *, .ct-tiles > * {{ min-width: 0; }}
.ct-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(132px, 1fr)); gap: 10px; margin: .4rem 0 1rem; }}
.ct-stat {{ background: var(--ct-track); border: 1px solid var(--ct-lane); border-radius: 12px; padding: 10px 14px; min-width: 0; }}
.ct-stat .l {{ color: var(--ct-mist); font-size: .85rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.ct-stat .v {{ font-family: var(--ct-display); font-size: 1.7rem; font-weight: 700; color: var(--ct-chalk); white-space: nowrap; }}
.ct-stat .v small {{ font-size: .9rem; color: var(--ct-mist); font-weight: 400; margin-left: .2rem; }}
.ct-stat .d {{ font-size: .8rem; color: var(--ct-dim); }}
.ct-stat .d .up {{ color: var(--ct-good); }} .ct-stat .d .down {{ color: var(--ct-bad); }}
.ct-stat.hero .v {{ color: var(--ct-chrono); }}
@media (max-width: 760px) {{
  .ct-board {{ grid-template-columns: 1fr; }}
  .ct-clock-card {{ grid-template-columns: 1fr; padding: 18px; }}
  .ct-tiles {{ grid-template-rows: none; }}
}}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; animation: none !important; }} }}
</style>
"""


def inject() -> None:
    """Global CSS (call once per run, from app.py)."""
    st.html(CSS)


def page_header(title: str, subtitle: str | None = None) -> None:
    sub = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    st.html(f'<div class="ct-head"><h1>{html.escape(title)}</h1>{sub}</div>')


def _fmt(value: float | None, decimals: int = 0) -> str:
    if value is None or not np.isfinite(value):
        return "–"
    return f"{value:.{decimals}f}".replace(".", ",")


def _delta(value: float | None, unit: str, good_when: str = "up", decimals: int = 1, suffix: str = "") -> str:
    """Arrow + signed value; colour carries good/bad, the arrow and the words carry direction."""
    if value is None or not np.isfinite(value) or round(value, decimals) == 0:
        return f'<span class="flat">= stable</span>{suffix}' if value is not None else "&nbsp;"
    arrow = "▲" if value > 0 else "▼"
    good = (value > 0) == (good_when == "up")
    text = f"{value:+.{decimals}f}".replace(".", ",").replace("-", "−")
    return f'<span class="{"up" if good else "down"}">{arrow} {text} {unit}</span>{suffix}'


def _svg_img(svg: str, alt: str) -> str:
    """st.html sanitises inline <svg>; an <img> with a data URI survives it."""
    import base64

    data = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f'<img src="data:image/svg+xml;base64,{data}" alt="{html.escape(alt)}" title="{html.escape(alt)}">'


def tick_strip(values: list[float | None], labels: list[str]) -> str:
    """Weekly medians as metronome ticks: the last (current) tick is amber."""
    vals = [v if v is not None and np.isfinite(v) else None for v in values]
    present = [v for v in vals if v is not None]
    if not present:
        return ""
    lo, hi = min(present) - 2, max(present) + 1
    n, w, gap, h = len(vals), 100.0, 2.4, 58.0
    bw = (w - gap * (n - 1)) / n
    bars = []
    for i, (v, label) in enumerate(zip(vals, labels, strict=True)):
        x = i * (bw + gap)
        if v is None:
            bars.append(f'<rect x="{x:.2f}" y="{h - 2:.2f}" width="{bw:.2f}" height="2" fill="{TOKENS["lane"]}"/>')
            continue
        bh = max(4.0, (v - lo) / (hi - lo) * (h - 6))
        color = TOKENS["chrono"] if i == n - 1 else TOKENS["mist"]
        opacity = 1 if i == n - 1 else 0.42
        bars.append(
            f'<rect x="{x:.2f}" y="{h - bh:.2f}" width="{bw:.2f}" height="{bh:.2f}" rx="1.2" fill="{color}" opacity="{opacity}">'
            f"<title>{html.escape(label)} : {_fmt(v, 1)} pas/min</title></rect>"
        )
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 {h:.0f}" preserveAspectRatio="none">{"".join(bars)}</svg>'
    return _svg_img(svg, "Cadence moyenne des 12 dernières semaines")


def lane_progress(baseline: float, current: float, target: float) -> str:
    """A running lane from the starting point to the goal, with your position on it (pure CSS)."""
    span = target - baseline
    pos = 0.0 if span == 0 else min(max((current - baseline) / span, 0.0), 1.0)
    return (
        f'<div class="ct-lane-track" role="img" aria-label="Progression vers l\'objectif : {pos:.0%}">'
        f'<div class="fill" style="width:{pos * 100:.1f}%"></div><div class="dot" style="left:{pos * 100:.1f}%"></div>'
        '<div class="finish"></div></div>'
    )


def scoreboard(
    *,
    cadence: float | None,
    cadence_delta: float | None,
    weekly: list[float | None],
    weekly_labels: list[str],
    goal: tuple[float, float, float] | str | None,
    tiles: list[tuple[str, str, str, str]],
) -> None:
    """Dashboard hero: race-clock cadence + quiet side tiles.

    tiles: (label, value, unit, delta_html).
    """
    lane = (
        '<div class="ct-lane"><div class="cap"><span>Pas encore d\'objectif de cadence. '
        '<a href="objectif-cadence" target="_self">Définir un objectif</a> pour suivre votre progression.</span></div></div>'
    )
    if isinstance(goal, str):
        lane = f'<div class="ct-lane"><div class="cap"><span>{html.escape(goal)}</span></div></div>'
    elif goal:
        base, cur, target = goal
        progress = 0 if target == base else (cur - base) / (target - base) * 100
        lane = (
            f'<div class="ct-lane">{lane_progress(base, cur, target)}'
            f'<div class="cap"><span>Départ {_fmt(base, 1)}</span>'
            f"<span>{_fmt(progress)} % du chemin</span><span>Objectif {_fmt(target)}</span></div></div>"
        )
    strip = tick_strip(weekly, weekly_labels)
    strip_html = (
        f'<div class="ct-strip">{strip}<div class="cap"><span>12 semaines</span><span>cette semaine</span></div></div>'
        if strip
        else ""
    )
    tiles_html = "".join(
        f'<div class="ct-tile"><span class="l">{html.escape(label)}</span><span class="v">{value}<small>{unit}</small></span>'
        f'<span class="d">{delta}</span></div>'
        for label, value, unit, delta in tiles
    )
    st.html(
        f"""
<div class="ct-board">
  <div class="ct-clock-card">
    <div class="ct-clock-label">Cadence moyenne des 4 dernières semaines, hors marche et arrêts</div>
    <div>
      <div class="ct-clock"><span class="v">{_fmt(cadence, 1)}</span><span class="u">pas/min</span></div>
      <div class="ct-delta">{_delta(cadence_delta, "pas/min", suffix=" par rapport aux 4 semaines précédentes")}</div>
    </div>
    {strip_html}
    {lane}
  </div>
  <div class="ct-tiles">{tiles_html}</div>
</div>"""
    )


def stat_row(items: list[tuple]) -> None:
    """Compact stats that wrap on small screens.

    items: (label, value, unit[, sub_html[, hero]]) — `hero` paints the value amber.
    """
    cells = []
    for item in items:
        label, value, unit, *rest = item
        sub = rest[0] if rest else ""
        hero = rest[1] if len(rest) > 1 else False
        cls = "ct-stat hero" if hero else "ct-stat"
        sub_html = f'<div class="d">{sub}</div>' if sub else ""
        cells.append(
            f'<div class="{cls}"><div class="l" title="{html.escape(label)}">{html.escape(label)}</div>'
            f'<div class="v">{value}<small>{unit}</small></div>{sub_html}</div>'
        )
    st.html(f'<div class="ct-stats">{"".join(cells)}</div>')


def lane_block(baseline: float, current: float, target: float) -> None:
    """Standalone lane progress (goal page)."""
    progress = 0 if target == baseline else (current - baseline) / (target - baseline) * 100
    st.html(
        f'<div class="ct-lane" style="margin: 0 0 1rem">{lane_progress(baseline, current, target)}'
        f'<div class="cap"><span>Départ {_fmt(baseline, 1)}</span><span>Aujourd\'hui {_fmt(current, 1)}, {_fmt(progress)} % du chemin</span>'
        f"<span>Objectif {_fmt(target)}</span></div></div>"
    )


delta_html = _delta
fmt = _fmt
