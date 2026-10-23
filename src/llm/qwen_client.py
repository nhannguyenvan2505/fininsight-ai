"""
qwen_client.py — Kết nối LLM Qwen (hoặc OpenAI-compatible API).

Hỗ trợ:
- Qwen qua Alibaba DashScope (OpenAI-compatible endpoint)
- Fallback sang OpenAI nếu cấu hình tương ứng
"""

from __future__ import annotations

from openai import OpenAI

from src.utils.config import QWEN_API_KEY, QWEN_BASE_URL, get_llm_settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

# Singleton client
_llm_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
    """Trả về OpenAI-compatible client (singleton)."""
    global _llm_client
    if _llm_client is None:
        if not QWEN_API_KEY.strip():
            raise ValueError("Missing QWEN_API_KEY. Copy .env.example to .env and configure your provider.")
        _llm_client = OpenAI(
            api_key=QWEN_API_KEY,
            base_url=QWEN_BASE_URL,
            timeout=60.0,
            max_retries=2,
        )
        logger.info(f"[QwenClient] Kết nối LLM tại: {QWEN_BASE_URL}")
    return _llm_client


def call_llm(
    prompt: str,
    system_prompt: str = "Bạn là chuyên gia phân tích tài chính doanh nghiệp Việt Nam.",
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    stream: bool = False,
) -> str:
    """
    Gọi LLM với prompt và trả về kết quả dạng text.

    Args:
        prompt: Nội dung câu hỏi/yêu cầu của người dùng.
        system_prompt: Hướng dẫn hệ thống cho LLM.
        model: Tên model. Mặc định lấy từ config.
        temperature: Độ ngẫu nhiên (0.0–1.0).
        max_tokens: Giới hạn token đầu ra.
        stream: Có dùng streaming hay không.

    Returns:
        Chuỗi phản hồi từ LLM.
    """
    cfg = get_llm_settings()
    model = model or cfg.get("model", "qwen-plus")
    temperature = temperature if temperature is not None else cfg.get("temperature", 0.2)
    max_tokens = max_tokens or cfg.get("max_tokens", 2048)

    client = get_llm_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    logger.debug(f"[QwenClient] Gọi model='{model}', temp={temperature}, max_tokens={max_tokens}")

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream,
    )

    if stream:
        # Trả về generator cho Streamlit
        return response  # type: ignore

    content = response.choices[0].message.content or ""
    logger.debug(f"[QwenClient] Phản hồi ({len(content)} ký tự).")
    return content


def call_llm_with_history(
    messages: list[dict],
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """
    Gọi LLM với lịch sử hội thoại đầy đủ (multi-turn).

    Args:
        messages: Danh sách dict {"role": ..., "content": ...}.
        model, temperature, max_tokens: Tham số LLM.

    Returns:
        Chuỗi phản hồi.
    """
    cfg = get_llm_settings()
    model = model or cfg.get("model", "qwen-plus")
    temperature = temperature if temperature is not None else cfg.get("temperature", 0.2)
    max_tokens = max_tokens or cfg.get("max_tokens", 2048)

    client = get_llm_client()
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""
