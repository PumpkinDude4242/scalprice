# Scrapers package
from .base import BaseScraper
from .amazon import AmazonScraper
from .ldlc import LDLCScraper
from .generic import GenericScraper, SITE_CONFIGS, SiteConfig
from .factory import ScraperFactory, scraper_registry

__all__ = [
    'BaseScraper',
    'AmazonScraper',
    'LDLCScraper',
    'GenericScraper',
    'SiteConfig',
    'SITE_CONFIGS',
    'ScraperFactory',
    'scraper_registry',
]
