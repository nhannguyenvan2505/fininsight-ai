"""
summary_module.py — Module 08: Tạo báo cáo tóm tắt tài chính doanh nghiệp.
"""

from __future__ import annotations

from src.llm.prompt_templates import summary_prompt
from src.llm.qwen_client import call_llm
from src.retrieval.hybrid_search import hybrid_search
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Các chủ đề tóm tắt được hỗ trợ
SUMMARY_FOCUSES = {
    "tổng quan": "tổng quan tình hình tài chính",
    "lợi nhuận": "kết quả hoạt động kinh doanh và lợi nhuận",
    "thanh khoản": "khả năng thanh khoản và dòng tiền",
    "tăng trưởng": "tốc độ tăng trưởng và tiềm năng phát triển",
    "rủi ro": "các rủi ro tài chính và hoạt động",
}

# Các câu hỏi mặc định để thu thập chunk cho từng tiêu điểm
_FOCUS_QUERIES = {
    "tổng quan": "tổng quan tài chính doanh thu lợi nhuận tài sản vốn chủ sở hữu",
    "lợi nhuận": "lợi nhuận sau thuế doanh thu chi phí ROE ROA EPS",
    "thanh khoản": "tiền mặt thanh khoản dòng tiền ngắn hạn nợ phải trả",
    "tăng trưởng": "tăng trưởng doanh thu mở rộng thị trường đầu tư",
    "rủi ro": "rủi ro tài chính nợ vay đòn bẩy tài chính biến động",
}


def generate_summary(
    company: str,
    focus: str = "tổng quan",
    top_k: int = 10,
) -> dict:
    """
    Tạo báo cáo tóm tắt tài chính cho một công ty.

    Args:
        company: Tên công ty.
        focus: Tiêu điểm tóm tắt (xem SUMMARY_FOCUSES).
        top_k: Số chunk context (tăng lên để bao quát).

    Returns:
        Dict gồm: summary, company, focus, sources.
    """
    focus_desc = SUMMARY_FOCUSES.get(focus, focus)
    query = _FOCUS_QUERIES.get(focus, focus)

    logger.info(f"[Summary] Tóm tắt '{company}' với tiêu điểm: {focus_desc}")

    chunks = hybrid_search(query, company, top_k=top_k)

    if not chunks:
        return {
            "summary": f"Không tìm thấy dữ liệu để tóm tắt cho '{company}'.",
            "company": company,
            "focus": focus,
            "sources": [],
        }

    prompt = summary_prompt(company, chunks, focus=focus_desc)
    result = call_llm(
        prompt=prompt,
        system_prompt=(
            "Bạn là chuyên gia tư vấn tài chính cấp cao, chuyên soạn báo cáo phân tích "
            "doanh nghiệp cho nhà đầu tư. Viết rõ ràng, có cấu trúc, dựa trên số liệu thực."
        ),
        temperature=0.25,
        max_tokens=3000,
    )

    sources = [
        {
            "company": company,
            "file_name": c.get("metadata", {}).get("file_name", ""),
            "page": c.get("metadata", {}).get("page", ""),
        }
        for c in chunks
    ]

    return {
        "summary": result,
        "company": company,
        "focus": focus,
        "sources": sources,
    }


def generate_full_report(company: str) -> dict:
    """
    Tạo báo cáo đầy đủ cho tất cả các tiêu điểm.

    Returns:
        Dict {focus: summary_result}.
    """
    logger.info(f"[Summary] Tạo báo cáo đầy đủ cho '{company}'")
    return {focus: generate_summary(company, focus) for focus in SUMMARY_FOCUSES}
