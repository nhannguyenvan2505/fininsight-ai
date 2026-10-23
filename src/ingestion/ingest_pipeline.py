"""
ingest_pipeline.py — Module 01: Pipeline hoàn chỉnh nạp dữ liệu vào ChromaDB.

Luồng xử lý:
  raw_pdfs/ → PDFLoader → Chunker → Embedder → ChromaDB
"""

from __future__ import annotations

import json
from pathlib import Path

from src.ingestion.chunker import TextChunk, chunk_pages
from src.ingestion.embedder import embed_chunks
from src.ingestion.pdf_loader import PageContent, iter_all_companies, load_company_pdfs
from src.ingestion.pdf_stats import PDFLoadReport
from src.storage.chroma_client import get_chroma_collection
from src.utils.config import DATA_PROCESSED_DIR, DATA_RAW_DIR, get_ingestion_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _save_chunks_cache(company: str, chunks: list[TextChunk]) -> None:
    """Lưu cache chunk dưới dạng JSON để debug / tái sử dụng."""
    cache_dir = DATA_PROCESSED_DIR / company
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "chunks.json"
    data = [{"chunk_id": c.chunk_id, "text": c.text, "metadata": c.metadata} for c in chunks]
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.debug(f"[Pipeline] Cache chunk lưu tại {cache_file}")


def ingest_company(
    company: str,
    company_dir: Path | None = None,
    force_reingest: bool = False,
    pages: list[PageContent] | None = None,
    report: PDFLoadReport | None = None,
) -> int:
    """
    Pipeline nạp dữ liệu cho một công ty.

    Args:
        company: Tên công ty (ví dụ: "fpt", "vinamilk").
        company_dir: Thư mục chứa PDF. Mặc định = DATA_RAW_DIR / company.
        force_reingest: Nếu True, sẽ xoá collection cũ và nạp lại.
        pages: Danh sách trang đã load sẵn (tránh đọc/OCR lại PDF nếu caller
               đã gọi load_company_pdfs trước đó, ví dụ từ ingest_all()).
        report: Báo cáo đọc PDF tương ứng với `pages` (bắt buộc nếu truyền `pages`).

    Returns:
        Số chunk đã nạp vào ChromaDB.
    """
    if company_dir is None:
        company_dir = DATA_RAW_DIR / company

    logger.info(f"═══ Bắt đầu ingest: {company.upper()} ═══")

    # 1. Load PDF (bỏ qua nếu caller đã load sẵn — tránh OCR 2 lần)
    if pages is None:
        pages, report = load_company_pdfs(company_dir, company)
    assert report is not None
    if not pages:
        logger.warning(f"[Pipeline] Không có trang nào để xử lý cho '{company}'.")
        warning = report.build_warning(
            min_readable_ratio=get_ingestion_settings().get("min_readable_page_ratio", 0.5)
        )
        if warning:
            logger.warning(f"[Pipeline] {warning}")
        return 0

    warning = report.build_warning(
        min_readable_ratio=get_ingestion_settings().get("min_readable_page_ratio", 0.5)
    )
    if warning:
        logger.warning(f"[Pipeline] {warning}")

    # 2. Chunk
    chunks = chunk_pages(pages)
    _save_chunks_cache(company, chunks)

    # 3. Embed
    chunk_embeddings = embed_chunks(chunks)

    # 4. Upsert vào ChromaDB
    collection = get_chroma_collection(company, force_reingest=force_reingest)
    ids = [c.chunk_id for c, _ in chunk_embeddings]
    documents = [c.text for c, _ in chunk_embeddings]
    embeddings = [vec for _, vec in chunk_embeddings]
    metadatas = [c.metadata for c, _ in chunk_embeddings]

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )
    from src.retrieval.bm25_search import invalidate_bm25_index
    invalidate_bm25_index(company)

    logger.info(f"[Pipeline] Đã upsert {len(ids)} chunks vào collection '{company}'.")
    return len(ids)


def ingest_all(force_reingest: bool = False) -> dict[str, int]:
    """
    Chạy pipeline cho tất cả công ty trong DATA_RAW_DIR.

    Returns:
        Dict {company: số_chunk_đã_nạp}.
    """
    summary: dict[str, int] = {}
    for company, pages, report in iter_all_companies(DATA_RAW_DIR):
        count = ingest_company(
            company, force_reingest=force_reingest, pages=pages, report=report
        )
        summary[company] = count

    logger.info("═══ Hoàn tất ingest tất cả công ty ═══")
    for company, count in summary.items():
        logger.info(f"  {company:20s}: {count:6d} chunks")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="FinInsight AI — Ingestion Pipeline")
    parser.add_argument("--company", type=str, default=None, help="Tên công ty cụ thể")
    parser.add_argument("--force", action="store_true", help="Xoá và nạp lại từ đầu")
    args = parser.parse_args()

    if args.company:
        ingest_company(args.company, force_reingest=args.force)
    else:
        ingest_all(force_reingest=args.force)
