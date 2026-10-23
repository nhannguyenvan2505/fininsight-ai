"""Offline regression coverage for portfolio maintenance fixes."""
from unittest.mock import patch

import pytest


def test_comparison_requires_distinct_documents():
    from src.modules.comparison_module import compare_companies
    with patch("src.modules.comparison_module.hybrid_search") as search:
        result = compare_companies("Compare revenue", ["fpt", "fpt"])
    assert result["sources"] == []
    assert "hai" in result["comparison"]
    search.assert_not_called()


@pytest.mark.parametrize("question", ["   ", "x" * 8001])
def test_router_rejects_invalid_question_before_api_call(question):
    from src.orchestrator.chain_router import route_question
    with patch("src.orchestrator.chain_router.detect_intent") as detect:
        with pytest.raises(ValueError):
            route_question(question)
    detect.assert_not_called()


def test_router_keeps_single_collection_scope():
    from src.orchestrator.chain_router import route_question
    with patch("src.orchestrator.chain_router.get_available_collections", return_value=["only_doc"]), patch(
        "src.orchestrator.chain_router.answer_question", return_value={}
    ) as answer:
        route_question("Revenue?", intent_override="QA")
    assert answer.call_args.kwargs["collection_names"] == ["only_doc"]


def test_bm25_only_result_keeps_source():
    from src.retrieval.hybrid_search import hybrid_search
    metadata = {"file_name": "report.pdf", "page": 7}
    with patch("src.retrieval.hybrid_search.build_bm25_index"), patch(
        "src.retrieval.hybrid_search.bm25_search",
        return_value=[{"id": "one", "text": "Revenue", "metadata": metadata, "bm25_score": 1}],
    ), patch("src.retrieval.hybrid_search.semantic_search", return_value=[]):
        result = hybrid_search("Revenue", "fpt")
    assert result[0]["metadata"] == metadata


@pytest.mark.parametrize("content,name", [(b"", "a.pdf"), (b"hello", "a.pdf"), (b"%PDF-1.7", "a.txt")])
def test_invalid_upload_does_not_touch_database(content, name):
    from src.ingestion.upload_ingest import ingest_uploaded_pdf
    with patch("src.ingestion.upload_ingest.get_chroma_collection") as collection:
        with pytest.raises(ValueError):
            ingest_uploaded_pdf(content, name)
    collection.assert_not_called()


def test_upload_does_not_force_delete_and_preserves_source_name():
    from src.ingestion.upload_ingest import ingest_uploaded_pdf
    from src.ingestion.pdf_loader import PageContent
    from src.ingestion.pdf_stats import PDFLoadReport
    page = PageContent("test", "temporary.pdf", 1, "Revenue 123 " * 20,
                       {"company": "test", "file_name": "temporary.pdf", "page": 1})
    with patch("src.ingestion.upload_ingest.load_pdf", return_value=([page], PDFLoadReport())), patch(
        "src.ingestion.upload_ingest.embed_chunks", side_effect=lambda chunks, **kw: [(c, [0.1] * 3) for c in chunks]
    ), patch("src.ingestion.upload_ingest.get_chroma_collection") as collection:
        result = ingest_uploaded_pdf(b"%PDF-1.7 test", "annual.pdf", skip_financial_check=True)
    assert result.chunk_count > 0
    assert collection.call_args.kwargs["force_reingest"] is False
    assert collection.return_value.upsert.call_args.kwargs["metadatas"][0]["file_name"] == "annual.pdf"


def test_chunker_accepts_zero_overlap():
    from src.ingestion.chunker import chunk_pages
    with patch("src.ingestion.chunker._make_splitter") as splitter:
        chunk_pages([], chunk_size=32, chunk_overlap=0)
    splitter.assert_called_once_with(32, 0)
