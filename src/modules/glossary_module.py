"""
glossary_module.py — Module 07: Giải thích thuật ngữ tài chính.

Tra cứu thuật ngữ từ tài liệu và bổ sung kiến thức LLM nội tại.
"""

from __future__ import annotations

from src.llm.prompt_templates import GLOSSARY_SYSTEM, glossary_prompt
from src.llm.qwen_client import call_llm
from src.retrieval.hybrid_search import hybrid_search_multi_company
from src.storage.schema import get_available_collections
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Cache glossary để không phải gọi LLM nhiều lần với cùng thuật ngữ
_glossary_cache: dict[str, str] = {}


def explain_term(
    term: str,
    use_document_context: bool = True,
    top_k: int = 3,
    use_cache: bool = True,
    collection_names: list[str] | None = None,
) -> dict:
    """
    Giải thích một thuật ngữ tài chính.

    Args:
        term: Thuật ngữ cần giải thích.
        use_document_context: Có tìm ngữ cảnh từ tài liệu không.
        top_k: Số chunk tìm kiếm.
        use_cache: Có dùng cache hay không.

    Returns:
        Dict gồm: term, explanation, sources.
    """
    term_key = term.lower().strip()
    # Document-backed answers must not reuse a global term-only cache.
    use_cache = use_cache and not use_document_context

    if use_cache and term_key in _glossary_cache:
        logger.debug(f"[Glossary] Cache hit: '{term}'")
        return {"term": term, "explanation": _glossary_cache[term_key], "sources": []}

    logger.info(f"[Glossary] Giải thích thuật ngữ: '{term}'")

    # Tìm ngữ cảnh từ tài liệu
    context_chunks: list[dict] = []
    if use_document_context:
        collections = get_available_collections() if collection_names is None else collection_names
        if collections:
            context_chunks = hybrid_search_multi_company(
                query=term,
                companies=collections,
                top_k=top_k,
            )

    prompt = glossary_prompt(term, context_chunks if context_chunks else None)
    explanation = call_llm(
        prompt=prompt,
        system_prompt=GLOSSARY_SYSTEM,
        temperature=0.1,  # Cần chính xác cao
        max_tokens=1024,
    )

    if use_cache:
        _glossary_cache[term_key] = explanation

    sources = [
        {
            "company": c.get("company", c.get("metadata", {}).get("company", "")),
            "file_name": c.get("metadata", {}).get("file_name", ""),
            "page": c.get("metadata", {}).get("page", ""),
        }
        for c in context_chunks
    ]

    return {"term": term, "explanation": explanation, "sources": sources}


def batch_explain(terms: list[str]) -> list[dict]:
    """Giải thích nhiều thuật ngữ cùng lúc."""
    return [explain_term(t) for t in terms]
