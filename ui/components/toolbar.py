"""Toolbar component — spec 2.5 (dashboard layout, không dùng trong sidebar UI)."""

from __future__ import annotations

import streamlit as st

WIDGET_CATEGORIES: dict[str, list[str]] = {
    "Climate": [
        "Average Temperature",
        "Average Precipitation",
        "Average Rainfall",
    ],
    "Atmosphere": [
        "Air Quality Station",
        "Air Quality Filter",
    ],
    "Population": ["Population"],
    "Industry": ["Industry Production"],
    "Forest": ["Forest Cover Area", "Afforestation"],
    "Operators": ["Statistics Merge", "Simple Merge"],
    "Visualization": ["Column Chart", "Line Chart", "Pie Chart", "Maps"],
}

DATASET_DIMENSIONS = ["Year", "City", "Period of City"]

DEFAULT_OPEN_CATEGORY = "Visualization"


def render_toolbar() -> dict:
    """
    Render Toolbar với Widgets dropdown menu.

    Returns:
        Dict gồm selected_widget và selected_category.
    """
    if "toolbar_open_categories" not in st.session_state:
        st.session_state["toolbar_open_categories"] = {DEFAULT_OPEN_CATEGORY: True}

    if "selected_widget" not in st.session_state:
        st.session_state["selected_widget"] = None
        st.session_state["selected_category"] = None

    open_cats: dict[str, bool] = st.session_state["toolbar_open_categories"]

    st.markdown('<div class="dashboard-toolbar">', unsafe_allow_html=True)
    st.markdown('<div class="toolbar-title">Widgets</div>', unsafe_allow_html=True)

    for category, items in WIDGET_CATEGORIES.items():
        is_open = open_cats.get(category, category == DEFAULT_OPEN_CATEGORY)
        arrow = "▼" if is_open else "▶"

        header_key = f"toolbar_hdr_{category}"
        if st.button(f"{arrow} {category}", key=header_key, use_container_width=True):
            open_cats[category] = not is_open
            st.session_state["toolbar_open_categories"] = open_cats
            st.rerun()

        if is_open:
            for item in items:
                is_active = (
                    st.session_state.get("selected_widget") == item
                    and st.session_state.get("selected_category") == category
                )
                item_key = f"toolbar_item_{category}_{item}"

                if st.button(
                    item,
                    key=item_key,
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state["selected_widget"] = item
                    st.session_state["selected_category"] = category
                    st.rerun()

    st.markdown(
        f'<div class="toolbar-dimensions">Dimensions: {", ".join(DATASET_DIMENSIONS)}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

    return {
        "selected_widget": st.session_state.get("selected_widget"),
        "selected_category": st.session_state.get("selected_category"),
    }
