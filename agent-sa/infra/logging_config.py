"""Runtime logging for ADA.

Operational logs go to stdout and a rotating file. Prompt bodies, generated
content, credentials, and authorization headers are deliberately excluded.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_ada_logging(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("ada")
    if getattr(logger, "_ada_configured", False):
        return logger

    level_name = os.getenv("ADA_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    logger.setLevel(level)
    logger.propagate = False

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / "ada.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError as exc:
        logger.warning("file_logging_unavailable error=%r", str(exc))

    logger._ada_configured = True
    return logger

