"""
Generic Multi-Site Scraper

A flexible scraper that can be configured for different e-commerce sites.
Uses site-specific configurations for selectors.

Supports:
- TopAchat
- Materiel.net
- Cybertek
- Grosbill
- RueDuCommerce
"""

import asyncio
import re
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapingResult
from utils.logger import get_logger


@dataclass
class SiteConfig:
    """Configuration for a specific e-commerce site."""
    name: str
    display_name: str
    base_url: str
    price_selectors: List[str]
    name_selectors: List[str]
    image_selectors: List[str]
    availability_selectors: List[str]
    mpn_selectors: List[str]
    brand_selectors: List[str]
    cookie_accept_selectors: List[str] = None


# Site configurations
SITE_CONFIGS = {
    "topachat": SiteConfig(
        name="topachat",
        display_name="TopAchat",
        base_url="https://www.topachat.com",
        price_selectors=[
            ".product-price .price",
            ".offer-price",
            ".prix-produit",
            "[itemprop='price']",
        ],
        name_selectors=[
            "h1.product-title",
            "h1[itemprop='name']",
            ".product-name h1",
        ],
        image_selectors=[
            ".product-image img",
            "img[itemprop='image']",
            ".product-gallery img",
        ],
        availability_selectors=[
            ".stock-status",
            ".availability",
            "[itemprop='availability']",
        ],
        mpn_selectors=[
            "[itemprop='mpn']",
            ".product-ref",
        ],
        brand_selectors=[
            "[itemprop='brand']",
            ".product-brand",
        ],
        cookie_accept_selectors=[
            "#tarteaucitronPersonalize2",
            "button:has-text('Accepter')",
        ],
    ),

    "materiel_net": SiteConfig(
        name="materiel_net",
        display_name="Materiel.net",
        base_url="https://www.materiel.net",
        price_selectors=[
            ".product-price .price",
            ".o-product__price",
            "[itemprop='price']",
            ".price-box .price",
        ],
        name_selectors=[
            "h1.product-title",
            "h1[itemprop='name']",
            ".product-name",
        ],
        image_selectors=[
            ".product-image img",
            "img[itemprop='image']",
        ],
        availability_selectors=[
            ".stock-status",
            ".availability",
        ],
        mpn_selectors=[
            "[itemprop='mpn']",
            ".product-mpn",
        ],
        brand_selectors=[
            "[itemprop='brand']",
            ".product-brand",
        ],
        cookie_accept_selectors=[
            "#onetrust-accept-btn-handler",
            "button:has-text('Accepter')",
        ],
    ),

    "cybertek": SiteConfig(
        name="cybertek",
        display_name="Cybertek",
        base_url="https://www.cybertek.fr",
        price_selectors=[
            ".product-price",
            "[itemprop='price']",
            ".price-box .price",
        ],
        name_selectors=[
            "h1.product-name",
            "h1[itemprop='name']",
        ],
        image_selectors=[
            ".product-image img",
            "img[itemprop='image']",
        ],
        availability_selectors=[
            ".stock-status",
            ".availability",
        ],
        mpn_selectors=[
            "[itemprop='mpn']",
        ],
        brand_selectors=[
            "[itemprop='brand']",
        ],
        cookie_accept_selectors=[
            "button:has-text('Accepter')",
        ],
    ),

    "grosbill": SiteConfig(
        name="grosbill",
        display_name="GrosBill",
        base_url="https://www.grosbill.com",
        price_selectors=[
            ".product-price",
            "[itemprop='price']",
            ".prix",
        ],
        name_selectors=[
            "h1.product-name",
            "h1[itemprop='name']",
        ],
        image_selectors=[
            ".product-image img",
            "img[itemprop='image']",
        ],
        availability_selectors=[
            ".stock-status",
            ".availability",
        ],
        mpn_selectors=[
            "[itemprop='mpn']",
        ],
        brand_selectors=[
            "[itemprop='brand']",
        ],
        cookie_accept_selectors=[
            "button:has-text('Accepter')",
        ],
    ),
}


class GenericScraper(BaseScraper):
    """
    Generic scraper that can be configured for any e-commerce site.

    Usage:
        scraper = GenericScraper(site_name="topachat")
        scraper = GenericScraper(site_config=custom_config)
    """

    def __init__(self, site_name: str = None, site_config: SiteConfig = None):
        """
        Initialize with a site name or custom config.

        Args:
            site_name: Name of a pre-configured site (topachat, materiel_net, etc.)
            site_config: Custom SiteConfig object
        """
        if site_config:
            self.config = site_config
        elif site_name and site_name in SITE_CONFIGS:
            self.config = SITE_CONFIGS[site_name]
        else:
            raise ValueError(f"Unknown site: {site_name}. Available: {list(SITE_CONFIGS.keys())}")

        super().__init__()

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def display_name(self) -> str:
        return self.config.display_name

    @property
    def base_url(self) -> str:
        return self.config.base_url

    def get_price_selector(self) -> str:
        return self.config.price_selectors[0] if self.config.price_selectors else ""

    def get_product_name_selector(self) -> str:
        return self.config.name_selectors[0] if self.config.name_selectors else ""

    def get_image_selector(self) -> str:
        return self.config.image_selectors[0] if self.config.image_selectors else ""

    def get_availability_selector(self) -> str:
        return self.config.availability_selectors[0] if self.config.availability_selectors else ""

    async def pre_scrape_hook(self, page: Page, url: str) -> None:
        """Handle cookie popups."""
        await self._handle_cookies(page)

    async def _handle_cookies(self, page: Page) -> None:
        """Try to accept cookie consent."""
        if not self.config.cookie_accept_selectors:
            return

        for selector in self.config.cookie_accept_selectors:
            try:
                button = page.locator(selector)
                if await button.count() > 0:
                    await button.first.click()
                    await asyncio.sleep(0.5)
                    return
            except Exception:
                continue

    async def extract_price(self, page: Page) -> Optional[str]:
        """Extract price from page."""
        for selector in self.config.price_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    if text and re.search(r'\d', text):
                        return text.strip()
            except Exception:
                continue
        return None

    async def extract_product_name(self, page: Page) -> Optional[str]:
        """Extract product name from page."""
        for selector in self.config.name_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    if text:
                        return text.strip()
            except Exception:
                continue
        return None

    async def extract_image_url(self, page: Page) -> Optional[str]:
        """Extract product image URL from page."""
        for selector in self.config.image_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    url = await element.get_attribute("src")
                    if url and not url.startswith("data:"):
                        if url.startswith("//"):
                            url = "https:" + url
                        elif url.startswith("/"):
                            url = self.base_url + url
                        return url
            except Exception:
                continue
        return None

    async def check_availability(self, page: Page) -> bool:
        """Check product availability."""
        for selector in self.config.availability_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = (await element.text_content() or "").lower()
                    if any(word in text for word in ["en stock", "disponible", "in stock"]):
                        return True
                    if any(word in text for word in ["rupture", "indisponible", "out of stock"]):
                        return False
            except Exception:
                continue
        return True  # Default to available

    async def extract_mpn(self, page: Page) -> Optional[str]:
        """Extract MPN from page."""
        for selector in self.config.mpn_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    mpn = await element.text_content()
                    if mpn:
                        return mpn.strip()
            except Exception:
                continue
        return None

    async def extract_brand(self, page: Page) -> Optional[str]:
        """Extract brand from page."""
        for selector in self.config.brand_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    brand = await element.text_content()
                    if brand:
                        return brand.strip()
            except Exception:
                continue
        return None

    async def extract_full_product_data(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract all product data for the comparator pipeline.

        Returns:
            Dict with product data or None if extraction fails
        """
        name = await self.extract_product_name(page)
        price_str = await self.extract_price(page)
        image_url = await self.extract_image_url(page)
        available = await self.check_availability(page)
        brand = await self.extract_brand(page)
        mpn = await self.extract_mpn(page)

        if not name or not price_str:
            self.logger.warning(f"Missing essential data for {url}")
            return None

        # Parse price
        price = 0.0
        if price_str:
            price_val, _ = self.normalizer.normalize_price(price_str)
            price = price_val or 0.0

        return {
            "mpn": mpn,  # May be None - that's OK for discovered products
            "name": name,
            "brand": brand or "",
            "price": price,
            "currency": "EUR",
            "stock": available,
            "url": url,
            "image_url": image_url or "",
            "retailer": self.name,
        }


# Factory function
def create_scraper(site_name: str) -> GenericScraper:
    """Create a scraper for a specific site."""
    return GenericScraper(site_name=site_name)
