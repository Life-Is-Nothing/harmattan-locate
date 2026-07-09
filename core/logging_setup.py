from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.config import DATA_DIR, ensure_dirs


def setup_logging() -> logging.Logger:
    ensure_dirs()
    logger = logging.getLogger("hloc")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s", "%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    try:
        fh = RotatingFileHandler(Path(DATA_DIR) / "locate.log", maxBytes=1_500_000, backupCount=2)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    return logger


def get_logger(name: str = "hloc") -> logging.Logger:
    return logging.getLogger(name)
