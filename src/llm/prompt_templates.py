"""
prompt_templates.py — Tập hợp tất cả prompt template cho các module nghiệp vụ.

Mỗi template là một f-string hoặc hàm trả về string,
nhận context chunks và câu hỏi của người dùng.
"""

from __future__ import annotations


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_context(chunks: list[dict], max_chars: int = 4000) -> str:
    """Gộp các chunk thành đoạn context cho LLM."""
    parts = []
    total = 0
    for i, chunk in enumerate(chunks, 1):
        company = chunk.get("metadata", {}).get("company", chunk.get("company", "?"))
        file_name = chunk.get("metadata", {}).get("file_name", "")
        page = chunk.get("metadata", {}).get("page", "?")
        text = chunk.get("text", "")

        header = f"[Nguồn {i} | {company.upper()} | {file_name} | Trang {page}]"
        block = f"{header}\n{text}"

        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)

    return "\n\n---\n\n".join(parts)


# ─── Module 04 — Q&A ──────────────────────────────────────────────────────────

def qa_prompt(question: str, chunks: list[dict]) -> str:
    context = _format_context(chunks)
    return f"""Dựa vào các đoạn trích từ Báo cáo Tài chính dưới đây, hãy trả lời câu hỏi một cách chính xác, ngắn gọn và có dẫn nguồn.

=== THÔNG TIN THAM KHẢO ===
{context}

=== CÂU HỎI ===
{question}

=== YÊU CẦU ===
- Trả lời bằng tiếng Việt
- Dẫn nguồn cụ thể (tên công ty, trang) sau mỗi luận điểm
- Nếu không có thông tin trong tài liệu, hãy nói rõ "Không tìm thấy thông tin trong tài liệu hiện có."
- Nếu tài liệu không phải Báo cáo Tài chính hoặc không liên quan câu hỏi tài chính, hãy nói rõ và không suy diễn
- Không bịa số liệu

=== TRẢ LỜI ==="""


# ─── Module 05 — So sánh doanh nghiệp ────────────────────────────────────────

def comparison_prompt(question: str, chunks: list[dict], companies: list[str]) -> str:
    context = _format_context(chunks, max_chars=5000)
    company_list = ", ".join(c.upper() for c in companies)
    return f"""Bạn là chuyên gia phân tích tài chính. Hãy so sánh các doanh nghiệp ({company_list}) dựa trên thông tin sau:

=== DỮ LIỆU TÀI CHÍNH ===
{context}

=== YÊU CẦU SO SÁNH ===
{question}

=== HƯỚNG DẪN ===
- Trình bày dưới dạng bảng so sánh nếu có số liệu cụ thể
- Đưa ra nhận xét, đánh giá khách quan
- Dẫn nguồn rõ ràng
- Kết luận bằng đánh giá tổng quan

=== KẾT QUẢ SO SÁNH ==="""


# ─── Module 06 — Phân tích xu hướng ─────────────────────────────────────────

def trend_prompt(question: str, chunks: list[dict], company: str) -> str:
    context = _format_context(chunks)
    return f"""Phân tích xu hướng tài chính của {company.upper()} dựa trên dữ liệu nhiều năm sau:

=== DỮ LIỆU THEO NĂM ===
{context}

=== YÊU CẦU ===
{question}

=== HƯỚNG DẪN ===
- Xác định xu hướng tăng/giảm qua các năm
- Giải thích nguyên nhân có thể
- Dự báo ngắn hạn nếu có cơ sở
- Sử dụng số liệu cụ thể để minh chứng

=== PHÂN TÍCH XU HƯỚNG ==="""


# ─── Module 07 — Giải thích thuật ngữ ────────────────────────────────────────

GLOSSARY_SYSTEM = """Bạn là chuyên gia tài chính với kiến thức sâu về kế toán và phân tích báo cáo tài chính Việt Nam. 
Giải thích thuật ngữ một cách rõ ràng, chính xác, có ví dụ thực tế từ doanh nghiệp Việt Nam nếu có thể."""

def glossary_prompt(term: str, context_chunks: list[dict] | None = None) -> str:
    context_part = ""
    if context_chunks:
        ctx = _format_context(context_chunks, max_chars=1500)
        context_part = f"\n\n=== NGỮ CẢNH TỪ TÀI LIỆU ===\n{ctx}\n"

    return f"""Hãy giải thích thuật ngữ tài chính sau:{context_part}

=== THUẬT NGỮ ===
"{term}"

=== YÊU CẦU ===
1. Định nghĩa chính xác
2. Ý nghĩa trong phân tích tài chính
3. Công thức tính (nếu có)
4. Ví dụ minh hoạ
5. Lưu ý quan trọng khi đọc chỉ số này

=== GIẢI THÍCH ==="""


# ─── Module 08 — Tóm tắt báo cáo ────────────────────────────────────────────

def summary_prompt(company: str, chunks: list[dict], focus: str = "tổng quan") -> str:
    context = _format_context(chunks, max_chars=6000)
    return f"""Tạo báo cáo tóm tắt tình hình tài chính của {company.upper()} với trọng tâm: {focus}

=== DỮ LIỆU ===
{context}

=== CẤU TRÚC BÁO CÁO ===
1. **Tổng quan doanh nghiệp** — Ngành nghề, quy mô, vị thế thị trường
2. **Kết quả kinh doanh** — Doanh thu, lợi nhuận, tăng trưởng
3. **Sức khoẻ tài chính** — Thanh khoản, đòn bẩy, hiệu quả
4. **Điểm mạnh & Rủi ro** — Đánh giá SWOT nhanh
5. **Kết luận** — Đánh giá tổng quan và khuyến nghị

=== BÁO CÁO TÓM TẮT ==="""
