"""Réglages: import & synchronisation, general settings (two tabs).

Specs: docs/specs/F01, F08, F09.
"""

from __future__ import annotations

import streamlit as st

from cadence_tracker.ui import theme
from cadence_tracker.ui.views import data, settings_view


def render() -> None:
    theme.page_header("Réglages")
    tab_import, tab_settings = st.tabs(["Import et synchronisation", "Paramètres généraux"])
    with tab_import:
        data.render_import()
    with tab_settings:
        settings_view.render_settings()
