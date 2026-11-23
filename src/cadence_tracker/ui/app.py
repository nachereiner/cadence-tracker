"""Streamlit entry point: `ctrack ui` (or `streamlit run src/cadence_tracker/ui/app.py`).

Each page is a `render()` function in `ui/views/`. Navigation sits in the top
bar next to the logo; each page header carries the Route/Trail switch.
"""

from __future__ import annotations

import streamlit as st

from cadence_tracker.ui import common, theme
from cadence_tracker.ui.views import activities, compare, correlations, dashboard, goal, reglages

st.set_page_config(
    page_title="Cadence Tracker",
    page_icon=str(theme.MARK),
    layout="wide",
    initial_sidebar_state="collapsed",
)
theme.inject()
st.logo(str(theme.LOGO), size="large")

pages = {
    "dashboard": st.Page(dashboard.render, title="Tableau de bord", url_path="tableau-de-bord", default=True),
    "correlations": st.Page(correlations.render, title="Corrélations", url_path="correlations"),
    "goal": st.Page(goal.render, title="Objectif", url_path="objectif-cadence"),
    "activities": st.Page(activities.render, title="Sorties", url_path="sorties"),
    "compare": st.Page(compare.render, title="Comparer", url_path="comparer"),
    "settings": st.Page(reglages.render, title="Réglages", url_path="reglages"),
}
common.PAGES.update(pages)

nav = st.navigation(list(pages.values()), position="top")
if common.is_demo() and not st.session_state.get("_demo_notice"):
    st.session_state["_demo_notice"] = True
    st.toast("Mode démonstration : les sorties affichées sont synthétiques.", icon=":material/science:")
nav.run()
