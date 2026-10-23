"""
hybrid_search.py — Module 03: Kết hợp BM25 + Semantic search theo Reciprocal Rank Fusion (RRF).

RRF formula: score(d) = Σ 1 / (k + rank(d))
- k = 60 (hằng số giảm độ nhạy cảm với hạng đầu)
"""

from __future__ import annotations

from src.retrieval.bm25_search import bm25_search, build_bm25_index
from src.retrieval.semantic_search import semantic_search
from src.utils.config import get_retrieval_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

_RRF_K = 60


def _rrf_score(rank: int, k: int = _RRF_K) -> float:
    return 1.0 / (k + rank + 1)


def hybrid_search(
    query: str,
    company: str,
    top_k: int | None = None,
    bm25_weight: float = 0.4,
    semantic_weight: float = 0.6,
) -> list[dict]:
    """
    Hybrid search kết hợp BM25 và Semantic search.

    Args:
        query: Câu truy vấn.
        company: Tên công ty.
        top_k: Số kết quả cuối cùng trả về.
        bm25_weight: Trọng số cho BM25 (mặc định 0.4).
        semantic_weight: Trọng số cho Semantic (mặc định 0.6).

    Returns:
        Danh sách kết quả đã re-rank, mỗi phần tử gồm:
        id, text, metadata, hybrid_score, bm25_score, semantic_score.
    """
    cfg = get_retrieval_settings()
    top_k = top_k or cfg.get("hybrid_top_k", 6)
    fetch_k = top_k * 3  # Lấy nhiều hơn để RRF có đủ ứng viên

    # Đảm bảo BM25 index đã build
    build_bm25_index(company)

    # Chạy song song hai loại search
    bm25_results = bm25_search(query, company, top_k=fetch_k)
    semantic_results = semantic_search(query, company, top_k=fetch_k)

    # ─── RRF Fusion ───────────────────────────────────────────────────────────
    scores: dict[str, dict] = {}

    for rank, res in enumerate(bm25_results):
        doc_id = res["id"]
        if doc_id not in scores:
            scores[doc_id] = {"text": res["text"], "metadata": res.get("metadata", {}), "hybrid_score": 0.0,
                               "bm25_score": 0.0, "semantic_score": 0.0}
        scores[doc_id]["bm25_score"] = res["bm25_score"]
        scores[doc_id]["hybrid_score"] += bm25_weight * _rrf_score(rank)

    for rank, res in enumerate(semantic_results):
        doc_id = res["id"]
        if doc_id not in scores:
            scores[doc_id] = {"text": res["text"], "metadata": res["metadata"],
                               "hybrid_score": 0.0, "bm25_score": 0.0, "semantic_score": 0.0}
        scores[doc_id]["semantic_score"] = res["semantic_score"]
        scores[doc_id]["metadata"] = res["metadata"]
        scores[doc_id]["text"] = res["text"]
        scores[doc_id]["hybrid_score"] += semantic_weight * _rrf_score(rank)

    # Sắp xếp theo hybrid_score giảm dần
    ranked = sorted(scores.items(), key=lambda x: x[1]["hybrid_score"], reverse=True)

    results = [
        {
            "id": doc_id,
            "company": company,
            **info,
        }
        for doc_id, info in ranked[:top_k]
    ]

    logger.info(
        f"[Hybrid] '{query[:40]}' | company={company} | "
        f"bm25={len(bm25_results)}, semantic={len(semantic_results)} → top{top_k}"
    )
    return results


def hybrid_search_multi_company(
    query: str,
    companies: list[str],
    top_k: int = 6,
    bm25_weight: float = 0.4,
    semantic_weight: float = 0.6,
) -> list[dict]:
    """
    Hybrid search trên nhiều công ty, gộp và re-rank toàn cục.

    Args:
        query: Câu truy vấn.
        companies: Danh sách tên công ty.
        top_k: Số kết quả cuối trả về.

    Returns:
        Danh sách kết quả đã gộp và sắp xếp.
    """
    all_results: list[dict] = []
    for company in companies:
        results = hybrid_search(
            query, company,
            top_k=top_k,
            bm25_weight=bm25_weight,
            semantic_weight=semantic_weight,
        )
        all_results.extend(results)

    # Re-rank toàn cục
    all_results.sort(key=lambda x: x["hybrid_score"], reverse=True)
    return all_results[:top_k]
