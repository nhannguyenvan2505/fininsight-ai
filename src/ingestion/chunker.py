"""
chunker.py — Module 01: Chia văn bản thành các đoạn (chunk) phù hợp RAG.

Chiến lược:
- RecursiveCharacterTextSplitter của LangChain với overlap để duy trì ngữ cảnh.
- Mỗi chunk giữ nguyên metadata từ PageContent gốc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

from src.ingestion.pdf_loader import PageContent
from src.utils.config import get_ingestion_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TextChunk:
    """Một đoạn văn bản đã chia, kèm metadata đầy đủ."""
    chunk_id: str          # Định danh duy nhất: "{company}_{file}_{page}_{idx}"
    company: str
    text: str
    metadata: dict = field(default_factory=dict)


def _make_splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""],
        length_function=len,
        is_separator_regex=False,
    )


def chunk_pages(
    pages: list[PageContent],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[TextChunk]:
    """
    Chia danh sách PageContent thành các TextChunk.

    Args:
        pages: Danh sách trang đã trích xuất từ pdf_loader.
        chunk_size: Kích thước chunk (ký tự). Mặc định lấy từ config.
        chunk_overlap: Độ overlap giữa các chunk. Mặc định lấy từ config.

    Returns:
        Danh sách TextChunk.
    """
    cfg = get_ingestion_settings()
    chunk_size = chunk_size if chunk_size is not None else cfg.get("chunk_size", 512)
    chunk_overlap = chunk_overlap if chunk_overlap is not None else cfg.get("chunk_overlap", 64)
    if chunk_size <= 0 or not 0 <= chunk_overlap < chunk_size:
        raise ValueError("Require chunk_size > 0 and 0 <= chunk_overlap < chunk_size.")

    splitter = _make_splitter(chunk_size, chunk_overlap)
    chunks: list[TextChunk] = []

    for page in pages:
        if not page.text.strip():
            continue

        sub_texts = splitter.split_text(page.text)
        for idx, sub_text in enumerate(sub_texts):
            chunk_id = (
                f"{page.company}_{Path(page.source_file).stem}"
                f"_p{page.page_number:04d}_c{idx:03d}"
            )
            chunk_meta = {
                **page.metadata,
                "chunk_id": chunk_id,
                "chunk_index": idx,
                "chunk_total": len(sub_texts),
            }
            chunks.append(
                TextChunk(
                    chunk_id=chunk_id,
                    company=page.company,
                    text=sub_text.strip(),
                    metadata=chunk_meta,
                )
            )

    logger.info(
        f"[Chunker] {len(pages)} trang → {len(chunks)} chunks "
        f"(size={chunk_size}, overlap={chunk_overlap})"
    )
    return chunks


