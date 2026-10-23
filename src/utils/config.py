"""
config.py — Tải cấu hình từ config.yaml và biến môi trường (.env)
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

# Tải biến môi trường từ file .env
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Đường dẫn gốc dự án
ROOT_DIR = Path(__file__).resolve().parents[2]


def load_config(config_path: str | None = None) -> dict:
    """Đọc file config.yaml và trả về dict cấu hình."""
    if config_path is None:
        config_path = ROOT_DIR / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError("Configuration must be a YAML mapping.")
    return cfg


# Singleton config
_config: dict | None = None


def get_config() -> dict:
    global _config
    if _config is None:
        _config = load_config()
    return _config


# ─── Shortcuts ────────────────────────────────────────────────────────────────

def get_chroma_settings() -> dict:
    return get_config().get("chroma", {})


def get_llm_settings() -> dict:
    settings = dict(get_config().get("llm", {}))
    if model := os.getenv("QWEN_MODEL", "").strip():
        settings["model"] = model
    return settings


def get_ingestion_settings() -> dict:
    return get_config().get("ingestion", {})


def get_ocr_settings() -> dict:
    """Cấu hình OCR (nested trong ingestion.ocr)."""
    ingestion = get_ingestion_settings()
    return ingestion.get("ocr", {})


def get_financial_validation_settings() -> dict:
    """Cấu hình nhận diện PDF tài chính (nested trong ingestion.financial_validation)."""
    ingestion = get_ingestion_settings()
    return ingestion.get("financial_validation", {})


def get_suggestion_settings() -> dict:
    """Cấu hình gợi ý câu hỏi (section suggestions trong config.yaml)."""
    return get_config().get("suggestions", {})


def get_upload_settings() -> dict:
    """Cấu hình upload nhanh / nền."""
    return get_ingestion_settings().get("upload", {})


def get_retrieval_settings() -> dict:
    return get_config().get("retrieval", {})


# ─── Biến môi trường ──────────────────────────────────────────────────────────

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
QWEN_API_KEY: str = os.getenv("QWEN_API_KEY", "")
QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

DATA_RAW_DIR: Path = ROOT_DIR / "data" / "raw_pdfs"
DATA_PROCESSED_DIR: Path = ROOT_DIR / "data" / "processed"
CHROMA_DB_DIR: Path = ROOT_DIR / "data" / "chroma_db"
