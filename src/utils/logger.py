"""
logger.py — Cấu hình logging tập trung cho toàn dự án.
"""

import logging
import sys
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

_FMT = "%(asctime)s | %(levelname)-8s | %(name)s — %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Trả về logger đã cấu hình với handler console + file.

    Args:
        name: Tên module (thường dùng __name__).
        level: Cấp độ logging (mặc định INFO).

    Returns:
        logging.Logger đã cấu hình sẵn.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Tránh thêm handler trùng lặp

    logger.setLevel(level)
    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (rotate hàng ngày nếu cần — dùng FileHandler đơn giản trước)
    log_file = LOG_DIR / "fininsight.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
