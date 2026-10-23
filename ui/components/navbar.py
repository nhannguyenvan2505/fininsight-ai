"""Navbar component — spec 2.2.2."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"

NAV_BUTTONS = ["New", "Save", "Help", "Example 1", "Example 2"]


def render_navbar() -> str | None:
    """
    Render Navbar với Logo và Group Buttons.

    Returns:
        Tên button được click (nếu có), hoặc None.
    """
    logo_b64 = _logo_as_base64()

    st.markdown(
        f"""
        <div class="navbar">
            <div class="navbar-logo">
                <img src="data:image/png;base64,{logo_b64}" alt="Logo" />
            </div>
            <div class="navbar-buttons" id="navbar-spacer"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    clicked: str | None = None
    cols = st.columns(len(NAV_BUTTONS))
    for col, label in zip(cols, NAV_BUTTONS):
        with col:
            if st.button(label, key=f"nav_{label}", use_container_width=False):
                clicked = label
                _handle_nav_action(label)

    return clicked


def _handle_nav_action(action: str) -> None:
    """Xử lý sự kiện click trên navbar buttons."""
    if action == "New":
        from ui.components.chat_panel import clear_history
        st.session_state.pop("loaded_docs", None)
        st.session_state.pop("active_collections", None)
        st.session_state.pop("example_prompt", None)
        clear_history()
        st.toast("Đã tạo workspace mới.", icon="🆕")
        st.rerun()
    elif action == "Save":
        st.toast("Đã lưu trạng thái hiện tại.", icon="💾")
    elif action == "Help":
        st.session_state["show_help"] = True
    elif action == "Example 1":
        st.session_state["example_prompt"] = (
            "Phân tích doanh thu và lợi nhuận của FPT trong 3 năm gần nhất."
        )
    elif action == "Example 2":
        st.session_state["example_prompt"] = (
            "So sánh tỷ suất lợi nhuận giữa Vinamilk và TH True Milk."
        )


def _logo_as_base64() -> str:
    import base64
    if LOGO_PATH.exists():
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    return ""
