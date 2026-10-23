"""
chroma_client.py — Module 02: Quản lý kết nối và collection ChromaDB.

Mỗi công ty tương ứng với một collection riêng biệt trong ChromaDB.
"""

from __future__ import annotations

import chromadb
from chromadb.config import Settings

from src.utils.config import CHROMA_DB_DIR, get_chroma_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Singleton client
_client: chromadb.PersistentClient | None = None


def get_client() -> chromadb.PersistentClient:
    """Trả về ChromaDB client (singleton, persistent)."""
    global _client
    if _client is None:
        CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)
        cfg = get_chroma_settings()
        _client = chromadb.PersistentClient(
            path=str(CHROMA_DB_DIR),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True,
            ),
        )
        logger.info(f"[ChromaClient] Kết nối ChromaDB tại: {CHROMA_DB_DIR}")
    return _client


def get_chroma_collection(
    company: str,
    force_reingest: bool = False,
) -> chromadb.Collection:
    """
    Lấy hoặc tạo collection cho một công ty.

    Args:
        company: Tên công ty (dùng làm tên collection).
        force_reingest: Nếu True, xoá collection cũ trước khi tạo mới.

    Returns:
        chromadb.Collection đã sẵn sàng sử dụng.
    """
    client = get_client()
    collection_name = _sanitize_collection_name(company)

    if force_reingest:
        try:
            client.delete_collection(collection_name)
            logger.info(f"[ChromaClient] Đã xoá collection '{collection_name}'.")
        except Exception:
            pass  # Collection chưa tồn tại

    collection = client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"},  # Sử dụng cosine similarity
    )
    logger.debug(
        f"[ChromaClient] Collection '{collection_name}': "
        f"{collection.count()} documents hiện tại."
    )
    return collection


def list_collections() -> list[str]:
    """Liệt kê tên tất cả collection đang tồn tại."""
    client = get_client()
    return [col.name for col in client.list_collections()]


def get_collection_stats() -> dict[str, int]:
    """Trả về dict {collection_name: số_documents}."""
    client = get_client()
    stats: dict[str, int] = {}
    for col in client.list_collections():
        stats[col.name] = col.count()
    return stats


def reset_all() -> None:
    """XOÁ toàn bộ dữ liệu ChromaDB. Cẩn thận!"""
    client = get_client()
    client.reset()
    logger.warning("[ChromaClient] Đã reset toàn bộ ChromaDB.")


def _sanitize_collection_name(name: str) -> str:
    """ChromaDB chỉ chấp nhận tên [a-zA-Z0-9_-] và 3–63 ký tự."""
    import re
    name = re.sub(r"[^a-zA-Z0-9_\-]", "_", name)
    name = name[:63]
    if len(name) < 3:
        name = name.ljust(3, "_")
    return name
