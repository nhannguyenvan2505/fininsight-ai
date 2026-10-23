"""
bm25_search.py — Module 03: BM25 full-text search cho hybrid retrieval.

Dùng rank_bm25 để tính điểm BM25 trên corpus đã được index trước.
Index được cache in-memory theo company để tránh rebuild mỗi lần.
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from src.storage.chroma_client import get_chroma_collection
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache BM25 index: {company: (corpus_ids, BM25Okapi)}
_bm25_cache: dict[str, tuple[list[str], list[str], BM25Okapi]] = {}
_metadata_cache: dict[str, list[dict]] = {}


def invalidate_bm25_index(company: str) -> None:
    """Invalidate derived search data after a collection mutation."""
    _bm25_cache.pop(company, None)
    _metadata_cache.pop(company, None)


def _tokenize(text: str) -> list[str]:
    """Tokenize đơn giản: lowercase + tách từ."""
    text = text.lower()
    # Giữ lại chữ cái tiếng Việt, số, và khoảng trắng
    tokens = re.findall(r"[a-zàáâãèéêìíòóôõùúăđĩũơưạắặầẩậéếệỉịọộợờởợụứựỳỵỷỹ0-9]+", text)
    return tokens if tokens else text.split()


def build_bm25_index(company: str, force_rebuild: bool = False) -> None:
    """
    Xây dựng BM25 index cho một công ty từ ChromaDB.

    Args:
        company: Tên công ty.
        force_rebuild: Xây dựng lại dù đã cache.
    """
    if company in _bm25_cache and not force_rebuild:
        return

    logger.info(f"[BM25] Đang build index cho '{company}'…")
    collection = get_chroma_collection(company)
    n_docs = collection.count()

    if n_docs == 0:
        invalidate_bm25_index(company)
        logger.warning(f"[BM25] Collection '{company}' rỗng. Bỏ qua.")
        return

    # Lấy tất cả document (ChromaDB giới hạn limit)
    result = collection.get(include=["documents", "metadatas"])
    ids: list[str] = result["ids"]
    docs: list[str] = result["documents"]

    tokenized_corpus = [_tokenize(doc) for doc in docs]
    bm25 = BM25Okapi(tokenized_corpus)
    _bm25_cache[company] = (ids, docs, bm25)
    _metadata_cache[company] = result.get("metadatas") or [{} for _ in ids]
    logger.info(f"[BM25] Index '{company}' sẵn sàng: {len(ids)} documents.")


def bm25_search(
    query: str,
    company: str,
    top_k: int = 5,
) -> list[dict]:
    """
    Tìm kiếm BM25 trên corpus của một công ty.

    Args:
        query: Câu truy vấn.
        company: Tên công ty.
        top_k: Số kết quả trả về.

    Returns:
        Danh sách dict gồm id, text, score.
    """
    if company not in _bm25_cache:
        build_bm25_index(company)

    if company not in _bm25_cache:
        logger.warning(f"[BM25] Không có index cho '{company}'.")
        return []

    ids, docs, bm25 = _bm25_cache[company]
    tokenized_query = _tokenize(query)
    scores = bm25.get_scores(tokenized_query)

    # Lấy top_k indices theo score
    top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

    results = [
        {"id": ids[i], "text": docs[i], "bm25_score": float(scores[i]),
         "metadata": _metadata_cache[company][i] or {}}
        for i in top_indices
        if scores[i] > 0
    ]
    logger.debug(f"[BM25] Query '{query[:40]}' → {len(results)} kết quả.")
    return results
