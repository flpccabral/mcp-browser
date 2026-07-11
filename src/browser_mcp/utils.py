"""Utility functions for browser-mcp-server."""

import logging
import re
import sys


def _get_logger() -> logging.Logger:
    """Configure and return a logger that writes to stderr."""
    logger = logging.getLogger("browser_mcp")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


logger = _get_logger()


def sanitize_filename(name: str) -> str:
    """Sanitize a string to be safe for use as a filename.

    Removes or replaces characters that are invalid in filenames.
    """
    sanitized = re.sub(r'[\\/:*?"<>|]', "_", name)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized.strip("._")
    return sanitized or "untitled"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to a maximum length, appending a suffix if truncated.

    Args:
        text: The text to truncate.
        max_length: Maximum allowed length (including suffix).
        suffix: String to append when truncation occurs.

    Returns:
        Truncated text if it exceeds max_length, otherwise the original text.
    """
    if len(text) <= max_length:
        return text
    if max_length <= len(suffix):
        return suffix[:max_length]
    return text[: max_length - len(suffix)] + suffix


class BrowserError(Exception):
    """Base exception for browser-related errors."""

    pass
