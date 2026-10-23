"""
upload_ingest.py — Nạp dữ liệu từ file PDF upload trực tiếp qua giao diện Streamlit.

Nhận bytes của file PDF, lưu tạm, chạy pipeline ingest, trả về collection_name.
"""

from __future__ import annotations

import hashlib
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.ingestion.chunker import chunk_pages
from src.ingestion.embedder import embed_chunks
from src.ingestion.financial_validator import (
    FinancialValidation,
    should_reject_upload,
    validate_financial_document,
)
from src.ingestion.pdf_loader import load_pdf
from src.ingestion.pdf_stats import PDFLoadReport
from src.storage.chroma_client import get_chroma_collection
from src.utils.config import get_financial_validation_settings, get_ingestion_settings, get_upload_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IngestResult:
    """Kết quả nạp một file PDF upload."""

    collection_name: str
    chunk_count: int
    report: PDFLoadReport
    filename: str
    validation: FinancialValidation | None = None
    rejected: bool = False
    rejection_reason: str | None = None

    @property
    def warning(self) -> str | None:
        ratio = get_ingestion_settings().get("min_readable_page_ratio", 0.5)
        pdf_warning = self.report.build_warning(min_readable_ratio=ratio)
        if self.rejected and self.rejection_reason:
            return self.rejection_reason
        if self.validation and self.validation.is_borderline:
            borderline = self.validation.message or (
                "Tài liệu có dấu hiệu BCTC nhưng độ tin cậy thấp."
            )
            if pdf_warning:
                return f"{borderline} | {pdf_warning}"
            return borderline
        return pdf_warning

    @property
    def success_message(self) -> str:
        base = f"{self.filename}: {self.chunk_count} chunks ({self.report.summary_line()})"
        if self.report.ocr_pages:
            base += f" — OCR {self.report.ocr_pages} trang"
        if self.validation and self.validation.confidence == "medium":
            base += " — BCTC (độ tin cậy trung bình)"
        return base


def _run_financial_validation(pages) -> FinancialValidation | None:
    cfg = get_financial_validation_settings()
    if not cfg.get("enabled", True):
        return None
    return validate_financial_document(pages)


def _should_reject(validation: FinancialValidation | None) -> tuple[bool, str | None]:
    return should_reject_upload(validation)


def ingest_uploaded_pdf(
    file_bytes: bytes,
    filename: str,
    force_reingest: bool = False,
    *,
    skip_financial_check: bool = False,
    on_progress=None,  # deprecated — giữ để tương thích cache module cũ của Streamlit
    **kwargs,
) -> IngestResult:
    """
    Nhận bytes PDF từ Streamlit uploader, xử lý và nạp vào ChromaDB.

    Args:
        file_bytes: Nội dung file PDF dưới dạng bytes.
        filename: Tên file gốc (ví dụ: "bctc_2023.pdf").
        force_reingest: Nếu True, xoá collection cũ và nạp lại.
        skip_financial_check: Bỏ qua kiểm tra BCTC (CLI / dữ liệu tin cậy).
        on_progress: Không dùng (giữ cho tương thích).

    Returns:
        IngestResult gồm collection, số chunk, thống kê đọc PDF và cảnh báo.
    """
    _ = on_progress, kwargs
    max_bytes = int(get_upload_settings().get("max_bytes", 20 * 1024 * 1024))
    if not file_bytes or len(file_bytes) > max_bytes:
        raise ValueError(f"PDF phải có dữ liệu và không vượt quá {max_bytes // (1024 * 1024)} MB.")
    if Path(filename).suffix.lower() != ".pdf" or b"%PDF-" not in file_bytes[:1024]:
        raise ValueError("Tệp tải lên phải là PDF hợp lệ.")
    content_hash = hashlib.sha256(file_bytes).hexdigest()[:24]
    safe_name = Path(filename).stem
    safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", safe_name)[:30]
    collection_name = f"upload_{safe_name}_{content_hash}"

    logger.info(f"[UploadIngest] Bắt đầu nạp: {filename} → collection='{collection_name}'")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = Path(tmp.name)

    try:
        pages, report = load_pdf(
            tmp_path, company=collection_name, file_hash=content_hash
        )
        if not pages:
            logger.warning(f"[UploadIngest] Không trích xuất được trang nào từ '{filename}'.")
            return IngestResult(collection_name, 0, report, filename)

        # The parser reads a temporary file; citations must name the original PDF.
        for page in pages:
            page.source_file = Path(filename).name
            page.metadata["file_name"] = Path(filename).name

        validation = None if skip_financial_check else _run_financial_validation(pages)
        rejected, rejection_reason = _should_reject(validation)
        if rejected:
            logger.warning(
                f"[UploadIngest] Từ chối '{filename}': không phải tài liệu tài chính."
            )
            return IngestResult(
                collection_name,
                0,
                report,
                filename,
                validation=validation,
                rejected=True,
                rejection_reason=rejection_reason,
            )

        if validation:
            for page in pages:
                page.metadata["is_financial_document"] = validation.is_financial
                page.metadata["financial_confidence"] = validation.confidence

        chunks = chunk_pages(pages)

        chunk_embeddings = embed_chunks(chunks, show_progress=False)

        if not chunk_embeddings:
            return IngestResult(collection_name, 0, report, filename)
        collection = get_chroma_collection(collection_name, force_reingest=force_reingest)
        ids = [c.chunk_id for c, _ in chunk_embeddings]
        documents = [c.text for c, _ in chunk_embeddings]
        embeddings = [vec for _, vec in chunk_embeddings]
        metadatas = [c.metadata for c, _ in chunk_embeddings]

        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        from src.retrieval.bm25_search import invalidate_bm25_index
        invalidate_bm25_index(collection_name)

        logger.info(
            f"[UploadIngest] Hoàn tất: {len(ids)} chunks → collection='{collection_name}' "
            f"({report.summary_line()})"
        )
        return IngestResult(
            collection_name,
            len(ids),
            report,
            filename,
            validation=validation,
        )

    finally:
        tmp_path.unlink(missing_ok=True)


def delete_uploaded_collection(collection_name: str) -> None:
    """Xoá collection của một tài liệu đã upload."""
    from src.storage.chroma_client import get_client
    client = get_client()
    try:
        client.delete_collection(collection_name)
        from src.retrieval.bm25_search import invalidate_bm25_index
        invalidate_bm25_index(collection_name)
        logger.info(f"[UploadIngest] Đã xoá collection '{collection_name}'.")
    except Exception as e:
        logger.warning(f"[UploadIngest] Không thể xoá '{collection_name}': {e}")
