"""
financial_validator.py — Nhận diện PDF có phải báo cáo tài chính (BCTC) hay không.

Dùng heuristic dựa trên từ khoá tiếng Việt/Anh và mật độ số liệu,
không gọi LLM để giữ tốc độ upload.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Literal

from src.ingestion.pdf_loader import PageContent
from src.utils.config import get_financial_validation_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

Confidence = Literal["high", "medium", "low", "none"]

# Từ khoá mạnh — thường chỉ xuất hiện trong BCTC / báo cáo kiểm toán
_STRONG_TERMS: tuple[tuple[str, int], ...] = (
    (r"b[aá]o c[aá]o t[aà]i ch[ií]nh", 4),
    (r"b[aả]ng c[aâ]n \s*[\u0111d][\u1ed1o]i k[\u1ebf] to[aá]n", 4),
    (r"b[aá]o c[aá]o k[\u1ebf]t qu[aả] kinh doanh", 4),
    (r"b[aá]o c[aá]o l[uư]u chuy[\u1ec3]n ti[\u1ec1]n t[\u1ec7]", 4),
    (r"thuy[\u1ebf]t minh b[aá]o c[aá]o t[aà]i ch[ií]nh", 3),
    (r"financial statement", 3),
    (r"balance sheet", 3),
    (r"income statement", 3),
    (r"cash flow statement", 3),
    (r"[\u0111d][\u01a1]n v[\u1ecb] ki[\u1ec3]m to[aá]n", 3),
    (r"[\u00fd] ki[\u1ebf]n ki[\u1ec3]m to[aá]n", 3),
    (r"auditor'?s report", 2),
)

# Từ khoá trung bình — chỉ số / hạng mục BCTC
_MEDIUM_TERMS: tuple[tuple[str, int], ...] = (
    (r"t[\u1ed5]ng c[\u1ed9]ng t[aà]i s[\u1ea3]n|tong cong tai san", 2),
    (r"t[\u1ed5]ng c[\u1ed9]ng ngu[\u1ed3]n v[\u1ed1]n|tong cong nguon von", 2),
    (r"v[\u1ed1]n ch[\u1ee7] s[\u1edf] h[\u1eef]u|von chu so huu", 2),
    (r"n[\u1ee3] ph[\u1ea3]i tr[\u1ea3]|no phai tra", 2),
    (r"doanh thu thu[\u1ea7]n|doanh thu thuan", 2),
    (r"l[\u1ee3]i nhu[\u1ead]n sau thu[\u1ebf]|loi nhuan sau thue", 2),
    (r"l[\u1ee3]i nhu[\u1ead]n g[\u1ed9]p", 2),
    (r"ti[\u1ec1]n v[aà] t[\u01b0][\u01a1]ng [\u0111d][\u01b0][\u01a1]ng ti[\u1ec1]n", 2),
    (r"t[\u1ed3]n kho", 1),
    (r"chi ph[ií] t[\u00e0]i ch[ií]nh", 1),
    (r"chu[\u1ea9]n m[\u1ef1]c k[\u1ebf] to[aá]n", 2),
    (r"\bvas\b", 1),
    (r"\bifrs\b", 1),
    (r"k[\u1ef3] k[\u1ebf] to[aá]n", 1),
    (r"n[\u0103]m t[aà]i ch[ií]nh", 2),
    (r"eps\b", 1),
    (r"\broe\b", 1),
    (r"\broa\b", 1),
)

# Tín hiệu loại trừ — thường không phải BCTC
_NEGATIVE_TERMS: tuple[tuple[str, int], ...] = (
    (r"h[\u1ee3]p [\u0111d][\u1ed3]ng lao [\u0111d][\u1ed9]ng", 3),
    (r"curriculum vitae|\bcv\b", 2),
    (r"ti[\u1ec3]u thuy[\u1ec7]t|truy[\u1ec7]n ng[\u1eaf]n", 3),
    (r"th[\u1ef1]c [\u0111][\u01a1]n|menu\b", 2),
    (r"h[\u01b0][\u1edb]ng d[\u1eab]n s[\u1eed] d[\u1ee5]ng", 2),
    (r"terms of service|privacy policy", 2),
    (r"slide|powerpoint|b[\u00e0]i gi[\u1ea3]ng", 2),
)


@dataclass
class FinancialValidation:
    """Kết quả kiểm tra PDF có phải tài liệu tài chính."""

    is_financial: bool
    score: int
    confidence: Confidence
    matched_terms: list[str] = field(default_factory=list)
    negative_hits: list[str] = field(default_factory=list)
    numeric_density: float = 0.0
    message: str | None = None

    @property
    def is_borderline(self) -> bool:
        cfg = get_financial_validation_settings()
        threshold = int(cfg.get("low_confidence_threshold", 5))
        return self.is_financial and self.score < threshold


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_diacritics(text: str) -> str:
    """Chuẩn hoá không dấu — hỗ trợ text OCR."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _match_text(text: str) -> str:
    """Text gốc + bản không dấu để khớp từ khoá OCR."""
    base = _normalize(text)
    return f"{base} {_strip_diacritics(base)}"


def _collect_sample_text(pages: list[PageContent], max_chars: int) -> str:
    """Lấy mẫu text từ đầu, giữa và cuối PDF để tăng độ phủ."""
    if not pages:
        return ""

    if len(pages) <= 3:
        indices = list(range(len(pages)))
    else:
        mid = len(pages) // 2
        indices = [0, mid, len(pages) - 1]

    parts: list[str] = []
    total = 0
    per_page = max(max_chars // len(indices), 500)

    for idx in indices:
        snippet = pages[idx].text[:per_page]
        if total + len(snippet) > max_chars:
            snippet = snippet[: max_chars - total]
        parts.append(snippet)
        total += len(snippet)
        if total >= max_chars:
            break

    return "\n".join(parts)


def _term_hits(text: str, patterns: tuple[tuple[str, int], ...]) -> tuple[int, list[str]]:
    score = 0
    matched: list[str] = []
    for pattern, weight in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
            matched.append(pattern)
    return score, matched


def _numeric_density(text: str) -> float:
    """Tỷ lệ token số / tổng token — BCTC thường có mật độ số cao."""
    tokens = re.findall(r"\S+", text)
    if not tokens:
        return 0.0
    numeric = sum(
        1
        for t in tokens
        if re.search(r"\d", t) and re.search(r"[\d.,]+", t)
    )
    return numeric / len(tokens)


def validate_financial_document(pages: list[PageContent]) -> FinancialValidation:
    """
    Phân tích nội dung PDF đã trích xuất, xác định có phải BCTC không.

    Args:
        pages: Danh sách PageContent từ pdf_loader.

    Returns:
        FinancialValidation với điểm, confidence và thông báo.
    """
    cfg = get_financial_validation_settings()
    max_chars = int(cfg.get("sample_chars", 8000))
    min_score = int(cfg.get("min_score", 3))
    require_strong = bool(cfg.get("require_strong_indicator", True))
    min_numeric = float(cfg.get("min_numeric_density", 0.04))

    sample = _match_text(_collect_sample_text(pages, max_chars))
    if not sample:
        return FinancialValidation(
            is_financial=False,
            score=0,
            confidence="none",
            message="Không có nội dung text để xác minh loại tài liệu.",
        )

    strong_score, strong_hits = _term_hits(sample, _STRONG_TERMS)
    medium_score, medium_hits = _term_hits(sample, _MEDIUM_TERMS)
    neg_score, neg_hits = _term_hits(sample, _NEGATIVE_TERMS)

    total_score = strong_score + medium_score - neg_score
    numeric = _numeric_density(sample)

    matched_labels: list[str] = []
    for pattern in strong_hits + medium_hits:
        label = pattern.replace(r"\b", "").replace("[", "").replace("]", "")[:40]
        matched_labels.append(label)

    has_strong = strong_score > 0
    has_enough_score = total_score >= min_score
    has_numeric_signal = numeric >= min_numeric

    is_financial = has_enough_score and (has_strong or not require_strong)
    if is_financial and neg_score >= strong_score + medium_score:
        is_financial = False

    # BCTC scan đôi khi OCR yếu → nhiều số + vài từ khoá trung bình vẫn chấp nhận
    if not is_financial and medium_score >= 2 and numeric >= min_numeric * 2:
        is_financial = True
        total_score = max(total_score, min_score)

    if total_score >= 8 or (has_strong and total_score >= 5):
        confidence: Confidence = "high"
    elif total_score >= min_score:
        confidence = "medium"
    elif total_score > 0:
        confidence = "low"
    else:
        confidence = "none"

    message = _build_message(
        is_financial=is_financial,
        confidence=confidence,
        total_score=total_score,
        numeric=numeric,
        neg_hits=neg_hits,
    )

    logger.info(
        f"[FinancialValidator] score={total_score}, numeric={numeric:.2f}, "
        f"financial={is_financial}, confidence={confidence}"
    )

    return FinancialValidation(
        is_financial=is_financial,
        score=total_score,
        confidence=confidence,
        matched_terms=matched_labels[:8],
        negative_hits=neg_hits[:5],
        numeric_density=round(numeric, 3),
        message=message,
    )


def _build_message(
    *,
    is_financial: bool,
    confidence: Confidence,
    total_score: int,
    numeric: float,
    neg_hits: list[str],
) -> str | None:
    if is_financial:
        if confidence == "low" or total_score < int(
            get_financial_validation_settings().get("low_confidence_threshold", 5)
        ):
            return (
                "Tài liệu có dấu hiệu BCTC nhưng độ tin cậy thấp. "
                "Hãy kiểm tra lại nguồn và câu trả lời."
            )
        return None

    if neg_hits:
        return (
            "File này có vẻ không phải Báo cáo Tài chính "
            f"(phát hiện nội dung: {', '.join(neg_hits[:2])}). "
            "FinInsight AI chỉ hỗ trợ phân tích BCTC, báo cáo kiểm toán và tài liệu tài chính doanh nghiệp."
        )

    if numeric < 0.02:
        return (
            "File này không chứa đủ thuật ngữ hoặc số liệu tài chính điển hình. "
            "Vui lòng upload BCTC, báo cáo thường niên hoặc báo cáo kiểm toán."
        )

    return (
        "Không nhận diện được đây là Báo cáo Tài chính. "
        "FinInsight AI được thiết kế cho BCTC doanh nghiệp Việt Nam."
    )


def should_reject_upload(validation: FinancialValidation | None) -> tuple[bool, str | None]:
    """
    Quyết định có từ chối nạp file upload hay không.

    Returns:
        (rejected, rejection_reason)
    """
    if validation is None:
        return False, None
    cfg = get_financial_validation_settings()
    if not cfg.get("reject_on_fail", True):
        return False, validation.message
    if validation.is_financial:
        return False, None
    return True, validation.message
