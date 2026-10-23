"""
suggestion_module.py — Gợi ý câu hỏi tiếp theo cho người dùng.

Chiến lược:
1. LLM + chunk thực tế từ tài liệu (gợi ý thông minh, theo nội dung PDF)
2. Fallback template nếu LLM / retrieval không khả dụng
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.llm.qwen_client import call_llm
from src.utils.config import get_suggestion_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Tên công ty thường gặp trong tên file / nội dung
_KNOWN_COMPANIES: dict[str, str] = {
    "fpt": "FPT",
    "vinamilk": "Vinamilk",
    "vietcombank": "Vietcombank",
    "vcb": "Vietcombank",
    "hoaphat": "Hoà Phát",
    "hòa phát": "Hoà Phát",
    "tgdd": "TGDD",
    "the gioi di dong": "TGDD",
    "th true milk": "TH True Milk",
}

_WELCOME_TEMPLATES: tuple[str, ...] = (
    "Tổng cộng nguồn vốn của {subject} là bao nhiêu?",
    "Doanh thu thuần của {subject} năm gần nhất là bao nhiêu?",
    "Lợi nhuận sau thuế của {subject} là bao nhiêu?",
)

_TOPIC_FOLLOWUPS: dict[str, tuple[str, ...]] = {
    "doanh thu": (
        "Lợi nhuận sau thuế của {subject} là bao nhiêu?",
        "Chi phí bán hàng và quản lý doanh nghiệp của {subject} là bao nhiêu?",
        "Tỷ suất lợi nhuận gộp của {subject} là bao nhiêu?",
    ),
    "lợi nhuận": (
        "Doanh thu thuần của {subject} là bao nhiêu?",
        "ROE (tỷ suất sinh lời vốn chủ sở hữu) của {subject} là bao nhiêu?",
        "EPS của {subject} là bao nhiêu?",
    ),
    "nguồn vốn": (
        "Tổng cộng tài sản của {subject} là bao nhiêu?",
        "Vốn chủ sở hữu của {subject} là bao nhiêu?",
        "Nợ phải trả của {subject} là bao nhiêu?",
    ),
    "tài sản": (
        "Tổng cộng nguồn vốn của {subject} là bao nhiêu?",
        "Tiền và tương đương tiền của {subject} là bao nhiêu?",
        "Tồn kho của {subject} là bao nhiêu?",
    ),
    "nợ": (
        "Tỷ lệ nợ trên vốn chủ sở hữu (D/E) của {subject} là bao nhiêu?",
        "Vốn chủ sở hữu của {subject} là bao nhiêu?",
        "Khả năng thanh toán hiện hành của {subject} thế nào?",
    ),
    "vốn": (
        "Tổng cộng nguồn vốn của {subject} là bao nhiêu?",
        "Lợi nhuận sau thuế của {subject} là bao nhiêu?",
        "Doanh thu thuần của {subject} là bao nhiêu?",
    ),
    "chi phí": (
        "Doanh thu thuần của {subject} là bao nhiêu?",
        "Lợi nhuận gộp của {subject} là bao nhiêu?",
        "Chi phí tài chính của {subject} là bao nhiêu?",
    ),
    "xu hướng": (
        "So sánh doanh thu {subject} qua các năm gần nhất?",
        "Xu hướng lợi nhuận sau thuế của {subject} thế nào?",
        "Tăng trưởng tài sản của {subject} qua các năm?",
    ),
    "so sánh": (
        "Doanh thu thuần của {subject} là bao nhiêu?",
        "Tỷ suất lợi nhuận của {subject} so với ngành thế nào?",
        "Tổng cộng nguồn vốn của {subject} là bao nhiêu?",
    ),
}

_DEFAULT_FOLLOWUPS: tuple[str, ...] = (
    "Tổng cộng nguồn vốn của {subject} là bao nhiêu?",
    "Doanh thu thuần của {subject} là bao nhiêu?",
    "Lợi nhuận sau thuế của {subject} là bao nhiêu?",
)

_WELCOME_SEARCH_QUERY = (
    "báo cáo tài chính doanh thu lợi nhuận tài sản nguồn vốn vốn chủ sở hữu"
)

_SUGGESTION_SYSTEM = """Bạn gợi ý câu hỏi phân tích Báo cáo Tài chính Việt Nam.
Quy tắc:
- Mỗi câu hỏi cụ thể, có thể trả lời từ tài liệu được cung cấp
- Tiếng Việt, ngắn gọn, có chỉ tiêu và năm/kỳ nếu thấy trong tài liệu
- Không lặp câu hỏi người dùng vừa hỏi
- Chỉ trả về danh sách câu hỏi, không giải thích
- Mỗi câu một dòng, bắt đầu bằng "- \"" và kết thúc bằng dấu hỏi trong ngoặc kép
Ví dụ:
- "Tổng cộng nguồn vốn của FPT năm 2023 là bao nhiêu?"
- "Doanh thu thuần năm 2023 là bao nhiêu?"
"""


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    return re.sub(r"\s+", " ", text).strip()


def _guess_company(*texts: str) -> str | None:
    combined = _normalize(" ".join(t for t in texts if t))
    for key, label in _KNOWN_COMPANIES.items():
        if key in combined:
            return label
    return None


def _subject_label(doc_names: list[str], answer: str = "", question: str = "") -> str:
    company = _guess_company(*doc_names, answer, question)
    if company:
        return company
    if doc_names:
        stem = Path(doc_names[0]).stem
        if not re.match(r"^[a-f0-9]{6,}$", stem) and len(stem) > 2:
            return stem.replace("_", " ").title()
    return "doanh nghiệp"


def _detect_topic(question: str, answer: str = "") -> str | None:
    text = _normalize(f"{question} {answer}")
    topics = sorted(_TOPIC_FOLLOWUPS.keys(), key=len, reverse=True)
    for topic in topics:
        if topic in text:
            return topic
    if "so sánh" in text or "compare" in text:
        return "so sánh"
    if "xu hướng" in text or "tăng trưởng" in text or " qua các năm" in text:
        return "xu hướng"
    return None


def _dedupe_similar(suggestions: list[str], question: str, limit: int = 3) -> list[str]:
    q_norm = _normalize(question) if question else ""
    seen: set[str] = set()
    result: list[str] = []
    for s in suggestions:
        s = s.strip().strip('"').strip("'")
        if not s or not s.endswith("?"):
            if s and not s.endswith("?"):
                s = s.rstrip(".") + "?"
            elif not s:
                continue
        s_norm = _normalize(s)
        if s_norm in seen or (q_norm and s_norm == q_norm):
            continue
        q_words = set(q_norm.split()) if q_norm else set()
        s_words = set(s_norm.split())
        if q_words and len(q_words & s_words) / max(len(s_words), 1) > 0.75:
            continue
        seen.add(s_norm)
        result.append(s)
        if len(result) >= limit:
            break
    return result


def parse_llm_suggestions(raw: str, limit: int = 3) -> list[str]:
    """Parse danh sách câu hỏi từ output LLM."""
    if not raw:
        return []

    lines = raw.strip().splitlines()
    parsed: list[str] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Bỏ bullet / numbering
        line = re.sub(r"^[\-\*•]\s*", "", line)
        line = re.sub(r"^\d+[\.\)]\s*", "", line)
        # Lấy nội dung trong ngoặc kép nếu có
        quoted = re.findall(r'"([^"]+\?)"', line)
        if quoted:
            parsed.extend(quoted)
            continue
        if "?" in line:
            # Cắt tại dấu hỏi cuối cùng của câu
            match = re.search(r"(.+?\?)", line)
            if match:
                parsed.append(match.group(1).strip().strip('"').strip("'"))

    return _dedupe_similar(parsed, question="", limit=limit)


def _fetch_context_snippets(
    query: str,
    collection_names: list[str],
    top_k: int,
    max_chars: int,
) -> str:
    """Lấy đoạn text từ ChromaDB làm ngữ cảnh gợi ý."""
    if not collection_names:
        return ""

    try:
        from src.retrieval.hybrid_search import hybrid_search, hybrid_search_multi_company

        if len(collection_names) == 1:
            chunks = hybrid_search(query, collection_names[0], top_k=top_k)
        else:
            chunks = hybrid_search_multi_company(query, collection_names, top_k=top_k)
    except Exception as exc:
        logger.warning(f"[Suggestions] Không lấy được context: {exc}")
        return ""

    parts: list[str] = []
    total = 0
    for chunk in chunks:
        meta = chunk.get("metadata", {})
        page = meta.get("page", "?")
        file_name = meta.get("file_name", "")
        text = chunk.get("text", "")[:900]
        if not text.strip():
            continue
        block = f"[{file_name} | Trang {page}]\n{text}"
        if total + len(block) > max_chars:
            remaining = max_chars - total
            if remaining > 100:
                parts.append(block[:remaining])
            break
        parts.append(block)
        total += len(block)

    return "\n\n---\n\n".join(parts)


def _generate_llm_suggestions(
    *,
    mode: str,
    doc_names: list[str],
    collection_names: list[str],
    question: str | None = None,
    answer: str | None = None,
    intent: str = "QA",
    limit: int = 3,
) -> list[str]:
    """Gọi LLM để sinh gợi ý dựa trên nội dung tài liệu."""
    cfg = get_suggestion_settings()
    top_k = int(cfg.get("context_top_k", 4))
    max_chars = int(cfg.get("max_context_chars", 2500))
    temperature = float(cfg.get("temperature", 0.4))
    max_tokens = int(cfg.get("max_tokens", 300))

    search_query = question or _WELCOME_SEARCH_QUERY
    context = _fetch_context_snippets(search_query, collection_names, top_k, max_chars)
    if len(context) < 80:
        logger.debug("[Suggestions] Context quá ngắn, bỏ qua LLM.")
        return []

    subject = _subject_label(doc_names, answer=answer or "", question=question or "")
    docs_line = ", ".join(doc_names) if doc_names else "tài liệu đã upload"

    if mode == "welcome":
        user_prompt = f"""Tài liệu: {docs_line}
Doanh nghiệp / chủ đề ước lượng: {subject}

=== NỘI DUNG TRÍCH TỪ BCTC ===
{context}

Dựa trên các chỉ tiêu và số liệu THỰC SỰ có trong tài liệu trên, gợi ý {limit} câu hỏi hay nhất để người dùng bắt đầu phân tích.
Ưu tiên câu hỏi về chỉ tiêu xuất hiện trong tài liệu (vd: tổng cộng nguồn vốn, doanh thu, lợi nhuận...)."""
    else:
        user_prompt = f"""Tài liệu: {docs_line}
Chủ đề: {subject}
Ý định: {intent}

Câu hỏi vừa hỏi: {question}
Câu trả lời vừa nhận: {(answer or '')[:700]}

=== NỘI DUNG TRÍCH TỪ BCTC (liên quan) ===
{context}

Gợi ý {limit} câu hỏi tiếp theo KHÁC câu vừa hỏi, dựa trên chỉ tiêu còn lại trong tài liệu.
Nếu câu trả lời báo không tìm thấy, gợi ý câu hỏi cụ thể hơn với đúng tên chỉ tiêu trong tài liệu."""

    try:
        raw = call_llm(
            prompt=user_prompt,
            system_prompt=_SUGGESTION_SYSTEM,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        suggestions = parse_llm_suggestions(raw, limit=limit)
        if question:
            suggestions = _dedupe_similar(suggestions, question, limit=limit)
        logger.info(f"[Suggestions] LLM sinh {len(suggestions)} gợi ý ({mode}).")
        return suggestions
    except Exception as exc:
        logger.warning(f"[Suggestions] LLM thất bại: {exc}")
        return []


def _template_welcome(doc_names: list[str], limit: int) -> list[str]:
    subject = _subject_label(doc_names)
    return [t.format(subject=subject) for t in _WELCOME_TEMPLATES][:limit]


def _template_followup(
    question: str,
    answer: str,
    doc_names: list[str],
    intent: str,
    limit: int,
) -> list[str]:
    subject = _subject_label(doc_names, answer=answer, question=question)
    if intent == "GLOSSARY":
        templates = (
            "Doanh thu thuần của {subject} là bao nhiêu?",
            "Giải thích ROE là gì?",
            "Tổng cộng nguồn vốn của {subject} là bao nhiêu?",
        )
    elif intent == "COMPARE":
        templates = _TOPIC_FOLLOWUPS.get("so sánh", _DEFAULT_FOLLOWUPS)
    elif intent == "TREND":
        templates = _TOPIC_FOLLOWUPS.get("xu hướng", _DEFAULT_FOLLOWUPS)
    else:
        topic = _detect_topic(question, answer)
        templates = _TOPIC_FOLLOWUPS.get(topic, _DEFAULT_FOLLOWUPS) if topic else _DEFAULT_FOLLOWUPS
    suggestions = [t.format(subject=subject) for t in templates]
    return _dedupe_similar(suggestions, question, limit=limit)


def get_welcome_suggestions(
    doc_names: list[str],
    collection_names: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Gợi ý ban đầu khi người dùng mới upload tài liệu.

    Thử LLM + context tài liệu trước, fallback template nếu cần.
    """
    cfg = get_suggestion_settings()
    limit = limit or int(cfg.get("count", 3))

    if cfg.get("use_llm", True) and collection_names:
        smart = _generate_llm_suggestions(
            mode="welcome",
            doc_names=doc_names,
            collection_names=collection_names,
            limit=limit,
        )
        if smart:
            return smart

    if cfg.get("fallback_to_templates", True):
        return _template_welcome(doc_names, limit)
    return []


def get_followup_suggestions(
    question: str,
    answer: str,
    doc_names: list[str],
    intent: str = "QA",
    collection_names: list[str] | None = None,
    limit: int | None = None,
) -> list[str]:
    """
    Gợi ý câu hỏi tiếp theo sau mỗi lượt hỏi đáp.

    Thử LLM + chunk liên quan trước, fallback template nếu cần.
    """
    cfg = get_suggestion_settings()
    limit = limit or int(cfg.get("count", 3))

    if cfg.get("use_llm", True) and collection_names:
        smart = _generate_llm_suggestions(
            mode="followup",
            doc_names=doc_names,
            collection_names=collection_names,
            question=question,
            answer=answer,
            intent=intent,
            limit=limit,
        )
        if smart:
            return smart

    if cfg.get("fallback_to_templates", True):
        return _template_followup(question, answer, doc_names, intent, limit)
    return []
