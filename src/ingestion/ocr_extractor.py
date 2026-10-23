"""
ocr_extractor.py — OCR cho PDF dạng ảnh / scan.

Backend:
- rapidocr (mặc định): nhanh ~5–10x so với EasyOCR trên CPU
- easyocr: chậm hơn, đôi khi chính xác hơn với tiếng Việt phức tạp
"""

from __future__ import annotations

from typing import Any

import fitz
import numpy as np

from src.utils.config import get_ocr_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_rapid_engine: Any | None = None
_easy_reader: Any | None = None
_ocr_init_failed: bool = False
_rapid_failed: bool = False  # True khi RapidOCR không khả dụng


def _backend() -> str:
    """Backend OCR thực tế — auto chọn RapidOCR nếu đã cài."""
    global _rapid_failed
    cfg = get_ocr_settings()
    preferred = str(cfg.get("backend", "auto")).lower()
    if not _rapid_failed and preferred in ("auto", "rapidocr"):
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401
            return "rapidocr"
        except Exception:
            _rapid_failed = True
            if preferred == "rapidocr":
                logger.warning("[OCR] RapidOCR chưa cài — dùng EasyOCR.")
    return "easyocr"


def preload_ocr() -> None:
    """Tải sẵn engine OCR khi mở app (tránh chờ lần upload đầu)."""
    if not is_ocr_available():
        return
    backend = get_effective_backend()
    if backend == "rapidocr":
        _get_rapid_engine()
    else:
        _get_easy_reader()


def get_effective_backend() -> str:
    """Public alias — backend OCR đang dùng."""
    return _backend()


def is_ocr_available() -> bool:
    """Kiểm tra OCR backend đã sẵn sàng."""
    if _ocr_init_failed:
        return False
    if _backend() == "rapidocr":
        try:
            from rapidocr_onnxruntime import RapidOCR  # noqa: F401
            return True
        except Exception:
            pass
    try:
        import easyocr  # noqa: F401
        import torch
        _ = torch.__version__
        return True
    except Exception:
        return False


def _page_to_image(page: fitz.Page, zoom: float) -> np.ndarray:
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
    image = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    if pixmap.n == 4:
        image = image[:, :, :3]
    return image


def _get_rapid_engine() -> Any:
    global _rapid_engine, _ocr_init_failed, _rapid_failed
    if _ocr_init_failed:
        raise RuntimeError("OCR engine không khởi tạo được.")
    if _rapid_engine is not None:
        return _rapid_engine
    try:
        from rapidocr_onnxruntime import RapidOCR

        logger.info("[OCR] Đang tải RapidOCR (onnxruntime)…")
        _rapid_engine = RapidOCR()
        logger.info("[OCR] RapidOCR sẵn sàng.")
        return _rapid_engine
    except Exception as exc:
        _rapid_failed = True
        logger.warning(f"[OCR] RapidOCR thất bại: {exc}. Thử EasyOCR…")
        raise


def _get_easy_reader(languages: list[str] | None = None) -> Any:
    global _easy_reader, _ocr_init_failed
    if _ocr_init_failed:
        raise RuntimeError("OCR reader không khởi tạo được.")
    if _easy_reader is not None:
        return _easy_reader
    cfg = get_ocr_settings()
    langs = languages or cfg.get("languages", ["vi", "en"])
    try:
        import easyocr

        logger.info(f"[OCR] Đang tải EasyOCR (languages={langs})…")
        _easy_reader = easyocr.Reader(langs, gpu=False, verbose=False)
        logger.info("[OCR] EasyOCR sẵn sàng.")
        return _easy_reader
    except Exception as exc:
        _ocr_init_failed = True
        logger.error(f"[OCR] Không khởi tạo được reader: {exc}")
        raise


def _ocr_with_rapid(image: np.ndarray, min_confidence: float) -> str:
    engine = _get_rapid_engine()
    result, _elapse = engine(image)
    if not result:
        return ""
    lines: list[str] = []
    for item in result:
        if len(item) < 3:
            continue
        text, score = str(item[1]), float(item[2])
        if score >= min_confidence and text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def _ocr_with_easy(image: np.ndarray, min_confidence: float) -> str:
    reader = _get_easy_reader()
    results = reader.readtext(image)
    lines: list[str] = []
    for item in results:
        if len(item) < 3:
            continue
        _bbox, text, confidence = item[0], item[1], float(item[2])
        if confidence >= min_confidence and text.strip():
            lines.append(text.strip())
    return "\n".join(lines)


def ocr_pdf_page(
    page: fitz.Page,
    zoom: float | None = None,
    *,
    cached_text: str | None = None,
) -> str:
    """
    OCR một trang PDF (render ảnh → nhận dạng chữ).

    Args:
        page: Trang PyMuPDF.
        zoom: Hệ số phóng đại ảnh (mặc định từ config).
        cached_text: Text OCR đã cache — bỏ qua OCR nếu có.

    Returns:
        Văn bản nhận dạng được, hoặc chuỗi rỗng nếu thất bại.
    """
    if cached_text is not None:
        return cached_text

    cfg = get_ocr_settings()
    zoom = zoom if zoom is not None else cfg.get("zoom", 1.5)
    min_confidence = float(cfg.get("min_confidence", 0.3))
    image = _page_to_image(page, zoom)

    backend = _backend()
    try:
        if backend == "rapidocr":
            text = _ocr_with_rapid(image, min_confidence)
        else:
            text = _ocr_with_easy(image, min_confidence)
    except Exception as exc:
        logger.warning(f"[OCR] {backend} trang {page.number + 1} lỗi: {exc}")
        if backend == "rapidocr":
            # RapidOCR lỗi → fallback sang EasyOCR (không dùng lại engine cũ)
            global _rapid_failed
            _rapid_failed = True
            logger.info("[OCR] Chuyển sang EasyOCR do RapidOCR thất bại.")
            text = _ocr_with_easy(image, min_confidence)
        else:
            raise

    logger.debug(
        f"[OCR] Trang {page.number + 1} ({backend}): {len(text)} ký tự."
    )
    return text
