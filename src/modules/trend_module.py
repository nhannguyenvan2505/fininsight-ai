"""
trend_module.py — Module 06: Phân tích xu hướng tài chính theo thời gian.
"""

from __future__ import annotations

from src.llm.prompt_templates import trend_prompt
from src.llm.qwen_client import call_llm
from src.retrieval.hybrid_search import hybrid_search
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Từ khoá để phát hiện dữ liệu nhiều năm trong truy vấn
_YEAR_KEYWORDS = ["xu hướng", "qua các năm", "tăng trưởng", "biến động", "so với năm"]


def analyze_trend(
    question: str,
    company: str,
    top_k: int = 8,
) -> dict:
    """
    Phân tích xu hướng tài chính của một công ty.

    Args:
        question: Câu hỏi về xu hướng.
        company: Tên công ty.
        top_k: Số chunk context (tăng lên để cover nhiều năm).

    Returns:
        Dict gồm: analysis, company, sources.
    """
    logger.info(f"[Trend] Phân tích xu hướng '{company}' | Câu hỏi: {question[:60]}")

    # Tăng top_k để đảm bảo lấy dữ liệu nhiều năm
    chunks = hybrid_search(question, company, top_k=top_k)

    if not chunks:
        return {
            "analysis": f"Không tìm thấy dữ liệu xu hướng cho '{company}'.",
            "company": company,
            "sources": [],
        }

    prompt = trend_prompt(question, chunks, company)
    result = call_llm(
        prompt=prompt,
        system_prompt=(
            "Bạn là chuyên gia phân tích xu hướng tài chính. "
            "Phân tích dựa trên số liệu thực tế, đưa ra nhận xét khách quan và có căn cứ."
        ),
        temperature=0.3,
    )

    sources = [
        {
            "company": c.get("company", company),
            "file_name": c.get("metadata", {}).get("file_name", ""),
            "page": c.get("metadata", {}).get("page", ""),
        }
        for c in chunks
    ]

    return {
        "analysis": result,
        "company": company,
        "sources": sources,
    }
