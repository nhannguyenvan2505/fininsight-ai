"""Tests for follow-up question suggestions."""

from unittest.mock import patch

from src.modules.suggestion_module import (
    get_followup_suggestions,
    get_welcome_suggestions,
    parse_llm_suggestions,
)


class TestParseLlmSuggestions:
    def test_parse_bullet_quotes(self):
        raw = """
- "Tổng cộng nguồn vốn của FPT năm 2023 là bao nhiêu?"
- "Doanh thu thuần năm 2023 là bao nhiêu?"
- "Lợi nhuận sau thuế là bao nhiêu?"
"""
        result = parse_llm_suggestions(raw, limit=3)
        assert len(result) == 3
        assert "nguồn vốn" in result[0].lower()

    def test_parse_numbered_list(self):
        raw = """
1. Tổng cộng tài sản là bao nhiêu?
2. Vốn chủ sở hữu là bao nhiêu?
"""
        result = parse_llm_suggestions(raw, limit=2)
        assert len(result) == 2


class TestSuggestionModule:
    def test_welcome_suggestions_with_fpt_file(self):
        with patch("src.modules.suggestion_module.get_suggestion_settings") as mock_cfg:
            mock_cfg.return_value = {"use_llm": False, "fallback_to_templates": True, "count": 3}
            suggestions = get_welcome_suggestions(["bctc_fpt_2023.pdf"])
        assert len(suggestions) == 3
        assert any("FPT" in s for s in suggestions)
        assert any("nguồn vốn" in s.lower() for s in suggestions)

    def test_welcome_suggestions_generic(self):
        with patch("src.modules.suggestion_module.get_suggestion_settings") as mock_cfg:
            mock_cfg.return_value = {"use_llm": False, "fallback_to_templates": True, "count": 3}
            suggestions = get_welcome_suggestions(["report_xyz.pdf"])
        assert len(suggestions) == 3

    def test_followup_after_doanh_thu_question(self):
        with patch("src.modules.suggestion_module.get_suggestion_settings") as mock_cfg:
            mock_cfg.return_value = {"use_llm": False, "fallback_to_templates": True, "count": 3}
            suggestions = get_followup_suggestions(
                question="Doanh thu FPT năm 2023?",
                answer="Doanh thu thuần đạt 52.629 tỷ đồng.",
                doc_names=["bctc_fpt_2023.pdf"],
                intent="QA",
            )
        assert len(suggestions) <= 3
        assert any("lợi nhuận" in s.lower() for s in suggestions)

    def test_followup_nguon_von(self):
        with patch("src.modules.suggestion_module.get_suggestion_settings") as mock_cfg:
            mock_cfg.return_value = {"use_llm": False, "fallback_to_templates": True, "count": 3}
            suggestions = get_followup_suggestions(
                question="tổng tiền",
                answer="Không tìm thấy.",
                doc_names=["c13adf19.pdf"],
                intent="QA",
            )
        assert len(suggestions) >= 1

    @patch("src.modules.suggestion_module._generate_llm_suggestions")
    @patch("src.modules.suggestion_module.get_suggestion_settings")
    def test_smart_followup_when_llm_available(self, mock_cfg, mock_llm):
        mock_cfg.return_value = {"use_llm": True, "fallback_to_templates": True, "count": 3}
        mock_llm.return_value = [
            "Tổng cộng nguồn vốn năm 2023 là bao nhiêu?",
            "Vốn chủ sở hữu cuối kỳ là bao nhiêu?",
        ]
        suggestions = get_followup_suggestions(
            question="tổng tiền",
            answer="Không tìm thấy thông tin.",
            doc_names=["bctc_fpt.pdf"],
            collection_names=["upload_bctc_abc123"],
            intent="QA",
        )
        assert "nguồn vốn" in suggestions[0].lower()
        mock_llm.assert_called_once()

    @patch("src.modules.suggestion_module._generate_llm_suggestions")
    @patch("src.modules.suggestion_module.get_suggestion_settings")
    def test_smart_welcome_from_document(self, mock_cfg, mock_llm):
        mock_cfg.return_value = {"use_llm": True, "fallback_to_templates": True, "count": 3}
        mock_llm.return_value = [
            "Tổng cộng nguồn vốn của FPT năm 2023 là bao nhiêu?",
        ]
        suggestions = get_welcome_suggestions(
            ["bctc_fpt_2023.pdf"],
            collection_names=["upload_bctc_abc"],
        )
        assert "FPT" in suggestions[0] or "nguồn vốn" in suggestions[0].lower()
