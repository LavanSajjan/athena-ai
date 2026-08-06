"""
Logging configuration for Athena AI.
"""

import sys

from loguru import logger


def configure_logging() -> None:
    """Configure the application logger."""

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        colorize=True,
        backtrace=True,
        diagnose=True,
        enqueue=True,
    )

    logger.info("Logging initialized.")