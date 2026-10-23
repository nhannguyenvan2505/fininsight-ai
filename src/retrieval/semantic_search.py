"""
semantic_search.py — Module 03: Semantic search qua ChromaDB + vector embedding.
"""

from __future__ import annotations

from src.ingestion.embedder import embed_query
from src.storage.chroma_client import get_chroma_collection
from src.utils.config import get_retrieval_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def semantic_search(
    query: str,
    company: str,
    top_k: int | None = None,
    where: dict | None = None,
) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa (vector similarity) trong ChromaDB.

    Args:
        query: Câu hỏi / truy vấn.
        company: Tên công ty (tên collection ChromaDB).
        top_k: Số kết quả trả về. Mặc định từ config.
        where: Filter metadata ChromaDB (optional).

    Returns:
        Danh sách dict gồm id, text, metadata, semantic_score.
    """
    cfg = get_retrieval_settings()
    top_k = top_k or cfg.get("semantic_top_k", 5)

    query_vector = embed_query(query)
    collection = get_chroma_collection(company)

    query_kwargs: dict = {
        "query_embeddings": [query_vector],
        "n_results": min(top_k, max(collection.count(), 1)),
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        query_kwargs["where"] = where

    result = collection.query(**query_kwargs)

    results: list[dict] = []
    for idx in range(len(result["ids"][0])):
        # ChromaDB trả về distance (cosine) — chuyển sang similarity
        distance = result["distances"][0][idx]
        similarity = 1.0 - distance  # cosine space

        results.append(
            {
                "id": result["ids"][0][idx],
                "text": result["documents"][0][idx],
                "metadata": result["metadatas"][0][idx],
                "semantic_score": similarity,
            }
        )

    logger.debug(f"[Semantic] Query '{query[:40]}' → {len(results)} kết quả.")
    return results


def semantic_search_multi_company(
    query: str,
    companies: list[str],
    top_k: int = 5,
) -> list[dict]:
    """
    Tìm kiếm ngữ nghĩa trên nhiều công ty và gộp kết quả.

    Args:
        query: Câu truy vấn.
        companies: Danh sách tên công ty.
        top_k: Số kết quả trả về mỗi công ty.

    Returns:
        Danh sách kết quả gộp, sắp xếp theo semantic_score giảm dần.
    """
    all_results: list[dict] = []
    for company in companies:
        results = semantic_search(query, company, top_k=top_k)
        for r in results:
            r["company"] = company
        all_results.extend(results)

    all_results.sort(key=lambda x: x["semantic_score"], reverse=True)
    return all_results[:top_k]
