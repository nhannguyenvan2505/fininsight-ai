"""Cache kết quả OCR theo hash file — upload lại cùng PDF gần như tức thì."""

from __future__ import annotations

import json
from pathlib import Path

from src.utils.config import DATA_PROCESSED_DIR, get_ocr_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_CACHE_DIR = DATA_PROCESSED_DIR / "ocr_cache"


def _cache_enabled() -> bool:
    return bool(get_ocr_settings().get("cache_enabled", True))


def _cache_path(file_hash: str, backend: str, zoom: float) -> Path:
    key = f"{file_hash}_{backend}_z{zoom}".replace(".", "p")
    return _CACHE_DIR / f"{key}.json"


def load_ocr_cache(file_hash: str, backend: str, zoom: float) -> dict[str, str] | None:
    """Đọc cache OCR: {page_number_str: text}."""
    if not _cache_enabled() or not file_hash:
        return None
    path = _cache_path(file_hash, backend, zoom)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            logger.info(f"[OCRCache] Hit cache {path.name} ({len(data)} trang)")
            return {str(k): str(v) for k, v in data.items()}
    except Exception as exc:
        logger.warning(f"[OCRCache] Không đọc được cache: {exc}")
    return None


def save_ocr_cache(
    file_hash: str,
    backend: str,
    zoom: float,
    pages: dict[int, str],
) -> None:
    """Lưu toàn bộ OCR của file."""
    if not _cache_enabled() or not file_hash or not pages:
        return
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(file_hash, backend, zoom)
    payload = {str(k): v for k, v in sorted(pages.items())}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    logger.info(f"[OCRCache] Đã lưu {len(pages)} trang → {path.name}")
