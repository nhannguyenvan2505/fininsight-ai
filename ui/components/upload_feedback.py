"""Shared upload feedback helpers for sidebar and info panel."""

from __future__ import annotations

import streamlit as st

from src.ingestion.upload_ingest import IngestResult


def apply_ingest_result(filename: str, result: IngestResult) -> bool:
    """
    Cập nhật session state và hiển thị thông báo sau upload.

    Returns:
        True nếu file được nạp thành công vào ChromaDB.
    """
    if result.rejected:
        st.error(f"🚫 **{filename}:** {result.rejection_reason}")
        return False

    if result.chunk_count == 0:
        st.error(f"❌ {filename}: không đọc được nội dung nào.")
        if result.warning:
            st.warning(f"⚠️ {result.warning}")
        return False

    st.session_state["loaded_docs"][result.collection_name] = filename
    st.session_state["active_collections"].add(result.collection_name)
    st.toast(f"✅ {result.success_message}", icon="📄")

    if result.warning:
        st.warning(f"⚠️ **{filename}:** {result.warning}")
    elif result.report.ocr_pages > 0:
        st.info(
            f"ℹ️ **{filename}:** đã OCR {result.report.ocr_pages}/"
            f"{result.report.total_pages} trang (PDF dạng ảnh)."
        )
    elif result.validation and result.validation.confidence == "high":
        st.success(f"✅ **{filename}:** đã xác nhận là tài liệu tài chính.")

    return True
