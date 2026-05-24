"""Logging utilities for MIMO DevFlow."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.logging import RichHandler

_console = Console(stderr=True)
_initialized = False


def setup_logging(
    level: str = "INFO",
    log_file: Optional[str] = None,
    rich_console: bool = True,
) -> None:
    """Configure logging for the entire MIMO DevFlow framework.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path to write logs to
        rich_console: Whether to use Rich formatted console output
    """
    global _initialized
    if _initialized:
        return

    root_logger = logging.getLogger("mimo_devflow")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    if rich_console:
        console_handler = RichHandler(
            console=_console,
            show_time=True,
            show_path=False,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
        )
        console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        root_logger.addHandler(console_handler)
    else:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        stream_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
        root_logger.addHandler(stream_handler)

    if log_file:
        file_path = Path(log_file)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(file_path))
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger within the MIMO DevFlow namespace.

    Args:
        name: Logger name (will be prefixed with 'mimo_devflow.')

    Returns:
        Configured logger instance
    """
    if not _initialized:
        setup_logging()

    full_name = f"mimo_devflow.{name}" if not name.startswith("mimo_devflow.") else name
    return logging.getLogger(full_name)
