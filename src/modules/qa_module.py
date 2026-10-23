"""
qa_module.py — Module 04: Hỏi đáp thông minh dựa trên BCTC.

Pipeline: câu hỏi → hybrid search → LLM → trả lời có trích dẫn.
"""

from __future__ import annotations

from src.llm.prompt_templates import qa_prompt
from src.llm.qwen_client import call_llm
from src.retrieval.hybrid_search import hybrid_search, hybrid_search_multi_company
from src.storage.schema import get_available_collections
from src.utils.config import get_retrieval_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def answer_question(
    question: str,
    company: str | None = None,
    collection_names: list[str] | None = None,
    top_k: int | None = None,
    stream: bool = False,
) -> dict:
    """
    Trả lời câu hỏi về tài chính doanh nghiệp.

    Args:
        question: Câu hỏi của người dùng.
        company: Giới hạn tìm kiếm trong một collection cụ thể.
        collection_names: Danh sách collection cần tìm (tài liệu upload).
                          Nếu None → tìm toàn bộ collection hiện có.
        top_k: Số chunk context sử dụng.
        stream: Có stream kết quả không (cho Streamlit).

    Returns:
        Dict gồm: answer, sources, company.
    """
    cfg = get_retrieval_settings()
    top_k = top_k or cfg.get("qa_top_k", 5)

    # Xác định scope tìm kiếm
    if company:
        targets = [company]
    elif collection_names:
        targets = collection_names
    else:
        targets = get_available_collections()

    if not targets:
        return {
            "answer": "Chưa có tài liệu nào được nạp. Hãy upload file PDF trước.",
            "sources": [],
            "company": None,
        }

    # ─── Retrieval ────────────────────────────────────────────────────────────
    if len(targets) == 1:
        chunks = hybrid_search(question, targets[0], top_k=top_k)
        search_scope = targets[0]
    else:
        chunks = hybrid_search_multi_company(question, targets, top_k=top_k)
        search_scope = "multi"

    logger.info(f"[QA] Câu hỏi: '{question[:60]}' | scope={search_scope} | chunks={len(chunks)}")

    if not chunks:
        return {
            "answer": "Không tìm thấy thông tin liên quan trong tài liệu hiện có.",
            "sources": [],
            "company": company,
        }

    # Cảnh báo sớm nếu tài liệu có độ tin cậy BCTC thấp
    low_confidence_docs = {
        c.get("metadata", {}).get("file_name", "")
        for c in chunks
        if c.get("metadata", {}).get("financial_confidence") in ("low", "none")
    }
    low_confidence_docs.discard("")

    # ─── Generation ───────────────────────────────────────────────────────────
    prompt = qa_prompt(question, chunks)
    answer = call_llm(
        prompt=prompt,
        system_prompt="Bạn là chuyên gia phân tích tài chính doanh nghiệp Việt Nam. Trả lời chính xác, có dẫn chứng từ tài liệu.",
        stream=stream,
    )

    if low_confidence_docs:
        files = ", ".join(sorted(low_confidence_docs))
        answer += (
            f"\n\n⚠️ *Lưu ý: Tài liệu `{files}` có thể không phải BCTC chuẩn "
            "hoặc chất lượng OCR thấp — hãy đối chiếu nguồn gốc trước khi tin số liệu.*"
        )

    # Trích xuất nguồn từ chunks
    sources = [
        {
            "company": c.get("company", c.get("metadata", {}).get("company", "")),
            "file_name": c.get("metadata", {}).get("file_name", ""),
            "page": c.get("metadata", {}).get("page", ""),
            "score": round(c.get("hybrid_score", 0.0), 4),
        }
        for c in chunks
    ]

    return {
        "answer": answer,
        "sources": sources,
        "company": company or search_scope,
    }
