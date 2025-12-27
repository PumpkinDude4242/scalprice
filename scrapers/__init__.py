# Scrapers package
from .base import BaseScraper
from .amazon import AmazonScraper
from .ldlc import LDLCScraper
from .factory import ScraperFactory, scraper_registry

__all__ = [
    'BaseScraper',
    'AmazonScraper',
    'LDLCScraper',
    'ScraperFactory',
    'scraper_registry',
]
