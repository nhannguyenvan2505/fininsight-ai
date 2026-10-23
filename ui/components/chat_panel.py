"""
chat_panel.py — Panel hội thoại chính của FinInsight AI.
"""

from __future__ import annotations

import streamlit as st


def init_chat_history() -> None:
    """Khởi tạo lịch sử hội thoại trong session state."""
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": (
                    "👋 Xin chào! Tôi là **FinInsight AI** — trợ lý phân tích Báo cáo Tài chính.\n\n"
                    "Tôi có thể giúp bạn:\n"
                    "- 🔍 **Hỏi đáp** về số liệu tài chính (doanh thu, lợi nhuận, ROE, ...)\n"
                    "- 📊 **So sánh** các doanh nghiệp FPT, Vinamilk, Vietcombank, Hoà Phát, TGDD\n"
                    "- 📈 **Phân tích xu hướng** qua các năm\n"
                    "- 📖 **Giải thích thuật ngữ** tài chính\n"
                    "- 📋 **Tóm tắt** báo cáo theo yêu cầu\n\n"
                    "Hãy đặt câu hỏi của bạn! 💬"
                ),
            }
        ]


def render_chat_history() -> None:
    """Render lịch sử hội thoại."""
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

            # Hiển thị nguồn nếu có
            if msg.get("sources"):
                with st.expander("📚 Nguồn tham khảo", expanded=False):
                    _render_sources(msg["sources"], msg.get("show_scores", False))

            if msg["role"] == "assistant" and msg.get("suggestions"):
                render_suggestion_chips(msg["suggestions"], key_prefix=f"hist_{idx}")


def add_user_message(content: str) -> None:
    """Thêm tin nhắn người dùng vào lịch sử."""
    st.session_state.messages.append({"role": "user", "content": content})


def add_assistant_message(
    content: str,
    sources: list[dict] | None = None,
    show_scores: bool = False,
    suggestions: list[str] | None = None,
) -> None:
    """Thêm tin nhắn trợ lý vào lịch sử."""
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": content,
            "sources": sources or [],
            "show_scores": show_scores,
            "suggestions": suggestions or [],
        }
    )


def render_suggestion_chips(suggestions: list[str], key_prefix: str) -> None:
    """
    Hiển thị nút gợi ý câu hỏi — click sẽ điền vào ô chat.

    Args:
        suggestions: Danh sách câu hỏi gợi ý.
        key_prefix: Prefix duy nhất cho st.button key.
    """
    if not suggestions:
        return

    st.caption("💡 **Gợi ý câu hỏi tiếp theo** — bấm để hỏi ngay:")
    cols = st.columns(min(len(suggestions), 3))
    for i, question in enumerate(suggestions[:3]):
        with cols[i % len(cols)]:
            if st.button(
                question,
                key=f"{key_prefix}_sug_{i}",
                use_container_width=True,
                type="secondary",
            ):
                st.session_state["example_prompt"] = question
                st.rerun()


def _render_sources(sources: list[dict], show_scores: bool = False) -> None:
    """Render danh sách nguồn tham khảo."""
    if not sources:
        st.caption("Không có nguồn tham khảo.")
        return

    for i, src in enumerate(sources, 1):
        company = src.get("company", "").upper()
        file_name = src.get("file_name", "N/A")
        page = src.get("page", "?")
        score = src.get("score", None)

        score_text = f" | Điểm: `{score:.4f}`" if show_scores and score is not None else ""
        st.markdown(
            f"**{i}.** 🏢 `{company}` · 📄 {file_name} · Trang {page}{score_text}"
        )


def get_chat_input(placeholder: str = "Nhập câu hỏi về tài chính doanh nghiệp…") -> str | None:
    """Render chat input và trả về nội dung khi người dùng gửi."""
    return st.chat_input(placeholder)


def clear_history() -> None:
    """Xoá lịch sử hội thoại."""
    st.session_state.messages = []
    init_chat_history()
