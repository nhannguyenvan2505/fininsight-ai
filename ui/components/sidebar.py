"""Sidebar component — upload, tài liệu, chế độ phân tích."""

from __future__ import annotations

import streamlit as st

from src.utils.config import get_ingestion_settings, get_llm_settings

__all__ = ["render_sidebar"]


def render_sidebar() -> dict:
    """
    Render sidebar Streamlit (upload + cài đặt).

    Returns:
        Dict cấu hình cho chat: module, show_sources, show_scores, active_collections.
    """
    # Xóa job upload nền cũ (từ phiên bản trước) — tránh lỗi cache Streamlit
    st.session_state.pop("pending_ingest_jobs", None)

    with st.sidebar:
        st.header("📄 Tài liệu")

        uploaded_files = st.file_uploader(
            "Kéo & thả file PDF vào đây",
            type=["pdf"],
            accept_multiple_files=True,
            label_visibility="collapsed",
            help=(
                "Chỉ hỗ trợ BCTC, báo cáo kiểm toán, báo cáo thường niên. "
                "Tài liệu không phù hợp có thể được cảnh báo theo cấu hình."
            ),
        )

        if uploaded_files:
            is_uploading = st.session_state.get("_uploading", False)
            if st.button(
                "📎 Thêm tệp" if not is_uploading else "⏳ Đang xử lý…",
                type="primary",
                use_container_width=True,
                disabled=is_uploading,
            ):
                st.session_state["_uploading"] = True
                _ingest_uploaded_files(uploaded_files)



        loaded_docs: dict[str, str] = st.session_state.get("loaded_docs", {})

        if loaded_docs:
            st.markdown("**📚 Tài liệu đã nạp:**")
            to_delete = []
            for col_name, display_name in list(loaded_docs.items()):
                col1, col2 = st.columns([4, 1])
                with col1:
                    is_active = col_name in st.session_state.get(
                        "active_collections", set(loaded_docs.keys())
                    )
                    checked = st.checkbox(
                        display_name,
                        value=is_active,
                        key=f"chk_{col_name}",
                    )
                    if checked:
                        st.session_state.setdefault("active_collections", set()).add(col_name)
                    else:
                        st.session_state.get("active_collections", set()).discard(col_name)
                with col2:
                    if st.button("🗑️", key=f"del_{col_name}", help="Xoá tài liệu này"):
                        to_delete.append(col_name)

            for col_name in to_delete:
                _delete_collection(col_name)
        else:
            st.info("Chưa có tài liệu. Upload PDF ở trên.")

        st.divider()

        st.subheader("⚡ Chế độ")
        module = st.radio(
            "Chọn chức năng",
            options=[
                "🤖 Hỏi đáp tự động",
                "📊 So sánh",
                "📈 Xu hướng",
                "📖 Thuật ngữ",
                "📋 Tóm tắt",
            ],
            index=0,
            label_visibility="collapsed",
        )

        st.divider()

        st.subheader("⚙️ Tuỳ chọn")
        show_sources = st.toggle("Hiển thị nguồn tham khảo", value=True)
        show_scores = st.toggle("Hiển thị điểm relevance", value=False)

        if st.button("🔄 Xoá hội thoại", use_container_width=True):
            from ui.components.chat_panel import clear_history

            clear_history()
            st.toast("Đã xoá hội thoại.", icon="🔄")
            st.rerun()

        st.divider()

        with st.expander("ℹ️ Thông tin hệ thống"):
            _model_name = get_llm_settings().get("model", "N/A")
            embed_model = get_ingestion_settings().get("embedding_model", "N/A")
            doc_count = len(st.session_state.get("loaded_docs", {}))
            st.markdown(
                f"""
                **Model:** {_model_name}  
                **Tài liệu:** {doc_count} file  
                **Embedding:** {embed_model.split("/")[-1]}  
                **Vector DB:** ChromaDB  
                **Search:** BM25 + Semantic (RRF)
                """
            )

    module_map = {
        "🤖 Hỏi đáp tự động": "AUTO",
        "📊 So sánh": "COMPARE",
        "📈 Xu hướng": "TREND",
        "📖 Thuật ngữ": "GLOSSARY",
        "📋 Tóm tắt": "SUMMARY",
    }

    active_collections = list(st.session_state.get("active_collections", set()))

    return {
        "collection_filter": None,
        "module": module_map.get(module, "AUTO"),
        "show_sources": show_sources,
        "show_scores": show_scores,
        "active_collections": active_collections,
    }


def _ingest_uploaded_files(uploaded_files) -> None:
    """Nạp danh sách file PDF vào ChromaDB."""
    import importlib

    import src.ingestion.upload_ingest as upload_mod

    importlib.reload(upload_mod)
    ingest_fn = upload_mod.ingest_uploaded_pdf

    from ui.components.upload_feedback import apply_ingest_result

    if "loaded_docs" not in st.session_state:
        st.session_state["loaded_docs"] = {}
    if "active_collections" not in st.session_state:
        st.session_state["active_collections"] = set()

    for f in uploaded_files:
        with st.spinner(f"Đang xử lý: {f.name}…"):
            try:
                result = ingest_fn(f.read(), f.name)
                apply_ingest_result(f.name, result)
            except Exception as e:
                st.error(f"❌ Lỗi khi nạp '{f.name}': {e}")

    st.session_state["_uploading"] = False
    st.rerun()


def _delete_collection(col_name: str) -> None:
    from src.ingestion.upload_ingest import delete_uploaded_collection

    delete_uploaded_collection(col_name)
    st.session_state.get("loaded_docs", {}).pop(col_name, None)
    st.session_state.get("active_collections", set()).discard(col_name)
    st.toast("🗑️ Đã xoá tài liệu.", icon="✅")
    st.rerun()
