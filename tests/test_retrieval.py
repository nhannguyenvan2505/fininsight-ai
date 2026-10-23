"""
test_retrieval.py — Kiểm thử Module 03: Hybrid Search
"""

import pytest
from unittest.mock import MagicMock, patch


class TestBM25Search:
    """Test cases cho bm25_search.py"""

    def test_tokenize_vietnamese(self):
        from src.retrieval.bm25_search import _tokenize
        text = "Doanh thu thuần năm 2023 đạt 52.629 tỷ đồng"
        tokens = _tokenize(text)
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        assert all(isinstance(t, str) for t in tokens)

    def test_tokenize_empty(self):
        from src.retrieval.bm25_search import _tokenize
        tokens = _tokenize("")
        assert isinstance(tokens, list)

    def test_bm25_search_no_index(self):
        """Tìm kiếm khi chưa có index không crash."""
        import src.retrieval.bm25_search as bm25_module
        bm25_module._bm25_cache.clear()

        with patch("src.retrieval.bm25_search.get_chroma_collection") as mock_col:
            mock_col.return_value.count.return_value = 0
            from src.retrieval.bm25_search import bm25_search
            result = bm25_search("test query", "fpt")
            assert result == []


class TestSemanticSearch:
    """Test cases cho semantic_search.py"""

    @patch("src.retrieval.semantic_search.embed_query")
    @patch("src.retrieval.semantic_search.get_chroma_collection")
    def test_semantic_search_returns_list(self, mock_col, mock_embed):
        mock_embed.return_value = [0.1] * 768
        mock_collection = MagicMock()
        mock_collection.count.return_value = 2
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["text1", "text2"]],
            "metadatas": [[{"company": "fpt", "page": 1}, {"company": "fpt", "page": 2}]],
            "distances": [[0.1, 0.3]],
        }
        mock_col.return_value = mock_collection

        from src.retrieval.semantic_search import semantic_search
        results = semantic_search("doanh thu", "fpt", top_k=2)

        assert len(results) == 2
        assert all("id" in r for r in results)
        assert all("text" in r for r in results)
        assert all("semantic_score" in r for r in results)
        # Cosine similarity: 1 - distance
        assert abs(results[0]["semantic_score"] - 0.9) < 0.01

    @patch("src.retrieval.semantic_search.embed_query")
    @patch("src.retrieval.semantic_search.get_chroma_collection")
    def test_empty_collection(self, mock_col, mock_embed):
        mock_embed.return_value = [0.1] * 768
        mock_collection = MagicMock()
        mock_collection.count.return_value = 0
        mock_collection.query.return_value = {
            "ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]
        }
        mock_col.return_value = mock_collection

        from src.retrieval.semantic_search import semantic_search
        results = semantic_search("test", "empty_company", top_k=5)
        assert results == []


class TestHybridSearch:
    """Test cases cho hybrid_search.py"""

    def test_rrf_score_decreases_with_rank(self):
        from src.retrieval.hybrid_search import _rrf_score
        scores = [_rrf_score(i) for i in range(5)]
        assert scores == sorted(scores, reverse=True)  # Giảm dần theo rank

    def test_rrf_score_positive(self):
        from src.retrieval.hybrid_search import _rrf_score
        assert _rrf_score(0) > 0
        assert _rrf_score(100) > 0

    @patch("src.retrieval.hybrid_search.bm25_search")
    @patch("src.retrieval.hybrid_search.semantic_search")
    @patch("src.retrieval.hybrid_search.build_bm25_index")
    def test_hybrid_fusion_combines_results(self, mock_build, mock_sem, mock_bm25):
        mock_bm25.return_value = [
            {"id": "doc1", "text": "text1", "bm25_score": 0.8},
            {"id": "doc2", "text": "text2", "bm25_score": 0.5},
        ]
        mock_sem.return_value = [
            {"id": "doc2", "text": "text2", "metadata": {}, "semantic_score": 0.9},
            {"id": "doc3", "text": "text3", "metadata": {}, "semantic_score": 0.7},
        ]

        from src.retrieval.hybrid_search import hybrid_search
        results = hybrid_search("doanh thu", "fpt", top_k=3)

        assert len(results) <= 3
        # doc2 xuất hiện trong cả BM25 và Semantic → điểm cao hơn
        doc2 = next((r for r in results if r["id"] == "doc2"), None)
        assert doc2 is not None
