"""
comparison_module.py — Module 05: So sánh tài chính giữa các doanh nghiệp.
"""

from __future__ import annotations

from src.llm.prompt_templates import comparison_prompt
from src.llm.qwen_client import call_llm
from src.retrieval.hybrid_search import hybrid_search
from src.utils.logger import get_logger

logger = get_logger(__name__)


def compare_companies(
    question: str,
    companies: list[str],
    top_k_per_company: int = 4,
) -> dict:
    """
    So sánh các doanh nghiệp theo câu hỏi của người dùng.

    Args:
        question: Câu hỏi so sánh (ví dụ: "So sánh ROE của FPT và Vinamilk").
        companies: Danh sách tên công ty cần so sánh.
        top_k_per_company: Số chunk lấy mỗi công ty.

    Returns:
        Dict gồm: comparison, companies, sources.
    """
    companies = list(dict.fromkeys(companies))
    if len(companies) < 2:
        return {
            "comparison": "Cần ít nhất hai tài liệu khác nhau để so sánh.",
            "companies": companies,
            "sources": [],
        }
    logger.info(f"[Comparison] So sánh {companies} | Câu hỏi: {question[:60]}")

    # Thu thập chunks từ từng công ty
    all_chunks: list[dict] = []
    for company in companies:
        chunks = hybrid_search(question, company, top_k=top_k_per_company)
        for c in chunks:
            c.setdefault("company", company)
        all_chunks.extend(chunks)

    if not all_chunks:
        return {
            "comparison": "Không tìm thấy dữ liệu để so sánh.",
            "companies": companies,
            "sources": [],
        }

    prompt = comparison_prompt(question, all_chunks, companies)
    result = call_llm(
        prompt=prompt,
        system_prompt="Bạn là chuyên gia phân tích tài chính cấp cao. Hãy so sánh khách quan, dựa trên dữ liệu.",
    )

    sources = [
        {
            "company": c.get("company", ""),
            "file_name": c.get("metadata", {}).get("file_name", ""),
            "page": c.get("metadata", {}).get("page", ""),
        }
        for c in all_chunks
    ]

    return {
        "comparison": result,
        "companies": companies,
        "sources": sources,
    }
