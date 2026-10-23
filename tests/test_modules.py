"""
test_modules.py — Kiểm thử các Module nghiệp vụ 04–08
"""

import pytest
from unittest.mock import MagicMock, patch


class TestQAModule:
    """Test Module 04 — Q&A"""

    @patch("src.modules.qa_module.hybrid_search")
    @patch("src.modules.qa_module.call_llm")
    def test_answer_question_with_company(self, mock_llm, mock_search):
        mock_search.return_value = [
            {"id": "c1", "text": "Doanh thu FPT 2023 đạt 52.629 tỷ",
             "metadata": {"company": "fpt", "file_name": "bctc.pdf", "page": 5},
             "hybrid_score": 0.85, "company": "fpt"},
        ]
        mock_llm.return_value = "Doanh thu FPT năm 2023 đạt 52.629 tỷ đồng."

        from src.modules.qa_module import answer_question
        result = answer_question("Doanh thu FPT 2023?", company="fpt")

        assert "answer" in result
        assert len(result["answer"]) > 0
        assert "sources" in result
        assert result["company"] == "fpt"

    @patch("src.modules.qa_module.hybrid_search_multi_company")
    @patch("src.modules.qa_module.call_llm")
    def test_answer_question_no_company(self, mock_llm, mock_search):
        mock_search.return_value = []
        from src.modules.qa_module import answer_question
        with patch("src.modules.qa_module.get_available_collections", return_value=["fpt", "vinamilk"]):
            result = answer_question("Câu hỏi không tìm thấy")
        assert "Không tìm thấy" in result["answer"]

    @patch("src.modules.qa_module.hybrid_search")
    @patch("src.modules.qa_module.call_llm")
    def test_answer_returns_sources(self, mock_llm, mock_search):
        mock_search.return_value = [
            {"id": "c1", "text": "text", "metadata": {"company": "fpt", "file_name": "a.pdf", "page": 1},
             "hybrid_score": 0.9, "company": "fpt"},
            {"id": "c2", "text": "text2", "metadata": {"company": "fpt", "file_name": "a.pdf", "page": 2},
             "hybrid_score": 0.8, "company": "fpt"},
        ]
        mock_llm.return_value = "Trả lời."

        from src.modules.qa_module import answer_question
        result = answer_question("test?", company="fpt")
        assert len(result["sources"]) == 2


class TestComparisonModule:
    """Test Module 05 — So sánh"""

    @patch("src.modules.comparison_module.hybrid_search")
    @patch("src.modules.comparison_module.call_llm")
    def test_compare_companies(self, mock_llm, mock_search):
        mock_search.return_value = [
            {"id": "c1", "text": "ROE FPT 2023: 28%", "metadata": {"company": "fpt", "page": 1},
             "hybrid_score": 0.9},
        ]
        mock_llm.return_value = "FPT có ROE cao hơn Vinamilk năm 2023."

        from src.modules.comparison_module import compare_companies
        result = compare_companies("So sánh ROE", ["fpt", "vinamilk"])

        assert "comparison" in result
        assert result["companies"] == ["fpt", "vinamilk"]
        assert "sources" in result

    @patch("src.modules.comparison_module.hybrid_search")
    def test_compare_no_data(self, mock_search):
        mock_search.return_value = []
        from src.modules.comparison_module import compare_companies
        result = compare_companies("test", ["fpt", "vinamilk"])
        assert "Không tìm thấy" in result["comparison"]


class TestGlossaryModule:
    """Test Module 07 — Thuật ngữ"""

    @patch("src.modules.glossary_module.hybrid_search_multi_company")
    @patch("src.modules.glossary_module.call_llm")
    def test_explain_term(self, mock_llm, mock_search):
        mock_search.return_value = []
        mock_llm.return_value = "ROE là tỷ suất sinh lời trên vốn chủ sở hữu."
        import src.modules.glossary_module as glos
        glos._glossary_cache.clear()

        from src.modules.glossary_module import explain_term
        result = explain_term("ROE")

        assert result["term"] == "ROE"
        assert "explanation" in result
        assert len(result["explanation"]) > 0

    @patch("src.modules.glossary_module.hybrid_search_multi_company")
    @patch("src.modules.glossary_module.call_llm")
    def test_glossary_cache(self, mock_llm, mock_search):
        mock_search.return_value = []
        mock_llm.return_value = "EPS là lợi nhuận trên mỗi cổ phiếu."
        import src.modules.glossary_module as glos
        glos._glossary_cache.clear()

        from src.modules.glossary_module import explain_term
        explain_term("EPS", use_document_context=False)
        explain_term("EPS", use_document_context=False)  # Lần 2 dùng cache

        # LLM chỉ được gọi 1 lần
        assert mock_llm.call_count == 1


class TestSummaryModule:
    """Test Module 08 — Tóm tắt"""

    @patch("src.modules.summary_module.hybrid_search")
    @patch("src.modules.summary_module.call_llm")
    def test_generate_summary(self, mock_llm, mock_search):
        mock_search.return_value = [
            {"id": "c1", "text": "Vinamilk dẫn đầu thị trường sữa Việt Nam.",
             "metadata": {"company": "vinamilk", "file_name": "bctc.pdf", "page": 3},
             "hybrid_score": 0.88},
        ]
        mock_llm.return_value = "Vinamilk là doanh nghiệp sữa hàng đầu với tốc độ tăng trưởng ổn định."

        from src.modules.summary_module import generate_summary
        result = generate_summary("vinamilk", focus="tổng quan")

        assert "summary" in result
        assert result["company"] == "vinamilk"
        assert result["focus"] == "tổng quan"

    def test_summary_focuses_defined(self):
        from src.modules.summary_module import SUMMARY_FOCUSES
        assert len(SUMMARY_FOCUSES) >= 5
        assert "tổng quan" in SUMMARY_FOCUSES
