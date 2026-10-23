# FinInsight AI

A Vietnamese financial-report learning application using retrieval-augmented generation (RAG). A personal portfolio project by Nguyễn Văn Nhân.

## Author

**Nguyễn Văn Nhân** develops this application as a personal internship portfolio project.

- GitHub: [nhannguyenvan2505](https://github.com/nhannguyenvan2505)
- Email: [nhann0515@gmail.com](mailto:nhann0515@gmail.com)

The project combines local PDF processing and retrieval with an OpenAI-compatible language model. Recent maintenance focuses on reliable ingestion, source citations, and regression testing.

## Features and architecture

PDF upload → PyMuPDF text extraction / OCR fallback → overlapping character chunks → local multilingual sentence embeddings → persistent ChromaDB → BM25 + semantic retrieval with reciprocal rank fusion → OpenAI-compatible LLM → Streamlit answers and source pages.

Implemented code paths include document Q&A, document comparison, trend analysis, terminology explanations, focused summaries, and suggested questions. These generate text from retrieved evidence; they are not a structured accounting engine or verified financial calculations. Comparison requires two distinct documents. Trend analysis needs suitable multi-year evidence. OCR quality warnings and keyword-based financial-document checks are available; the default warns rather than rejects nonfinancial content.

The active interface is `ui/app.py` with a sidebar and chat. Other dashboard components exist but are not the active entry point. No external SQL database, authentication, or hosted backend is required. ChromaDB is embedded on disk. The company directory names are ingestion examples, not preloaded coverage of five companies.

## Requirements

The reviewed environment uses Windows and Python 3.11.9. Python 3.11 is recommended. Embeddings and OCR run locally and may download model weights on first use. Generation requires an API credential, internet access, and a model supported by your chosen endpoint; provider charges may apply.

`requirements.txt` contains the project dependency constraints. `requirements-lock.txt` records the installed review environment to aid reproduction. It has not been validated by a clean installation or on other operating systems. Dependencies were not upgraded indiscriminately.

## Setup from scratch

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
Copy-Item .env.example .env
```

Set `QWEN_API_KEY` and `QWEN_BASE_URL` in `.env`. Set `QWEN_MODEL` to a model offered by that same provider; it overrides `llm.model` in `config.yaml`. For Groq, use `https://api.groq.com/openai/v1` with a model available in your Groq account. The example endpoint and default model target DashScope. The legacy variable names also work with other OpenAI-compatible providers. An `OPENAI_API_KEY` fallback is not implemented.

On Linux/macOS use `python3 -m venv .venv`, `.venv/bin/python` and `cp .env.example .env` instead.

```powershell
.\.venv\Scripts\python.exe -m streamlit run ui/app.py
```

Open the local URL shown by Streamlit. Upload a PDF (maximum 20 MiB by default), click **Thêm tệp**, select documents, and ask a question. The initial empty interface does not download the models. Uploading the first document may take time. Do not upload confidential reports: retrieved text and questions are sent to the configured LLM provider.

### Optional batch ingestion and database

Place reports you are authorized to use under `data/raw_pdfs/<company>/`:

```powershell
.\.venv\Scripts\python.exe -m src.ingestion.ingest_pipeline --company fpt
```

ChromaDB is created at `data/chroma_db/`. Chunk debug output and OCR caches go under `data/processed/`; logs go under `logs/`. No database server or migration is required. The current UI tracks uploaded documents in session state; batch-ingested collections are not automatically listed in the sidebar. `--force` deliberately replaces the target collection: back up your local database before choosing to use it. Do not change embedding models against an existing collection without planning reindexing.

## Testing

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall -q src ui tests
```

Most tests mock generation, retrieval, or embeddings. Passing them does not prove answer accuracy or external API availability. The latest local verification passed 62 tests. A live backend smoke test using a synthetic one-page PDF also passed; this does not validate all report types or UI interactions. There is no configured dedicated lint tool or frontend build step.

Optional publication scan: `python scripts/check_publication.py` (prints paths only, not secrets).

Optional live backend smoke test: `python scripts/smoke_rag.py`. This uses a generated one-page PDF and an in-memory database, downloads embedding weights if needed, and makes one potentially billable request to your configured LLM provider. It does not send your reports or modify the persistent database. The recorded smoke test returned the expected revenue with a citation to page 1.

## My Contributions

Recent maintenance was completed with AI-assisted code review and implementation. The following list describes the changes made during that review.

Recent maintenance changes include:

- PDF signature/size checks, stronger content identifiers, original filenames in citations, and respecting the upload replacement flag.
- Preserving BM25-only source metadata and invalidating BM25 caches after ingestion/deletion.
- Rejecting comparisons with fewer than two distinct documents; validating router input and keeping query scope explicit.
- Limiting document-context glossary retrieval to selected collections and preventing term-only cache reuse for document-backed explanations.
- Supporting explicit zero chunk overlap and validating chunk parameters.
- Deferring embedding/OCR downloads until needed; adding an actionable missing-key error and bounded LLM request timeouts/retries.
- An environment template, expanded ignore rules, installed dependency snapshot, regression tests, and accurate setup/provenance documentation.

The source snapshot includes these maintenance changes.

## Known Limitations

- This is a local, single-user learning application. Collections and caches are shared in one process/database; there is no tenant isolation or authorization. Do not expose it as a public upload service.
- Local documents persist after the browser session, while the UI document list is session-based. A document registry and safe restore workflow remain future work.
- LLM responses, OCR numbers, citations, cross-company comparisons, and year coverage require human review. Prompts do not guarantee resistance to instructions embedded in documents.
- No structured ratio computation, financial data API, live stock data, benchmark, or production accuracy claim is provided.
- Upload size is bounded, but there is no comprehensive page-count, OCR-time, or concurrency budget. Parser validation still handles malformed PDFs after the initial signature check.
- Explicit force replacement is not transactional. Large ingestion batches are not split according to ChromaDB's runtime batch limit.
- Dependency minimum versions remain broad in `requirements.txt`; use the review snapshot as a starting point, not a supply-chain security certification.
- A synthetic one-page PDF has passed backend ingestion, real embeddings, retrieval, and live LLM generation. This does not validate OCR, multi-page report accuracy, all UI interactions, or a clean installation.

## Project status and third-party rights

Developed by Nguyễn Văn Nhân.

No LICENSE or NOTICE is currently included. A redistribution license has not been selected automatically. Third-party dependencies and assets retain their own terms.

This public source snapshot excludes the local sample financial PDF, its extracted text, and an unverified logo. Supply your own authorized PDFs; no sample report or database is bundled. Optional legacy navbar/footer components tolerate the missing logo. Runtime dependencies and downloaded model weights have their own licenses and terms, separate from this repository.
