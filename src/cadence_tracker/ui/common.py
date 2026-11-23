"""Shared UI helpers: connection, cached data, the page header with its
Route/Trail switch and session-type filter, the date range, formatting.

Filter widgets use `persist_state="session"`, so every page works on the same
slice of data and the choice survives navigation (docs/specs/F04).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from cadence_tracker import config
from cadence_tracker.analysis.classification import SESSION_TYPES
from cadence_tracker.models import SUB_SPORT_LABELS
from cadence_tracker.storage import db
from cadence_tracker.storage import repository as repo
from cadence_tracker.units import format_duration, format_pace

MODES = {"road": "Route", "trail": "Trail"}
# In road mode the "Trail" type is meaningless (trail runs live in trail mode).
ROAD_TYPES = ["ef", "long", "intervals", "tempo", "other"]
# Selected by default: comparable, easy efforts (the user can add the others).
DEFAULT_TYPES = ["ef", "long"]
SESSION_FAMILIES = {
    "ef": "Endurance & sorties longues",
    "long": "Endurance & sorties longues",
    "intervals": "Qualité (seuil, fractionné)",
    "tempo": "Qualité (seuil, fractionné)",
    "trail": "Trail & autres",
    "other": "Trail & autres",
}
PAGES: dict[str, st.Page] = {}  # filled by app.py, used for links and st.switch_page


# ------------------------------------------------------------------ data access
@st.cache_resource
def _connection(path: str):
    return db.connect(path)


def conn():
    return _connection(str(config.db_path()))


def data_version() -> tuple:
    """Cheap fingerprint of the database content, used as cache key."""
    row = (
        conn()
        .execute(
            "SELECT COUNT(*), MAX(a.updated_at), MAX(m.computed_at), "
            "(SELECT value FROM settings WHERE key = 'analysis') FROM activities a "
            "LEFT JOIN activity_metrics m ON m.activity_id = a.id"
        )
        .fetchone()
    )
    return tuple(row)


@st.cache_data(show_spinner=False)
def _load_activities(path: str, version: tuple) -> pd.DataFrame:
    df = repo.load_activities(_connection(path))
    if df.empty:
        return df
    df["pace_s_km"] = 1000 / df["avg_speed_mps"]
    df["distance_km"] = df["distance_m"] / 1000
    df["duration_h"] = df["elapsed_s"] / 3600
    df["type_label"] = df["session_type"].map(SESSION_TYPES).fillna("Autre")
    df["family"] = df["session_type"].map(SESSION_FAMILIES).fillna("Trail & autres")
    df["terrain_label"] = df["sub_sport"].map(SUB_SPORT_LABELS).fillna("Route")
    # Trail mode = trail terrain, or a run classified as trail (hilly, or named so).
    df["is_trail"] = (df["sub_sport"] == "trail") | (df["session_type"] == "trail")
    df["title"] = df["name"].fillna("Course")
    df["label"] = (
        df["start_local"].dt.strftime("%d/%m/%Y")
        + ", "
        + df["title"]
        + ", "
        + df["distance_km"].map(lambda v: f"{v:.1f} km".replace(".", ",") if pd.notna(v) else "")
    )
    return df


def activities() -> pd.DataFrame:
    """All activities (including excluded ones) with display helpers."""
    return _load_activities(str(config.db_path()), data_version())


@st.cache_data(show_spinner=False)
def _load_splits(path: str, version: tuple) -> pd.DataFrame:
    return repo.load_splits(_connection(path))


def splits() -> pd.DataFrame:
    return _load_splits(str(config.db_path()), data_version())


def settings() -> config.Settings:
    return repo.load_settings(conn())


def is_demo() -> bool:
    return bool(repo.get_flag(conn(), "is_demo"))


def invalidate() -> None:
    """Call after any write so cached frames are rebuilt."""
    st.cache_data.clear()


# --------------------------------------------------------------------- filters
def mode() -> str:
    return st.session_state.get("f_mode") or "road"


def in_mode(df: pd.DataFrame, current: str | None = None) -> pd.DataFrame:
    """Runs of the current mode (trail runs, or everything else), excluded runs removed."""
    if df.empty:
        return df
    current = current or mode()
    out = df[~df["excluded"]]
    return out[out["is_trail"]] if current == "trail" else out[~out["is_trail"]]


def page_header(
    title: str,
    *,
    with_types: bool = True,
    types_key: str = "f_types",
    types_default: list[str] | None = None,
) -> pd.DataFrame:
    """Title + Route/Trail switch (+ session-type filter in road mode).

    Returns the runs of the current mode, filtered by type, excluded runs removed.
    """
    from cadence_tracker.ui import theme

    all_df = activities()
    left, right = st.columns([1.3, 1], vertical_alignment="bottom")
    types: list[str] = []
    with right:
        c1, c2 = st.columns([1, 1], vertical_alignment="bottom", gap="small")
        current = (
            c1.segmented_control(
                "Mode",
                list(MODES),
                default="road",
                key="f_mode",
                persist_state="session",
                format_func=MODES.get,
                label_visibility="collapsed",
                width="stretch",
            )
            or "road"
        )
        if with_types and current == "road":
            default = types_default or DEFAULT_TYPES
            with c2.popover("Type de séance", icon=":material/tune:", width="stretch"):
                types = (
                    st.pills(
                        "Type de séance",
                        ROAD_TYPES,
                        selection_mode="multi",
                        default=default,
                        key=types_key,
                        format_func=SESSION_TYPES.get,
                        persist_state="session",
                        label_visibility="collapsed",
                    )
                    or []
                )
    df = in_mode(all_df, current) if not all_df.empty else all_df
    if types and not df.empty:
        df = df[df["session_type"].isin(types)]
    with left:
        theme.page_header(title, _caption(df, current, types, with_types) if not all_df.empty else None)
    return df


def _caption(df: pd.DataFrame, current: str, types: list[str], with_types: bool) -> str:
    n = f"{len(df)} sortie{'s' if len(df) != 1 else ''}"
    if current == "trail":
        return f"{n} trail"
    if not with_types or len(types) in (0, len(ROAD_TYPES)):
        return f"{n} sur route, tous types de séance"
    return f"{n} sur route : " + ", ".join(SESSION_TYPES[t].lower() for t in types)


def date_range(df: pd.DataFrame, label: str = "Période") -> pd.DataFrame:
    """Date-range slider shared by the analysis pages (one range per mode)."""
    if df.empty or df["date"].nunique() < 2:
        return df
    lo, hi = df["date"].min().date(), df["date"].max().date()
    key = f"f_range_{mode()}"
    stored = st.session_state.get(key)
    if stored and (stored[0] < lo or stored[1] > hi or stored[0] > stored[1]):
        st.session_state[key] = (max(stored[0], lo), min(stored[1], hi))
    start, end = st.slider(
        label,
        min_value=lo,
        max_value=hi,
        value=(lo, hi),
        key=key,
        persist_state="session",
        format="DD/MM/YYYY",
    )
    return df[(df["date"].dt.date >= start) & (df["date"].dt.date <= end)]


def range_caption(df: pd.DataFrame) -> str:
    if df.empty:
        return ""
    return f"du {df['date'].min():%d/%m/%Y} au {df['date'].max():%d/%m/%Y}"


# ---------------------------------------------------------------- charts / links
def palette() -> dict:
    from cadence_tracker.ui.charts import NIGHT

    return NIGHT


# No export anywhere in the app: the "download as image" button is removed too.
PLOTLY_CONFIG = {
    "displaylogo": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d", "toImage"],
    "locale": "fr",
}


def show(fig, key: str | None = None, **kwargs):
    return st.plotly_chart(fig, width="stretch", theme=None, config=PLOTLY_CONFIG, key=key, **kwargs)


# ------------------------------------------------------------------ formatting
def fr_num(value, decimals: int = 1, unit: str = "") -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "–"
    text = f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")
    return f"{text} {unit}".strip()


FR_MONTHS = [
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
FR_DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def fr_month(ts) -> str:
    """Timestamp -> 'novembre 2026'"""
    return f"{FR_MONTHS[ts.month - 1]} {ts.year}"


def fr_datetime(ts) -> str:
    """Timestamp -> 'mardi 18/11/2026 à 07:12'"""
    return f"{FR_DAYS[ts.weekday()]} {ts:%d/%m/%Y} à {ts:%H:%M}"


def pace(value) -> str:
    return format_pace(value)


def duration(value) -> str:
    return format_duration(value)


def empty_state() -> None:
    st.info(
        "Aucune sortie pour l'instant. Synchronisez Garmin ou importez vos fichiers FIT, GPX ou TCX "
        "pour commencer. Pour découvrir l'application sans vos données : `ctrack demo` puis `ctrack ui --demo`.",
        icon=":material/directions_run:",
    )
    if "settings" in PAGES:
        st.page_link(PAGES["settings"], label="Importer mes sorties", icon=":material/sync:")


def no_match() -> None:
    st.warning(
        "Aucune sortie ne correspond. Changez de mode (route ou trail) ou de type de séance.",
        icon=":material/filter_alt_off:",
    )
