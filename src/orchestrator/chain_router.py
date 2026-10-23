"""
chain_router.py — Orchestrator: Định tuyến câu hỏi đến đúng module nghiệp vụ.

LangChain được dùng để phân loại ý định (intent) của câu hỏi
và điều phối đến Module 04–08 tương ứng.
"""

from __future__ import annotations

from src.llm.qwen_client import call_llm
from src.modules.comparison_module import compare_companies
from src.modules.glossary_module import explain_term
from src.modules.qa_module import answer_question
from src.modules.summary_module import generate_summary
from src.modules.trend_module import analyze_trend
from src.storage.schema import get_available_collections
from src.utils.logger import get_logger

logger = get_logger(__name__)


# ─── Intent Detection ─────────────────────────────────────────────────────────

INTENT_CLASSIFY_PROMPT = """Phân loại ý định của câu hỏi tài chính sau vào MỘT trong các nhãn:

- QA: Hỏi đáp thông thường về thông tin tài chính
- COMPARE: So sánh giữa 2+ doanh nghiệp hoặc tài liệu
- TREND: Phân tích xu hướng theo thời gian (nhiều năm)
- GLOSSARY: Hỏi về định nghĩa/ý nghĩa thuật ngữ tài chính
- SUMMARY: Yêu cầu tóm tắt hoặc báo cáo tổng quan

Câu hỏi: "{question}"

Chỉ trả về đúng một nhãn viết hoa, không giải thích thêm."""

VALID_INTENTS = {"QA", "COMPARE", "TREND", "GLOSSARY", "SUMMARY"}


def detect_intent(question: str) -> str:
    """Phát hiện ý định câu hỏi qua LLM."""
    prompt = INTENT_CLASSIFY_PROMPT.format(question=question)
    raw = call_llm(
        prompt=prompt,
        system_prompt="Bạn là bộ phân loại ý định câu hỏi tài chính.",
        temperature=0.0,
        max_tokens=10,
    ).strip().upper()

    # Fallback nếu LLM trả về không hợp lệ
    parts = raw.split()
    intent = parts[0] if parts else "QA"
    if intent not in VALID_INTENTS:
        logger.warning(f"[Router] Intent không nhận dạng được: '{raw}'. Fallback → QA")
        intent = "QA"

    logger.info(f"[Router] Intent: {intent} | Câu hỏi: '{question[:60]}'")
    return intent


# ─── Main Router ──────────────────────────────────────────────────────────────

def route_question(
    question: str,
    company_filter: str | None = None,
    intent_override: str | None = None,
    collection_names: list[str] | None = None,
) -> dict:
    """
    Điều phối câu hỏi đến module nghiệp vụ phù hợp.

    Args:
        question: Câu hỏi của người dùng.
        company_filter: Giới hạn trong một collection (từ sidebar).
        intent_override: Bỏ qua phát hiện ý định tự động.
        collection_names: Danh sách collection upload để tìm kiếm.

    Returns:
        Dict kết quả từ module tương ứng, bổ sung thêm trường 'intent'.
    """
    question = question.strip()
    if not question or len(question) > 8000:
        raise ValueError("Câu hỏi phải có từ 1 đến 8000 ký tự.")
    if intent_override is not None and intent_override not in VALID_INTENTS:
        raise ValueError("Chế độ phân tích không hợp lệ.")
    intent = intent_override or detect_intent(question)

    # Xác định các collection cần tìm kiếm
    if company_filter:
        targets = [company_filter]
    elif collection_names:
        targets = collection_names
    else:
        targets = get_available_collections()

    # ─── Dispatch ─────────────────────────────────────────────────────────────
    if intent == "GLOSSARY":
        result = explain_term(question, collection_names=targets)

    elif intent == "COMPARE":
        result = compare_companies(question, targets)

    elif intent == "TREND":
        company = targets[0] if targets else None
        result = analyze_trend(question, company) if company else {
            "analysis": "Chưa có tài liệu nào được nạp.",
            "company": None, "sources": [],
        }

    elif intent == "SUMMARY":
        company = company_filter or (targets[0] if targets else None)
        result = generate_summary(company) if company else {
            "summary": "Chưa có tài liệu nào được nạp.",
            "company": None, "focus": "tổng quan", "sources": [],
        }

    else:  # QA (default)
        company = company_filter if company_filter else None
        cols = None if company else targets
        result = answer_question(
            question,
            company=company,
            collection_names=cols,
        )

    result["intent"] = intent
    result["detected_companies"] = targets
    return result
