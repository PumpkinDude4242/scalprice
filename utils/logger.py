"""
Logging Configuration Module

Provides consistent logging across all scrapers with:
- Console output for real-time monitoring
- File output for post-run analysis
- Colored output for better readability
- Per-scraper logging namespaces
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from config.settings import settings


class ColoredFormatter(logging.Formatter):
    """
    Custom formatter adding colors to log levels.

    Makes console output easier to scan:
    - DEBUG: Grey
    - INFO: Green
    - WARNING: Yellow
    - ERROR: Red
    - CRITICAL: Bold Red
    """

    COLORS = {
        'DEBUG': '\033[90m',      # Grey
        'INFO': '\033[92m',       # Green
        'WARNING': '\033[93m',    # Yellow
        'ERROR': '\033[91m',      # Red
        'CRITICAL': '\033[1;91m', # Bold Red
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        # Add color based on level
        color = self.COLORS.get(record.levelname, self.RESET)

        # Format the message
        message = super().format(record)

        # Apply color to level name
        colored_level = f"{color}{record.levelname}{self.RESET}"
        message = message.replace(record.levelname, colored_level)

        return message


def setup_logger(
    name: str = "scraper",
    log_file: Optional[str] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Setup and configure a logger instance.

    Args:
        name: Logger name (use scraper name for namespacing)
        log_file: Optional log file path
        level: Log level (DEBUG, INFO, WARNING, ERROR)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # Set level from argument or settings
    log_level = getattr(logging, level or settings.LOG_LEVEL)
    logger.setLevel(log_level)

    # === Console Handler ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Use colored formatter for console
    console_format = ColoredFormatter(
        fmt="%(asctime)s │ %(name)-15s │ %(levelname)-8s │ %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # === File Handler ===
    if log_file or settings.LOG_FILE:
        log_path = Path(settings.BASE_DIR) / (log_file or settings.LOG_FILE)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(log_level)

        # Plain format for file (no colors)
        file_format = logging.Formatter(
            fmt="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name.

    Convenience function for scrapers to get their logger:
    ```python
    logger = get_logger("amazon")
    logger.info("Starting scrape...")
    ```
    """
    # Prefix with 'scraper.' for namespace organization
    full_name = f"scraper.{name}" if not name.startswith("scraper.") else name

    # Check if logger already exists
    if full_name in logging.Logger.manager.loggerDict:
        return logging.getLogger(full_name)

    # Setup new logger
    return setup_logger(full_name)


# Setup root scraper logger on module import
root_logger = setup_logger("scraper")
