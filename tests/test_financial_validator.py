"""
test_financial_validator.py — Kiểm thử nhận diện PDF tài chính.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.ingestion.financial_validator import validate_financial_document
from src.ingestion.pdf_loader import PageContent


def _page(text: str, page: int = 1) -> PageContent:
    return PageContent(
        company="test",
        source_file="test.pdf",
        page_number=page,
        text=text,
        metadata={"file_name": "test.pdf", "page": page},
    )


BCTC_SAMPLE = """
CÔNG TY CỔ PHẦN FPT
BÁO CÁO TÀI CHÍNH HỢP NHẤT
Cho năm tài chính kết thúc ngày 31/12/2023

BẢNG CÂN ĐỐI KẾ TOÁN
Tại ngày 31 tháng 12 năm 2023

TÀI SẢN
Tiền và tương đương tiền          12.345.678.000
Tồn kho                            5.432.100.000
TỔNG CỘNG TÀI SẢN                50.000.000.000

NGUỒN VỐN
Nợ phải trả                       20.000.000.000
Vốn chủ sở hữu                    30.000.000.000
TỔNG CỘNG NGUỒN VỐN               50.000.000.000

BÁO CÁO KẾT QUẢ KINH DOANH
Doanh thu thuần                   52.629.000.000
Lợi nhuận sau thuế                 8.500.000.000
"""

NON_FINANCIAL_SAMPLE = """
HƯỚNG DẪN SỬ DỤNG PHẦN MỀM

Chương 1: Giới thiệu
Đây là tài liệu hướng dẫn người dùng cài đặt và vận hành phần mềm.
Vui lòng đọc kỹ trước khi sử dụng.

Chương 2: Cài đặt
Bước 1: Tải file cài đặt
Bước 2: Chạy trình cài đặt
"""


class TestFinancialValidator:
    def test_accepts_bctc_document(self):
        result = validate_financial_document([_page(BCTC_SAMPLE)])
        assert result.is_financial is True
        assert result.score >= 3
        assert result.confidence in ("high", "medium")

    def test_rejects_non_financial_document(self):
        result = validate_financial_document([_page(NON_FINANCIAL_SAMPLE)])
        assert result.is_financial is False
        assert result.message is not None

    def test_rejects_empty_content(self):
        result = validate_financial_document([])
        assert result.is_financial is False
        assert result.confidence == "none"

    def test_ocr_like_bctc_with_numbers(self):
        """File scan: ít từ khoá mạnh nhưng nhiều số và hạng mục BCTC."""
        ocr_text = (
            "TONG CONG TAI SAN 50000000000\n"
            "TONG CONG NGUON VON 50000000000\n"
            "Doanh thu thuan 52629000000\n"
            "Loi nhuan sau thue 8500000000\n"
            "112233445566778899001122\n"
        ) * 3
        result = validate_financial_document([_page(ocr_text)])
        assert result.is_financial is True

    @patch("src.ingestion.financial_validator.get_financial_validation_settings")
    def test_should_reject_non_financial(self, mock_cfg):
        from src.ingestion.financial_validator import FinancialValidation, should_reject_upload

        mock_cfg.return_value = {"reject_on_fail": True}
        validation = FinancialValidation(
            is_financial=False,
            score=0,
            confidence="none",
            message="Không phải BCTC.",
        )
        rejected, reason = should_reject_upload(validation)
        assert rejected is True
        assert reason == "Không phải BCTC."

    def test_should_accept_financial(self):
        from src.ingestion.financial_validator import FinancialValidation, should_reject_upload

        validation = FinancialValidation(
            is_financial=True,
            score=10,
            confidence="high",
        )
        rejected, reason = should_reject_upload(validation)
        assert rejected is False
        assert reason is None
