"""
embedder.py — Module 01: Tạo vector embedding cho các TextChunk.

Model embedding:
- Mặc định: sentence-transformers/paraphrase-multilingual-mpnet-base-v2
  (hỗ trợ tiếng Việt tốt, chạy local, miễn phí)
- Có thể đổi sang bất kỳ model HuggingFace nào qua config.yaml
"""

from __future__ import annotations

import numpy as np
from sentence_transformers import SentenceTransformer

from src.ingestion.chunker import TextChunk
from src.utils.config import get_ingestion_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache model để không load lại mỗi lần gọi
_model_cache: dict[str, SentenceTransformer] = {}


def _get_model(model_name: str) -> SentenceTransformer:
    if model_name not in _model_cache:
        logger.info(f"[Embedder] Đang tải model: {model_name}")
        _model_cache[model_name] = SentenceTransformer(model_name)
        logger.info(f"[Embedder] Model '{model_name}' đã sẵn sàng.")
    return _model_cache[model_name]


def embed_chunks(
    chunks: list[TextChunk],
    model_name: str | None = None,
    batch_size: int = 32,
    show_progress: bool = True,
) -> list[tuple[TextChunk, list[float]]]:
    """
    Tạo embedding vector cho danh sách TextChunk.

    Args:
        chunks: Danh sách TextChunk cần embed.
        model_name: Tên model SentenceTransformer. Mặc định lấy từ config.
        batch_size: Số chunk xử lý mỗi batch.
        show_progress: Hiển thị progress bar.

    Returns:
        Danh sách tuple (chunk, embedding_vector).
    """
    if not chunks:
        return []

    cfg = get_ingestion_settings()
    model_name = model_name or cfg.get(
        "embedding_model",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    )
    batch_size = int(cfg.get("embed_batch_size", batch_size))

    model = _get_model(model_name)
    texts = [c.text for c in chunks]

    logger.info(f"[Embedder] Embedding {len(chunks)} chunks với batch_size={batch_size}…")
    vectors: np.ndarray = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        normalize_embeddings=True,  # cosine similarity ≈ dot product
        convert_to_numpy=True,
    )

    results = [(chunk, vec.tolist()) for chunk, vec in zip(chunks, vectors)]
    logger.info(f"[Embedder] Hoàn tất. Dim={vectors.shape[1]}")
    return results


def embed_query(
    query: str,
    model_name: str | None = None,
) -> list[float]:
    """
    Tạo embedding cho một câu truy vấn đơn lẻ.

    Args:
        query: Câu hỏi / câu truy vấn.
        model_name: Model SentenceTransformer.

    Returns:
        Vector embedding dưới dạng list[float].
    """
    cfg = get_ingestion_settings()
    model_name = model_name or cfg.get(
        "embedding_model",
        "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    )
    model = _get_model(model_name)
    vec: np.ndarray = model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vec[0].tolist()
