"""
test_ingestion.py — Kiểm thử Module 01: Ingestion Pipeline
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


class TestPDFLoader:
    """Test cases cho pdf_loader.py"""

    def test_clean_text_removes_control_chars(self):
        from src.ingestion.pdf_loader import _clean_text
        raw = "Hello\x00World\x1fTest"
        result = _clean_text(raw)
        assert "\x00" not in result
        assert "\x1f" not in result
        assert "Hello" in result

    def test_clean_text_merges_blank_lines(self):
        from src.ingestion.pdf_loader import _clean_text
        raw = "Line 1\n\n\n\n\nLine 2"
        result = _clean_text(raw)
        assert "\n\n\n" not in result

    def test_load_pdf_missing_file(self, tmp_path):
        from src.ingestion.pdf_loader import load_pdf
        fake_path = tmp_path / "nonexistent.pdf"
        pages, report = load_pdf(fake_path, "test_company")
        assert pages == []
        assert report.total_pages == 0

    def test_load_company_pdfs_empty_dir(self, tmp_path):
        from src.ingestion.pdf_loader import load_company_pdfs
        pages, report = load_company_pdfs(tmp_path, "fpt")
        assert pages == []
        assert report.total_pages == 0


class TestChunker:
    """Test cases cho chunker.py"""

    def test_chunk_pages_basic(self):
        from src.ingestion.pdf_loader import PageContent
        from src.ingestion.chunker import chunk_pages

        pages = [
            PageContent(
                company="fpt",
                source_file="/data/fpt/bctc2023.pdf",
                page_number=1,
                text="Doanh thu thuần năm 2023 đạt 52.629 tỷ đồng, tăng 19,6% so với năm 2022. " * 20,
                metadata={"company": "fpt", "file_name": "bctc2023.pdf", "page": 1, "total_pages": 100},
            )
        ]
        chunks = chunk_pages(pages, chunk_size=256, chunk_overlap=32)
        assert len(chunks) > 0
        assert all(len(c.text) <= 512 for c in chunks)  # Không vượt quá kích thước tối đa

    def test_chunk_preserves_metadata(self):
        from src.ingestion.pdf_loader import PageContent
        from src.ingestion.chunker import chunk_pages

        pages = [
            PageContent(
                company="vinamilk",
                source_file="/data/vinamilk/bctc2023.pdf",
                page_number=5,
                text="Lợi nhuận sau thuế năm 2023 " * 30,
                metadata={"company": "vinamilk", "file_name": "bctc2023.pdf", "page": 5, "total_pages": 80},
            )
        ]
        chunks = chunk_pages(pages, chunk_size=128, chunk_overlap=16)
        assert all(c.company == "vinamilk" for c in chunks)
        assert all("chunk_id" in c.metadata for c in chunks)

    def test_chunk_empty_pages(self):
        from src.ingestion.chunker import chunk_pages
        result = chunk_pages([])
        assert result == []


class TestEmbedder:
    """Test cases cho embedder.py"""

    @patch("src.ingestion.embedder.SentenceTransformer")
    def test_embed_query_returns_list(self, mock_st):
        import numpy as np
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([[0.1, 0.2, 0.3]])
        mock_st.return_value = mock_model

        from src.ingestion.embedder import embed_query
        # Reset cache
        import src.ingestion.embedder as emb_module
        emb_module._model_cache.clear()

        vec = embed_query("Doanh thu FPT 2023", model_name="test-model")
        assert isinstance(vec, list)
        assert len(vec) == 3

    @patch("src.ingestion.embedder.SentenceTransformer")
    def test_embed_chunks_length_matches(self, mock_st):
        import numpy as np
        from src.ingestion.chunker import TextChunk
        from src.ingestion.embedder import embed_chunks

        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.rand(3, 768)
        mock_st.return_value = mock_model

        import src.ingestion.embedder as emb_module
        emb_module._model_cache.clear()

        chunks = [
            TextChunk("id1", "fpt", "Text 1", {}),
            TextChunk("id2", "fpt", "Text 2", {}),
            TextChunk("id3", "fpt", "Text 3", {}),
        ]
        results = embed_chunks(chunks, model_name="test-model", show_progress=False)
        assert len(results) == 3
        assert all(isinstance(vec, list) for _, vec in results)


class TestPDFLoadReport:
    """Test cases cho pdf_stats.py"""

    def test_warning_when_image_pages_need_ocr(self):
        from src.ingestion.pdf_stats import PDFLoadReport

        report = PDFLoadReport(
            total_pages=5,
            image_pages=5,
            text_pages=0,
            ocr_pages=0,
            ocr_available=False,
        )
        warning = report.build_warning()
        assert warning is not None
        assert "easyocr" in warning.lower() or "ocr" in warning.lower()

    def test_warning_low_ratio(self):
        from src.ingestion.pdf_stats import PDFLoadReport

        report = PDFLoadReport(
            total_pages=10,
            image_pages=8,
            text_pages=2,
            native_text_pages=2,
            ocr_pages=1,
        )
        warning = report.build_warning(min_readable_ratio=0.5)
        assert warning is not None
        assert "3/10" in warning

    def test_no_warning_when_most_pages_readable(self):
        from src.ingestion.pdf_stats import PDFLoadReport

        report = PDFLoadReport(
            total_pages=10,
            image_pages=2,
            text_pages=8,
            native_text_pages=8,
            ocr_pages=2,
        )
        assert report.build_warning(min_readable_ratio=0.5) is None


class TestPageClassification:
    """Phân loại trang ảnh vs text."""

    def test_classify_text_page(self):
        import fitz
        from src.ingestion.pdf_loader import classify_page

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Doanh thu thuần năm 2023 đạt 52.629 tỷ đồng")
        assert classify_page(page) == "text"
        doc.close()

    @patch("src.ingestion.pdf_loader.classify_page", return_value="image")
    @patch("src.ingestion.pdf_loader.ocr_pdf_page")
    @patch("src.ingestion.pdf_loader._ocr_enabled", return_value=True)
    def test_image_page_uses_ocr_not_hidden_text(
        self, _mock_enabled, mock_ocr, _mock_classify, tmp_path
    ):
        import fitz
        from src.ingestion.pdf_loader import load_pdf

        pdf_path = tmp_path / "signed_scan.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Digitally signed by TEST COMPANY")
        doc.save(str(pdf_path))
        doc.close()

        mock_ocr.return_value = "Tổng cộng nguồn vốn: 1.000 tỷ đồng"
        pages, report = load_pdf(pdf_path, "test_co")

        assert len(pages) == 1
        assert report.image_pages == 1
        assert report.native_text_pages == 0
        assert report.ocr_pages == 1
        assert "nguồn vốn" in pages[0].text.lower()
        assert pages[0].metadata["extract_method"] == "ocr"
        assert pages[0].metadata["page_mode"] == "image"
        mock_ocr.assert_called_once()


class TestMixedMode:
    """Chế độ mixed: gộp text layer + OCR."""

    def test_signature_junk_not_meaningful(self):
        from src.ingestion.pdf_loader import _is_meaningful_text, _is_signature_junk

        junk = (
            "Digitally signed by FPT CORPORATION\n"
            "Foxit Reader Version 10.0.0\n"
            "Reason: I am the author of this document"
        )
        assert _is_signature_junk(junk)
        assert not _is_meaningful_text(junk)

    def test_merge_text_sources_combines_both(self):
        from src.ingestion.pdf_loader import _merge_text_sources

        native = "Doanh thu thuần năm 2023"
        ocr = "Tổng cộng nguồn vốn: 1.000 tỷ đồng"
        merged = _merge_text_sources(native, ocr)
        assert native in merged
        assert ocr in merged

    def test_merge_text_sources_deduplicates(self):
        from src.ingestion.pdf_loader import _merge_text_sources

        text = "Doanh thu thuần năm 2023 đạt 52.629 tỷ đồng"
        assert _merge_text_sources(text, text) == text

    @patch("src.ingestion.pdf_loader._image_coverage", return_value=0.6)
    def test_classify_mixed_when_image_and_meaningful_text(self, _mock_cov):
        import fitz
        from src.ingestion.pdf_loader import classify_page

        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Doanh thu thuần năm 2023 đạt 52.629 tỷ đồng, tăng 19,6% so với năm 2022.",
        )
        assert classify_page(page) == "mixed"
        doc.close()

    @patch("src.ingestion.pdf_loader.classify_page", return_value="mixed")
    @patch("src.ingestion.pdf_loader.ocr_pdf_page")
    @patch("src.ingestion.pdf_loader._ocr_enabled", return_value=True)
    def test_mixed_page_merges_native_and_ocr(
        self, _mock_enabled, mock_ocr, _mock_classify, tmp_path
    ):
        import fitz
        from src.ingestion.pdf_loader import load_pdf

        pdf_path = tmp_path / "mixed_page.pdf"
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text(
            (72, 72),
            "Doanh thu thuần năm 2023 đạt 52.629 tỷ đồng, tăng 19,6% so với năm 2022.",
        )
        doc.save(str(pdf_path))
        doc.close()

        mock_ocr.return_value = "Tổng cộng nguồn vốn: 1.000 tỷ đồng"
        pages, report = load_pdf(pdf_path, "test_co")

        assert len(pages) == 1
        assert report.mixed_pages == 1
        assert report.mixed_extract_pages == 1
        assert "doanh thu" in pages[0].text.lower()
        assert "nguồn vốn" in pages[0].text.lower()
        assert pages[0].metadata["extract_method"] == "mixed"
        assert pages[0].metadata["page_mode"] == "mixed"

    def test_mixed_extract_warning(self):
        from src.ingestion.pdf_stats import PDFLoadReport

        report = PDFLoadReport(
            total_pages=5,
            mixed_pages=2,
            mixed_extract_pages=2,
            native_text_pages=3,
        )
        warning = report.build_warning(min_readable_ratio=0.5)
        assert warning is not None
        assert "mixed" in warning.lower()
