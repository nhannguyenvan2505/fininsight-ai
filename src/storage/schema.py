"""
schema.py — Module 02: Định nghĩa schema metadata cho ChromaDB documents.

ChromaDB không enforce schema cứng, nhưng module này chuẩn hoá
các trường metadata bắt buộc để đảm bảo nhất quán toàn hệ thống.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


# ─── Metadata Schema ──────────────────────────────────────────────────────────

@dataclass
class ChunkMetadata:
    """
    Schema chuẩn của metadata cho mỗi document trong ChromaDB.

    Tất cả trường đều phải là kiểu nguyên thuỷ (str, int, float, bool)
    vì ChromaDB không hỗ trợ nested objects.
    """
    company: str                # Ví dụ: "fpt", "vinamilk"
    file_name: str              # Tên file PDF gốc
    page: int                   # Số trang trong PDF
    total_pages: int            # Tổng số trang của file
    chunk_id: str               # ID duy nhất của chunk
    chunk_index: int            # Vị trí chunk trong trang
    chunk_total: int            # Tổng số chunk của trang


# ─── Các hằng số ──────────────────────────────────────────────────────────────

# COMPANIES được lấy động từ ChromaDB (không còn danh sách cố định)
# Dùng hàm get_available_collections() thay thế.

def get_available_collections() -> list[str]:
    """Trả về danh sách collection hiện có trong ChromaDB (tài liệu đã nạp)."""
    from src.storage.chroma_client import list_collections
    return list_collections()


REQUIRED_METADATA_KEYS = [f.name for f in ChunkMetadata.__dataclass_fields__.values()]


# ─── Hàm tiện ích ─────────────────────────────────────────────────────────────

def validate_metadata(metadata: dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Kiểm tra metadata có đủ trường bắt buộc không.

    Returns:
        (is_valid, danh_sách_lỗi)
    """
    missing = [key for key in REQUIRED_METADATA_KEYS if key not in metadata]
    return len(missing) == 0, missing


def build_metadata(
    company: str,
    file_name: str,
    page: int,
    total_pages: int,
    chunk_id: str,
    chunk_index: int,
    chunk_total: int,
    **extra,
) -> dict[str, Any]:
    """
    Tạo metadata dict chuẩn cho một chunk.

    Args:
        **extra: Các trường metadata bổ sung (tùy chọn).

    Returns:
        Dict metadata đã chuẩn hoá.
    """
    base = asdict(
        ChunkMetadata(
            company=company,
            file_name=file_name,
            page=page,
            total_pages=total_pages,
            chunk_id=chunk_id,
            chunk_index=chunk_index,
            chunk_total=chunk_total,
        )
    )
    base.update(extra)
    return base
