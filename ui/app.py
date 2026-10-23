"""
app.py — Module 09: Giao diện Streamlit chính của FinInsight AI.

Layout: Sidebar (upload + cài đặt) | Chat chính

Chạy: .venv\\Scripts\\streamlit.exe run ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _verify_torch_runtime() -> None:
    """Kiểm tra torch trước khi import embedding stack (tránh lỗi SymInt)."""
    exe = Path(sys.executable).resolve()
    expected = (ROOT / ".venv" / "Scripts" / "python.exe").resolve()
    try:
        import torch
    except ImportError as exc:
        _fail_runtime(
            "Chưa cài torch trong môi trường hiện tại.\n"
            f"Python đang dùng: {exe}\n"
            "Chạy: .venv\\Scripts\\pip install -r requirements.txt\n"
            "Hoặc: .\\run.ps1",
            exc,
        )
    if not hasattr(torch, "SymInt"):
        _fail_runtime(
            "Torch bị hỏng (thiếu SymInt).\n"
            f"Python đang dùng: {exe}\n"
            f"Python khuyến nghị: {expected}\n"
            "Sửa: .venv\\Scripts\\pip install torch==2.12.1 torchvision==0.27.1 --force-reinstall\n"
            "Chạy app: .\\run.ps1",
        )


def _fail_runtime(message: str, exc: Exception | None = None) -> None:
    print(f"❌ {message}", file=sys.stderr)
    raise SystemExit(1) from exc


_verify_torch_runtime()

import importlib
import streamlit as st

# Tránh Streamlit giữ bản cũ của module ingestion trong RAM
import src.ingestion.ocr_extractor as _ocr_mod
import src.ingestion.upload_ingest as _upload_ingest_mod

importlib.reload(_ocr_mod)
importlib.reload(_upload_ingest_mod)

from src.modules.suggestion_module import get_followup_suggestions, get_welcome_suggestions
from src.modules.summary_module import SUMMARY_FOCUSES, generate_summary
from src.orchestrator.chain_router import route_question
from ui.components.chat_panel import (
    add_assistant_message,
    add_user_message,
    get_chat_input,
    init_chat_history,
    render_chat_history,
    render_suggestion_chips,
)
from ui.components.result_card import (
    render_company_tags,
    render_intent_badge,
    render_sources_expander,
)


def _get_render_sidebar():
    """
    Import render_sidebar an toàn.

    Streamlit hot-reload đôi khi giữ module sidebar cũ (thiếu render_sidebar)
    trong sys.modules — xóa cache trước khi import lại.
    """
    import importlib

    name = "ui.components.sidebar"
    cached = sys.modules.get(name)
    if cached is not None and not hasattr(cached, "render_sidebar"):
        del sys.modules[name]

    sidebar_mod = importlib.import_module(name)
    importlib.reload(sidebar_mod)
    if not hasattr(sidebar_mod, "render_sidebar"):
        raise ImportError(
            f"{name} thiếu render_sidebar. "
            "Dừng Streamlit (Ctrl+C) và chạy lại .\\run.ps1"
        )
    return sidebar_mod.render_sidebar

# ─── Cấu hình trang ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FinInsight AI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource(show_spinner="Đang tải model embedding (lần đầu ~1–2 phút)…")
def _preload_embedding_model() -> bool:
    """Tải sẵn model embedding để upload nhanh hơn."""
    from src.ingestion.embedder import _get_model
    from src.utils.config import get_ingestion_settings

    cfg = get_ingestion_settings()
    model_name = cfg.get(
        "embedding_model",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    )
    _get_model(model_name)
    return True


@st.cache_resource(show_spinner="Đang tải OCR (lần đầu ~30–60 giây)…")
def _preload_ocr() -> bool:
    """Tải sẵn engine OCR — upload không phải chờ load model."""
    import importlib

    ocr_mod = importlib.import_module("src.ingestion.ocr_extractor")
    importlib.reload(ocr_mod)
    if hasattr(ocr_mod, "preload_ocr"):
        ocr_mod.preload_ocr()
    return True


def _render_chat(config: dict) -> None:
    """Khu vực chat chính."""
    module = config["module"]
    show_sources = config["show_sources"]
    show_scores = config["show_scores"]
    active_collections = config["active_collections"]

    st.title("📊 FinInsight AI")
    st.caption("Phân tích Báo cáo Tài chính doanh nghiệp Việt Nam")

    example = st.session_state.get("example_prompt")

    if not active_collections:
        st.warning(
            "📂 **Chưa có tài liệu nào được nạp.**\n\n"
            "Hãy upload file PDF ở **sidebar bên trái**.",
            icon="👉",
        )
        if example:
            st.info(f"💬 Câu hỏi đang chờ: *{example}* — upload PDF để hỏi.")
        return

    if module == "SUMMARY":
        _render_summary_ui(active_collections, show_sources)
        return

    init_chat_history()
    render_chat_history()

    loaded_docs = st.session_state.get("loaded_docs", {})
    doc_names = [loaded_docs.get(c, c) for c in active_collections]

    if len(st.session_state.messages) == 1 and doc_names:
        welcome_suggestions = get_welcome_suggestions(
            doc_names, collection_names=active_collections
        )
        render_suggestion_chips(welcome_suggestions, key_prefix="welcome")

    user_input = example or get_chat_input()
    if not user_input:
        return

    st.session_state.pop("example_prompt", None)

    add_user_message(user_input)
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Đang tìm kiếm và phân tích…"):
            intent_override = None if module == "AUTO" else module

            try:
                result = route_question(
                    question=user_input,
                    company_filter=None,
                    intent_override=intent_override,
                    collection_names=active_collections,
                )

                intent = result.get("intent", "QA")
                detected_companies = result.get("detected_companies", [])

                col_badge, col_tags = st.columns([2, 5])
                with col_badge:
                    render_intent_badge(intent)
                with col_tags:
                    render_company_tags(detected_companies)
                st.markdown("")

                answer_key = {
                    "QA": "answer",
                    "COMPARE": "comparison",
                    "TREND": "analysis",
                    "GLOSSARY": "explanation",
                    "SUMMARY": "summary",
                }.get(intent, "answer")

                content = result.get(answer_key, "Không có kết quả.")
                st.markdown(content)

                sources = result.get("sources", [])
                if show_sources and sources:
                    render_sources_expander(sources, show_scores)

                with st.spinner("💡 Đang gợi ý câu hỏi tiếp theo…"):
                    suggestions = get_followup_suggestions(
                        question=user_input,
                        answer=content,
                        doc_names=doc_names,
                        intent=intent,
                        collection_names=active_collections,
                    )
                render_suggestion_chips(
                    suggestions,
                    key_prefix=f"live_{len(st.session_state.messages)}",
                )

                add_assistant_message(content, sources, show_scores, suggestions)

            except Exception as e:
                error_msg = f"Đã xảy ra lỗi: {str(e)}"
                st.error(f"❌ {error_msg}")
                add_assistant_message(f"❌ {error_msg}")


def _render_summary_ui(active_collections: list[str], show_sources: bool) -> None:
    st.subheader("📋 Tóm tắt Báo cáo Tài chính")

    loaded_docs = st.session_state.get("loaded_docs", {})
    doc_options = {col: loaded_docs.get(col, col) for col in active_collections}

    if not doc_options:
        st.info("Chưa có tài liệu nào. Hãy upload file PDF trước.")
        return

    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        selected_col = st.selectbox(
            "Tài liệu",
            options=list(doc_options.keys()),
            format_func=lambda c: doc_options[c],
        )
    with col2:
        selected_focus = st.selectbox(
            "Tiêu điểm",
            options=list(SUMMARY_FOCUSES.keys()),
            index=0,
        )
    with col3:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_btn = st.button("🚀 Tạo báo cáo", use_container_width=True, type="primary")

    if generate_btn:
        with st.spinner(f"📝 Đang tạo báo cáo cho '{doc_options[selected_col]}'…"):
            try:
                result = generate_summary(selected_col, focus=selected_focus)
                st.markdown(result["summary"])
                if show_sources and result.get("sources"):
                    render_sources_expander(result["sources"])
            except Exception as e:
                st.error(f"❌ Lỗi: {e}")
    else:
        st.info("👆 Chọn tài liệu, tiêu điểm và nhấn **Tạo báo cáo**.")


def main():
    config = _get_render_sidebar()()
    _render_chat(config)


if __name__ == "__main__":
    main()
