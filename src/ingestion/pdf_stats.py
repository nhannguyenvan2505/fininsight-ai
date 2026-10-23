"""
pdf_stats.py — Thống kê chất lượng đọc PDF (text layer vs OCR vs mixed).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PDFLoadReport:
    """Báo cáo số trang đọc được từ một hoặc nhiều file PDF."""

    total_pages: int = 0
    text_pages: int = 0              # Trang phân loại text thuần
    image_pages: int = 0             # Trang phân loại ảnh / scan
    mixed_pages: int = 0             # Trang phân loại vừa text vừa ảnh
    native_text_pages: int = 0       # Trang extract bằng text layer
    ocr_pages: int = 0               # Trang extract bằng OCR
    mixed_extract_pages: int = 0     # Trang extract gộp text + OCR
    skipped_pages: int = 0
    ocr_available: bool = True

    @property
    def readable_pages(self) -> int:
        return self.native_text_pages + self.ocr_pages + self.mixed_extract_pages

    def merge(self, other: PDFLoadReport) -> None:
        """Gộp thống kê từ file PDF khác."""
        self.total_pages += other.total_pages
        self.text_pages += other.text_pages
        self.image_pages += other.image_pages
        self.mixed_pages += other.mixed_pages
        self.native_text_pages += other.native_text_pages
        self.ocr_pages += other.ocr_pages
        self.mixed_extract_pages += other.mixed_extract_pages
        self.skipped_pages += other.skipped_pages
        self.ocr_available = self.ocr_available and other.ocr_available

    def build_warning(self, min_readable_ratio: float = 0.5) -> str | None:
        """
        Tạo cảnh báo nếu PDF có thể là file scan hoặc đọc không đủ trang.

        Args:
            min_readable_ratio: Tỷ lệ trang đọc được tối thiểu (0.0–1.0).

        Returns:
            Chuỗi cảnh báo hoặc None nếu không cần cảnh báo.
        """
        if self.total_pages == 0:
            return "Không mở được PDF hoặc file rỗng."

        if self.readable_pages == 0:
            msg = (
                f"Không đọc được trang nào từ PDF ({self.total_pages} trang). "
                "File có thể là scan chất lượng thấp hoặc được bảo vệ."
            )
            if not self.ocr_available and self.image_pages > 0:
                msg += (
                    " Cài OCR để đọc file scan: đóng Streamlit, chạy "
                    "`pip install easyocr`, rồi upload lại file."
                )
            return msg

        ratio = self.readable_pages / self.total_pages

        if self.image_pages > 0 and not self.ocr_available:
            return (
                f"PDF có {self.image_pages}/{self.total_pages} trang ảnh cần OCR, "
                "nhưng EasyOCR chưa sẵn sàng. Cài `easyocr` rồi upload lại."
            )

        if ratio < min_readable_ratio:
            return (
                f"PDF này chỉ đọc được {self.readable_pages}/{self.total_pages} trang "
                f"(ảnh={self.image_pages}, text={self.text_pages}, mixed={self.mixed_pages}). "
                "Kết quả phân tích có thể không đầy đủ."
            )

        if self.ocr_pages > 0 and self.native_text_pages == 0 and self.mixed_extract_pages == 0:
            return (
                f"PDF dạng ảnh: đã OCR {self.ocr_pages}/{self.image_pages} trang ảnh. "
                "Hãy kiểm tra lại câu trả lời vì OCR có thể sai số liệu."
            )

        if self.mixed_extract_pages > 0:
            return (
                f"PDF có {self.mixed_extract_pages} trang mixed (text + OCR). "
                "Hãy kiểm tra nguồn tham khảo khi xem số liệu."
            )

        return None

    def summary_line(self) -> str:
        """Một dòng tóm tắt cho log hoặc toast."""
        parts = [
            f"{self.readable_pages}/{self.total_pages} trang",
            f"ảnh={self.image_pages}",
            f"text={self.text_pages}",
        ]
        if self.mixed_pages:
            parts.append(f"mixed={self.mixed_pages}")
        if self.native_text_pages:
            parts.append(f"đọc_text={self.native_text_pages}")
        if self.ocr_pages:
            parts.append(f"ocr={self.ocr_pages}")
        if self.mixed_extract_pages:
            parts.append(f"gộp={self.mixed_extract_pages}")
        if self.skipped_pages:
            parts.append(f"bỏ_qua={self.skipped_pages}")
        return ", ".join(parts)
