"""
result_card.py — Component hiển thị kết quả phân tích dạng card.
"""

from __future__ import annotations

import streamlit as st
from html import escape


def render_intent_badge(intent: str) -> None:
    """Hiển thị badge ý định câu hỏi."""
    badge_map = {
        "QA": ("🔍 Hỏi đáp", "#1565C0"),
        "COMPARE": ("📊 So sánh", "#6A1B9A"),
        "TREND": ("📈 Xu hướng", "#00695C"),
        "GLOSSARY": ("📖 Thuật ngữ", "#E65100"),
        "SUMMARY": ("📋 Tóm tắt", "#4E342E"),
        "AUTO": ("🤖 Tự động", "#37474F"),
    }
    label, color = badge_map.get(intent, ("❓", "#607D8B"))
    st.markdown(
        f'<span style="background:{color}; color:white; padding:2px 10px; '
        f'border-radius:12px; font-size:0.78rem;">{label}</span>',
        unsafe_allow_html=True,
    )


def render_company_tags(companies: list[str]) -> None:
    """Hiển thị tags công ty được phát hiện."""
    if not companies:
        return
    tags = " ".join(
        f'<span style="background:#263238; color:#80CBC4; padding:2px 8px; '
        f'border-radius:8px; font-size:0.75rem; margin-right:4px;">{escape(c.upper())}</span>'
        for c in companies
    )
    st.markdown(tags, unsafe_allow_html=True)


def render_metric_card(title: str, value: str, delta: str | None = None) -> None:
    """Hiển thị một metric dạng card nhỏ."""
    st.metric(label=title, value=value, delta=delta)


def render_comparison_table(data: dict[str, dict[str, str]]) -> None:
    """
    Hiển thị bảng so sánh.

    Args:
        data: {metric: {company: value}}
    """
    import pandas as pd

    if not data:
        return

    df = pd.DataFrame(data).T
    df.index.name = "Chỉ số"
    st.dataframe(df, use_container_width=True)


def render_sources_expander(sources: list[dict], show_scores: bool = False) -> None:
    """Hiển thị nguồn tham khảo trong expander."""
    if not sources:
        return

    with st.expander(f"📚 Nguồn tham khảo ({len(sources)} tài liệu)", expanded=False):
        for i, src in enumerate(sources, 1):
            company = src.get("company", "").upper()
            file_name = src.get("file_name", "N/A")
            page = src.get("page", "?")
            score = src.get("score", None)

            cols = st.columns([1, 3, 1, 1])
            cols[0].markdown(f"**#{i}**")
            cols[1].markdown(f"🏢 `{company}` — {file_name}")
            cols[2].markdown(f"📄 Tr. {page}")
            if show_scores and score is not None:
                cols[3].markdown(f"`{score:.3f}`")


def render_error_card(message: str) -> None:
    """Hiển thị thông báo lỗi."""
    st.error(f"❌ {message}")


def render_info_card(message: str) -> None:
    """Hiển thị thông tin trung lập."""
    st.info(f"ℹ️ {message}")
