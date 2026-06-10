"""
Application-wide logging setup.
Captures unhandled exceptions and writes to a rotating log file.
"""

from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler


def setup_logging(
    log_path: str | None = None, level: int = logging.INFO
) -> logging.Logger:
    """Configure root logger with a rotating file and console handler."""

    if log_path is None:
        base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), os.pardir)
        )
        log_path = os.path.join(base_dir, "app_errors.log")

    logger = logging.getLogger()
    if logger.handlers:
        return logger

    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info("Logging initialized")
    return logger


def install_excepthook(logger: logging.Logger | None = None) -> None:
    """Capture unhandled exceptions and log them."""
    if logger is None:
        logger = logging.getLogger()

    def _excepthook(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_traceback),
        )

    sys.excepthook = _excepthook
