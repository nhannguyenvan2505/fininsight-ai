"""
pdf_loader.py — Module 01: Trích xuất văn bản từ file PDF tài chính.

Chiến lược theo từng trang:
- text  → đọc text layer trực tiếp
- image → OCR (trang scan / ảnh full trang)
- mixed → gộp text layer + OCR (trang vừa có chữ vừa có ảnh)
"""

from __future__ import annotations

import hashlib
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Literal

import fitz  # PyMuPDF
import numpy as np

from src.ingestion.ocr_cache import load_ocr_cache, save_ocr_cache
from src.ingestion.ocr_extractor import (
    _page_to_image,
    _ocr_with_rapid,
    _ocr_with_easy,
    _backend,
    get_effective_backend,
    is_ocr_available,
    ocr_pdf_page,
)
from src.ingestion.pdf_stats import PDFLoadReport
from src.utils.config import get_ingestion_settings, get_ocr_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

PageMode = Literal["image", "text", "mixed"]

# Mẫu nhận diện text ẩn chữ ký số (không phải nội dung BCTC)
_SIGNATURE_PATTERNS = (
    r"digitally signed by",
    r"foxit reader version",
    r"reason:\s*i am the author",
    r"your signing location here",
    r"oid\.0\.9\.2342",
)


@dataclass
class PageContent:
    """Kết quả trích xuất một trang PDF."""
    company: str
    source_file: str
    page_number: int
    text: str
    metadata: dict = field(default_factory=dict)


def _clean_text(raw: str) -> str:
    """Chuẩn hoá khoảng trắng, loại bỏ ký tự rác."""
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    raw = re.sub(r"[ \t]+", " ", raw)
    return raw.strip()


def _bbox_area(bbox: tuple[float, float, float, float]) -> float:
    x0, y0, x1, y1 = bbox
    return max(0.0, x1 - x0) * max(0.0, y1 - y0)


def _ocr_enabled() -> bool:
    cfg = get_ocr_settings()
    return bool(cfg.get("enabled", True)) and is_ocr_available()


def _image_coverage(page: fitz.Page) -> float:
    """Tỷ lệ diện tích trang bị ảnh phủ (0.0–1.0)."""
    page_area = page.rect.width * page.rect.height
    if page_area <= 0:
        return 0.0

    max_coverage = 0.0
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 1:
            coverage = _bbox_area(tuple(block["bbox"])) / page_area
            max_coverage = max(max_coverage, coverage)
    return max_coverage


def _is_signature_junk(text: str) -> bool:
    """Text ẩn từ chữ ký số / metadata PDF — không phải nội dung tài chính."""
    lower = text.lower()
    hits = sum(1 for pattern in _SIGNATURE_PATTERNS if re.search(pattern, lower))
    if hits >= 2:
        return True
    return hits >= 1 and len(text) < 500


def _is_meaningful_text(text: str) -> bool:
    """Text layer có nội dung BCTC thực sự (không phải metadata rác)."""
    cfg = get_ocr_settings()
    min_chars = int(cfg.get("min_meaningful_text_chars", 40))
    if not text or len(text) < min_chars:
        return False
    return not _is_signature_junk(text)


def _merge_text_sources(native: str, ocr: str) -> str:
    """
    Gộp text layer và OCR, tránh trùng lặp đơn giản.

    Args:
        native: Text đọc trực tiếp từ PDF.
        ocr: Text từ OCR.

    Returns:
        Chuỗi đã gộp.
    """
    if native and not ocr:
        return native
    if ocr and not native:
        return ocr
    if not native and not ocr:
        return ""

    n_norm = re.sub(r"\s+", " ", native.lower())
    o_norm = re.sub(r"\s+", " ", ocr.lower())

    if n_norm == o_norm or native in ocr:
        return ocr
    if ocr in native:
        return native

    return f"{native}\n\n---\n\n{ocr}"


def classify_page(page: fitz.Page) -> PageMode:
    """
    Phân loại trang PDF.

    Returns:
        - 'text':  chủ yếu text layer (ảnh nhỏ / không đáng kể)
        - 'image': ảnh phủ lớn, không có text layer hữu ích
        - 'mixed': vừa có text layer hữu ích vừa có ảnh đáng kể
    """
    cfg = get_ocr_settings()
    image_threshold = float(cfg.get("image_page_coverage_threshold", 0.55))
    mixed_threshold = float(cfg.get("mixed_image_coverage_threshold", 0.10))

    native = _clean_text(page.get_text("text"))
    coverage = _image_coverage(page)
    meaningful = _is_meaningful_text(native)

    if coverage >= image_threshold:
        return "mixed" if meaningful else "image"

    if coverage >= mixed_threshold and meaningful:
        return "mixed"

    return "text"


def _run_ocr(page: fitz.Page, cached_text: str | None = None) -> str:
    """Chạy OCR an toàn, trả về chuỗi rỗng nếu thất bại."""
    if cached_text is not None:
        return _clean_text(cached_text)
    if not _ocr_enabled():
        return ""
    try:
        return _clean_text(ocr_pdf_page(page, cached_text=cached_text))
    except Exception as exc:
        logger.warning(f"[PDFLoader] OCR trang {page.number + 1} thất bại: {exc}")
        return ""


def _extract_page_text(
    page: fitz.Page,
    page_mode: PageMode,
    cached_ocr: str | None = None,
) -> tuple[str, str, PageMode, str | None]:
    """
    Trích xuất text theo loại trang.

    Returns:
        (text, extract_method, page_mode, ocr_raw_for_cache)
        extract_method: 'native', 'ocr', 'mixed', hoặc ''.
        ocr_raw_for_cache: text OCR thuần để lưu cache (None nếu không OCR).
    """
    raw_native = _clean_text(page.get_text("text"))
    native = raw_native if _is_meaningful_text(raw_native) else ""
    ocr_for_cache: str | None = None

    if page_mode == "text":
        if native:
            return native, "native", page_mode, None
        logger.debug(f"  Trang {page.number + 1} (text): không có nội dung.")
        return "", "", page_mode, None

    if page_mode == "image":
        if cached_ocr is not None:
            ocr_text = _clean_text(cached_ocr)
        else:
            ocr_text = _run_ocr(page)
            ocr_for_cache = ocr_text or None
        if ocr_text:
            logger.debug(f"  Trang {page.number + 1} (image): OCR OK.")
            return ocr_text, "ocr", page_mode, ocr_for_cache
        return "", "", page_mode, None

    # mixed — gộp text layer + OCR
    if cached_ocr is not None:
        ocr_text = _clean_text(cached_ocr)
    else:
        ocr_text = _run_ocr(page)
        ocr_for_cache = ocr_text or None
    combined = _merge_text_sources(native, ocr_text)
    if combined:
        method = "mixed" if native and ocr_text else ("native" if native else "ocr")
        logger.debug(f"  Trang {page.number + 1} (mixed): {method}.")
        return combined, method, page_mode, ocr_for_cache

    if native:
        return native, "native", page_mode, None

    return "", "", page_mode, None


def load_pdf(
    pdf_path: Path,
    company: str,
    on_page_progress=None,  # deprecated — tương thích cache cũ
    file_hash: str | None = None,
    **kwargs,
) -> tuple[list[PageContent], PDFLoadReport]:
    """
    Mở một file PDF và trả về danh sách PageContent mỗi trang.

    Args:
        pdf_path: Đường dẫn tới file PDF.
        company: Tên công ty / collection (dùng làm metadata).

    Returns:
        Tuple (danh_sách_trang, báo_cáo_đọc_pdf).
    """
    _ = on_page_progress, kwargs
    logger.info(f"[PDFLoader] Đang xử lý: {pdf_path.name} ({company})")
    pages: list[PageContent] = []
    report = PDFLoadReport(ocr_available=is_ocr_available())

    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        logger.error(f"[PDFLoader] Không thể mở PDF {pdf_path}: {exc}")
        return pages, report

    report.total_pages = len(doc)

    ocr_cfg = get_ocr_settings()
    zoom = float(ocr_cfg.get("zoom", 1.0))
    backend = get_effective_backend()
    ocr_cache = load_ocr_cache(file_hash or "", backend, zoom) if file_hash else None
    new_ocr_pages: dict[int, str] = {}

    # ── Xử lý tuần tự từng trang để tránh deadlock của PyTorch/EasyOCR trên CPU ──
    min_confidence = float(ocr_cfg.get("min_confidence", 0.3))
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1
        page_mode = classify_page(page)

        cached_ocr = ocr_cache.get(str(page_num)) if ocr_cache else None
        
        # Trích xuất văn bản trang
        raw_native = _clean_text(page.get_text("text"))
        meaningful_native = raw_native if _is_meaningful_text(raw_native) else ""
        ocr_text = ""
        ocr_raw_for_cache = None

        if page_mode == "text":
            text = meaningful_native
            extract_method = "native" if meaningful_native else ""
        elif page_mode == "image":
            if cached_ocr is not None:
                ocr_text = _clean_text(cached_ocr)
                extract_method = "ocr" if ocr_text else ""
            elif _ocr_enabled():
                logger.info(f"[PDFLoader] Chạy OCR trang {page_num}/{len(doc)}…")
                ocr_text = _run_ocr(page)
                ocr_raw_for_cache = ocr_text or None
                extract_method = "ocr" if ocr_text else ""
            else:
                ocr_text = ""
                extract_method = ""
            text = ocr_text
        else:  # mixed
            if cached_ocr is not None:
                ocr_text = _clean_text(cached_ocr)
            elif _ocr_enabled():
                logger.info(f"[PDFLoader] Chạy OCR trang {page_num}/{len(doc)} (trang hỗn hợp)…")
                ocr_text = _run_ocr(page)
                ocr_raw_for_cache = ocr_text or None
            
            combined = _merge_text_sources(meaningful_native, ocr_text)
            text = combined
            if combined:
                extract_method = (
                    "mixed" if meaningful_native and ocr_text
                    else ("native" if meaningful_native else "ocr")
                )
            else:
                text = meaningful_native
                extract_method = "native" if meaningful_native else ""

        if ocr_raw_for_cache:
            new_ocr_pages[page_num] = ocr_raw_for_cache

        # Cập nhật report
        if page_mode == "image":
            report.image_pages += 1
        elif page_mode == "mixed":
            report.mixed_pages += 1
        else:
            report.text_pages += 1

        if not text:
            report.skipped_pages += 1
            continue

        if extract_method == "mixed":
            report.mixed_extract_pages += 1
        elif extract_method == "ocr":
            report.ocr_pages += 1
        else:
            report.native_text_pages += 1

        pages.append(
            PageContent(
                company=company,
                source_file=str(pdf_path),
                page_number=page_idx + 1,
                text=text,
                metadata={
                    "company": company,
                    "file_name": pdf_path.name,
                    "page": page_idx + 1,
                    "total_pages": len(doc),
                    "extract_method": extract_method,
                    "page_mode": page_mode,
                },
            )
        )

    doc.close()

    if file_hash and new_ocr_pages:
        merged = dict(ocr_cache or {})
        merged.update({str(k): v for k, v in new_ocr_pages.items()})
        save_ocr_cache(file_hash, backend, zoom, {int(k): v for k, v in merged.items()})

    logger.info(
        f"[PDFLoader] Trích xuất {len(pages)} trang từ {pdf_path.name} "
        f"({report.summary_line()})"
    )

    warning = report.build_warning(
        min_readable_ratio=get_ingestion_settings().get("min_readable_page_ratio", 0.5)
    )
    if warning:
        logger.warning(f"[PDFLoader] {warning}")

    return pages, report


def load_company_pdfs(company_dir: Path, company: str) -> tuple[list[PageContent], PDFLoadReport]:
    """
    Duyệt toàn bộ PDF trong thư mục của một công ty.

    Returns:
        Tuple (tất_cả_trang, báo_cáo_gộp).
    """
    all_pages: list[PageContent] = []
    combined = PDFLoadReport(ocr_available=is_ocr_available())
    pdf_files = sorted(company_dir.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"[PDFLoader] Không tìm thấy PDF nào trong {company_dir}")
        return all_pages, combined

    for pdf_file in pdf_files:
        file_hash = hashlib.md5(pdf_file.read_bytes()).hexdigest()[:8]
        pages, report = load_pdf(pdf_file, company, file_hash=file_hash)
        all_pages.extend(pages)
        combined.merge(report)

    logger.info(
        f"[PDFLoader] Công ty '{company}': tổng {len(all_pages)} trang từ "
        f"{len(pdf_files)} file ({combined.summary_line()})."
    )
    return all_pages, combined


def iter_all_companies(
    raw_pdf_root: Path,
) -> Iterator[tuple[str, list[PageContent], PDFLoadReport]]:
    """
    Generator duyệt qua tất cả thư mục công ty trong raw_pdf_root.

    Yields:
        Tuple (company_name, pages, report).
    """
    for company_dir in sorted(raw_pdf_root.iterdir()):
        if company_dir.is_dir():
            pages, report = load_company_pdfs(company_dir, company_dir.name)
            yield company_dir.name, pages, report