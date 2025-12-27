"""
Simple HTTP-based Scraper - Fallback without Playwright

Uses httpx + BeautifulSoup for sites that don't require JS rendering.
This is a lightweight alternative when Playwright isn't available.
"""

import asyncio
import re
from typing import Optional, List
from dataclasses import dataclass
import httpx
from bs4 import BeautifulSoup

from utils.anti_detection import AntiDetection
from utils.normalizer import DataNormalizer, NormalizedProduct
from utils.logger import get_logger
from config.settings import settings


@dataclass
class SimpleScrapingResult:
    """Result of a simple HTTP scrape."""
    success: bool
    product: Optional[NormalizedProduct] = None
    error: Optional[str] = None
    url: str = ""


class SimpleHTTPScraper:
    """
    Simple HTTP-based scraper using httpx + BeautifulSoup.

    Use this for sites that:
    - Don't heavily rely on JavaScript
    - Have simpler anti-bot protection
    - When Playwright isn't available
    """

    def __init__(self, name: str = "simple", display_name: str = "Simple HTTP"):
        self.name = name
        self.display_name = display_name
        self.anti_detection = AntiDetection()
        self.normalizer = DataNormalizer()
        self.logger = get_logger(name)
        self._client: Optional[httpx.AsyncClient] = None

    async def setup(self):
        """Initialize HTTP client with anti-detection headers."""
        profile = self.anti_detection.get_browser_profile()
        headers = self.anti_detection.get_request_headers(profile)

        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_page(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a page and return parsed HTML."""
        if not self._client:
            await self.setup()

        try:
            await self.anti_detection.random_delay()
            response = await self._client.get(url)

            if response.status_code == 200:
                return BeautifulSoup(response.text, 'lxml')
            else:
                self.logger.warning(f"HTTP {response.status_code} for {url}")
                return None

        except Exception as e:
            self.logger.error(f"Fetch error: {e}")
            return None


class SimpleLDLCScraper(SimpleHTTPScraper):
    """
    Simple HTTP scraper for LDLC.
    LDLC works reasonably well without JS rendering.
    """

    def __init__(self):
        super().__init__(name="ldlc_simple", display_name="LDLC (HTTP)")

    async def scrape_url(self, url: str) -> SimpleScrapingResult:
        """Scrape a single LDLC product URL."""
        result = SimpleScrapingResult(success=False, url=url)

        try:
            soup = await self.fetch_page(url)
            if not soup:
                result.error = "Failed to fetch page"
                return result

            # Extract product name
            name = None
            for selector in ['h1.title-1', 'h1', '.product-page h1']:
                elem = soup.select_one(selector)
                if elem:
                    name = elem.get_text(strip=True)
                    break

            # Extract price
            price = None
            for selector in ['.price .price', 'aside.product-info .price', '.price']:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    if re.search(r'\d', text):
                        price = text
                        break

            # Extract image
            image_url = ""
            for selector in ['.product-image img', 'img[itemprop="image"]', '.product-visual img']:
                elem = soup.select_one(selector)
                if elem:
                    image_url = elem.get('src') or elem.get('data-src') or ""
                    if image_url.startswith('//'):
                        image_url = 'https:' + image_url
                    elif image_url.startswith('/'):
                        image_url = 'https://www.ldlc.com' + image_url
                    break

            # Check availability
            available = True
            stock_elem = soup.select_one('.stock .content, .availability')
            if stock_elem:
                text = stock_elem.get_text(strip=True).lower()
                if 'rupture' in text or 'indisponible' in text:
                    available = False

            if not name or not price:
                result.error = f"Missing data: name={bool(name)}, price={bool(price)}"
                return result

            # Normalize
            product = self.normalizer.normalize_product(
                raw_name=name,
                raw_price=price,
                url=url,
                image_url=image_url,
                source_site=self.display_name,
                available=available,
            )

            result.success = True
            result.product = product
            self.logger.info(f"✓ {product.nom_produit[:40]}... → {product.prix_actuel} {product.devise}")

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"Scrape error: {e}")

        return result

    async def scrape_all(self, urls: List[str]) -> List[NormalizedProduct]:
        """Scrape all URLs."""
        products = []

        self.logger.info(f"Starting simple HTTP scrape of {len(urls)} URLs")

        try:
            await self.setup()

            for i, url in enumerate(urls, 1):
                self.logger.info(f"[{i}/{len(urls)}] Processing: {url[:50]}...")
                result = await self.scrape_url(url)

                if result.success and result.product:
                    products.append(result.product)
                else:
                    self.logger.warning(f"Failed: {result.error}")

        finally:
            await self.close()

        self.logger.info(f"Scrape complete: {len(products)}/{len(urls)} successful")
        return products


async def test_simple_scraper():
    """Test the simple HTTP scraper."""
    from config.products import PRODUCT_URLS

    scraper = SimpleLDLCScraper()
    urls = PRODUCT_URLS.get("ldlc", [])[:2]  # Test with first 2 URLs

    if not urls:
        print("No LDLC URLs configured")
        return

    products = await scraper.scrape_all(urls)

    print(f"\n=== Results ===")
    for p in products:
        print(f"  {p.nom_produit[:50]}: {p.prix_actuel} {p.devise}")

    return products


if __name__ == "__main__":
    asyncio.run(test_simple_scraper())
