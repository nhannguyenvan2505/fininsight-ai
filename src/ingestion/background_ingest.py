"""
background_ingest.py — Upload PDF chạy nền, UI phản hồi ngay (~2 giây).
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.ingestion.upload_ingest import IngestResult, ingest_uploaded_pdf
from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IngestJob:
    """Trạng thái một job upload."""

    job_id: str
    filename: str
    status: str = "running"  # running | done | error
    message: str = "Đang bắt đầu…"
    progress: float = 0.0
    result: IngestResult | None = None
    error: str | None = None


_jobs: dict[str, IngestJob] = {}
_lock = threading.Lock()


def start_background_ingest(file_bytes: bytes, filename: str) -> IngestJob:
    """
    Bắt đầu ingest trong thread nền.

    Returns:
        IngestJob — UI đọc trạng thái và gọi st.rerun() định kỳ.
    """
    job_id = uuid.uuid4().hex[:8]
    job = IngestJob(job_id=job_id, filename=filename)

    with _lock:
        _jobs[job_id] = job

    def _worker() -> None:
        try:
            result = ingest_uploaded_pdf(file_bytes, filename)
            job.result = result
            job.status = "done"
            job.message = "Hoàn tất!"
            job.progress = 1.0
            logger.info(f"[BackgroundIngest] Xong job {job_id}: {filename}")
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            job.message = f"Lỗi: {exc}"
            logger.error(f"[BackgroundIngest] Job {job_id} lỗi: {exc}")

    threading.Thread(target=_worker, daemon=True, name=f"ingest-{job_id}").start()
    return job


def get_job(job_id: str) -> IngestJob | None:
    with _lock:
        return _jobs.get(job_id)


def pop_job(job_id: str) -> IngestJob | None:
    with _lock:
        return _jobs.pop(job_id, None)


def list_active_jobs() -> list[IngestJob]:
    with _lock:
        return [j for j in _jobs.values() if j.status == "running"]
