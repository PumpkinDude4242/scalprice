"""
Configuration settings for the RAM price scraper.
All configurable parameters are centralized here.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List


@dataclass
class Settings:
    """
    Main configuration class for the scraper engine.
    Uses dataclass for clean initialization and immutability.
    """

    # === Directory Paths ===
    BASE_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent)
    OUTPUT_DIR: Path = field(default_factory=lambda: Path(__file__).parent.parent / "output")

    # === Anti-Detection Settings ===
    # Minimum delay between requests (seconds)
    MIN_DELAY: float = 2.0
    # Maximum delay between requests (seconds)
    MAX_DELAY: float = 5.0
    # Extra delay after potential bot detection (seconds)
    BACKOFF_DELAY: float = 30.0
    # Maximum retries per URL before giving up
    MAX_RETRIES: int = 3

    # === Request Settings ===
    # Request timeout in milliseconds (Playwright)
    REQUEST_TIMEOUT: int = 30000
    # Whether to run browser in headless mode
    HEADLESS: bool = True
    # Browser to use: 'chromium', 'firefox', 'webkit'
    BROWSER_TYPE: str = 'chromium'

    # === Output Settings ===
    # JSON output filename prefix
    OUTPUT_PREFIX: str = "ram_prices"
    # Pretty print JSON output
    JSON_INDENT: int = 2

    # === Logging Settings ===
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "scraper.log"

    # === Enabled Scrapers ===
    # List of scraper names to run (empty = all available)
    ENABLED_SCRAPERS: List[str] = field(default_factory=lambda: [
        "amazon_fr",
        "ldlc",
        # "alternate",  # Uncomment to enable
    ])

    def __post_init__(self):
        """Ensure output directory exists."""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> 'Settings':
        """
        Create Settings from environment variables.
        Allows overriding defaults via .env file or shell environment.
        """
        return cls(
            MIN_DELAY=float(os.getenv('SCRAPER_MIN_DELAY', 2.0)),
            MAX_DELAY=float(os.getenv('SCRAPER_MAX_DELAY', 5.0)),
            HEADLESS=os.getenv('SCRAPER_HEADLESS', 'true').lower() == 'true',
            LOG_LEVEL=os.getenv('SCRAPER_LOG_LEVEL', 'INFO'),
        )


# Global settings instance
settings = Settings()
