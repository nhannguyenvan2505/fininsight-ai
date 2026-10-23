"""Opt-in real-model smoke test using a synthetic PDF and an in-memory DB.

Run: python scripts/smoke_rag.py
Downloads embedding weights if absent and makes one billable provider request.
Never uses the user's PDFs or persistent Chroma database.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import chromadb
    import fitz
    from src.utils.config import get_config
    import src.storage.chroma_client as storage
    from src.ingestion.upload_ingest import ingest_uploaded_pdf
    from src.modules.qa_module import answer_question

    # Explicit isolation: real storage implementation, no persistent user data.
    storage._client = chromadb.EphemeralClient()
    get_config()["ingestion"]["ocr"]["enabled"] = False
    get_config()["ingestion"]["ocr"]["cache_enabled"] = False
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), (
        "SYNTHETIC TEST DATA - NOT A REAL COMPANY\n"
        "Example Company financial report 2023\n"
        "Revenue in 2023 was 123 million VND.\n"
        "Net profit in 2023 was 17 million VND.\n"
    ))
    payload = doc.tobytes()
    doc.close()
    result = ingest_uploaded_pdf(payload, "synthetic-report.pdf", skip_financial_check=True)
    assert result.chunk_count > 0, "No chunks ingested"
    response = answer_question("What was Example Company's revenue in 2023?", company=result.collection_name)
    assert response["sources"], "No source citations"
    assert all(s["file_name"] == "synthetic-report.pdf" and s["page"] == 1 for s in response["sources"])
    assert "123" in response["answer"], "Expected revenue missing from answer"
    print(json.dumps({"status": "passed", "chunks": result.chunk_count,
                      "sources": response["sources"], "answer": response["answer"]}, ensure_ascii=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Provider messages may contain request details: print only safe metadata.
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__,
                          "http_status": getattr(exc, "status_code", None)}))
        raise SystemExit(1)
