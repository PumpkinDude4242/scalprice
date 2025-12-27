"""
LDLC.com Scraper

COMPLEXITY LEVEL: MEDIUM
LDLC is a major French tech retailer. Their site is:
- Relatively simple HTML structure
- Less aggressive bot detection than Amazon
- Consistent CSS selectors
- Good performance

ANTI-DETECTION NOTES:
LDLC has lighter protection, but we still apply:
- Random delays (they do have rate limiting)
- User-Agent rotation
- Cookie consent handling
"""

import asyncio
import re
import urllib.parse
from typing import Optional, List
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapingResult
from utils.logger import get_logger


class LDLCScraper(BaseScraper):
    """
    Scraper for LDLC.com (French tech retailer).

    LDLC has a cleaner structure than Amazon, making it
    easier to scrape reliably.
    """

    @property
    def name(self) -> str:
        return "ldlc"

    @property
    def display_name(self) -> str:
        return "LDLC"

    @property
    def base_url(self) -> str:
        return "https://www.ldlc.com"

    # === CSS SELECTORS ===
    # LDLC's structure is more consistent, so fewer fallbacks needed

    # Price selectors
    PRICE_SELECTORS = [
        # Main product page price
        ".price .price",
        "aside.product-info .price",
        ".product-page .price",
        # Sale price
        ".new-price .price",
        # Fallback patterns
        "[data-price]",
        ".prix",
    ]

    # Product name selectors
    NAME_SELECTORS = [
        "h1.title-1",
        ".product-page h1",
        "h1[itemprop='name']",
        ".product-info h1",
        "h1.product-title",
    ]

    # Image selectors
    IMAGE_SELECTORS = [
        ".product-image img",
        ".product-page img.img-fluid",
        "img[itemprop='image']",
        ".product-visual img",
        "#product-images img",
    ]

    # Availability selectors
    AVAILABILITY_SELECTORS = [
        ".stock .content",
        ".availability",
        ".product-stock",
        ".in-stock",
        ".out-of-stock",
    ]

    def get_price_selector(self) -> str:
        return self.PRICE_SELECTORS[0]

    def get_product_name_selector(self) -> str:
        return self.NAME_SELECTORS[0]

    def get_image_selector(self) -> str:
        return self.IMAGE_SELECTORS[0]

    def get_availability_selector(self) -> str:
        return self.AVAILABILITY_SELECTORS[0]

    async def pre_scrape_hook(self, page: Page, url: str) -> None:
        """
        Handle LDLC-specific pre-scrape tasks:
        1. Cookie consent popup (GDPR)
        2. Age verification popup (for some products)
        3. Newsletter popup
        """
        # Handle cookie consent
        await self._handle_cookie_consent(page)

        # Handle any newsletter popup
        await self._close_newsletter_popup(page)

        # Wait for main content to load
        try:
            await page.wait_for_selector(
                "h1, .product-page, .product-info",
                timeout=5000,
            )
        except PlaywrightTimeout:
            self.logger.debug("Main content selector timeout")

    async def _handle_cookie_consent(self, page: Page) -> None:
        """
        Handle LDLC's cookie consent popup.

        LDLC uses a standard cookie banner that we need to accept.
        """
        try:
            # Common cookie accept button selectors
            accept_selectors = [
                "#cookieConsentAcceptButton",
                "button[data-consent='accept']",
                ".cookie-consent button.accept",
                "#tarteaucitronPersonalize2",  # French cookie lib
                ".cc-btn.cc-allow",
                "button:has-text('Accepter')",
                "button:has-text('J'accepte')",
            ]

            for selector in accept_selectors:
                try:
                    button = page.locator(selector)
                    if await button.count() > 0:
                        await button.first.click()
                        self.logger.debug(f"Cookie consent accepted via {selector}")
                        await asyncio.sleep(0.3)
                        return
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Cookie consent handling: {e}")

    async def _close_newsletter_popup(self, page: Page) -> None:
        """
        Close any newsletter/promo popup that might appear.
        """
        try:
            close_selectors = [
                ".popup-close",
                ".modal-close",
                "button[aria-label='Fermer']",
                ".newsletter-popup .close",
                "[data-dismiss='modal']",
            ]

            for selector in close_selectors:
                try:
                    button = page.locator(selector)
                    if await button.count() > 0 and await button.first.is_visible():
                        await button.first.click()
                        self.logger.debug("Newsletter popup closed")
                        await asyncio.sleep(0.3)
                        return
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Newsletter popup handling: {e}")

    async def extract_price(self, page: Page) -> Optional[str]:
        """
        Extract price from LDLC page.

        LDLC typically shows:
        - Single price (no variants)
        - Clear formatting: "145,99€" or "145.99 €"
        """
        for selector in self.PRICE_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    if text:
                        text = text.strip()
                        # Validate it contains numbers
                        if re.search(r"\d+", text):
                            self.logger.debug(f"Found price: {text}")
                            return text
            except Exception as e:
                self.logger.debug(f"Price selector '{selector}' failed: {e}")
                continue

        # Try data-price attribute
        try:
            elements = page.locator("[data-price]")
            count = await elements.count()
            for i in range(count):
                element = elements.nth(i)
                price = await element.get_attribute("data-price")
                if price:
                    return price + " €"
        except Exception:
            pass

        # Last resort: search in page content
        try:
            content = await page.content()
            # LDLC price pattern
            match = re.search(r'"price":\s*"?([\d,\.]+)"?', content)
            if match:
                return match.group(1) + " €"

            # Alternative pattern
            match = re.search(r'(\d+[,\.]\d{2})\s*€', content)
            if match:
                return match.group(0)
        except Exception:
            pass

        return None

    async def extract_product_name(self, page: Page) -> Optional[str]:
        """
        Extract product name from LDLC page.

        LDLC typically has the product name in an H1 tag.
        """
        for selector in self.NAME_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    if text and len(text.strip()) > 3:
                        # Clean up the name
                        name = text.strip()
                        # Remove reference numbers sometimes included
                        name = re.sub(r"^Réf\.\s*\d+\s*-?\s*", "", name)
                        return name
            except Exception:
                continue

        # Fallback: meta title
        try:
            title = await page.title()
            if title:
                # Remove " - LDLC" suffix
                title = re.sub(r"\s*[-|]\s*LDLC.*$", "", title)
                return title.strip()
        except Exception:
            pass

        return None

    async def extract_image_url(self, page: Page) -> Optional[str]:
        """
        Extract product image URL from LDLC page.
        """
        for selector in self.IMAGE_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    # Try src attribute
                    url = await element.get_attribute("src")
                    if url and not url.startswith("data:"):
                        # Make absolute if needed
                        if url.startswith("//"):
                            url = "https:" + url
                        elif url.startswith("/"):
                            url = self.base_url + url
                        return url

                    # Try data-src (lazy loading)
                    url = await element.get_attribute("data-src")
                    if url:
                        if url.startswith("//"):
                            url = "https:" + url
                        elif url.startswith("/"):
                            url = self.base_url + url
                        return url

            except Exception:
                continue

        return None

    async def check_availability(self, page: Page) -> bool:
        """
        Check if product is available on LDLC.

        LDLC shows clear stock status:
        - "En stock" / "En Stock Web"
        - "Rupture" / "Rupture de stock"
        - "Sur commande" (available but delayed)
        """
        try:
            for selector in self.AVAILABILITY_SELECTORS:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = (await element.text_content() or "").lower()

                    # Check for availability indicators
                    if any(word in text for word in [
                        "en stock",
                        "disponible",
                        "sur commande",
                        "expédié sous",
                    ]):
                        return True

                    if any(word in text for word in [
                        "rupture",
                        "indisponible",
                        "épuisé",
                    ]):
                        return False
        except Exception as e:
            self.logger.debug(f"Availability check failed: {e}")

        # Check for add-to-cart button as fallback
        try:
            add_button = page.locator("button:has-text('Ajouter au panier'), .add-to-cart")
            if await add_button.count() > 0:
                return True
        except Exception:
            pass

        # Default to True if undetermined
        return True

    async def post_scrape_hook(self, page: Page, result: ScrapingResult) -> None:
        """
        Post-scrape hook for LDLC.
        """
        # Could extract additional data here (specs, reviews, etc.)
        pass

    async def handle_bot_detection(self, page: Page) -> bool:
        """
        Handle LDLC's bot detection.

        LDLC is less aggressive than Amazon, so usually
        a simple delay is enough.
        """
        self.logger.warning("LDLC rate limiting detected, applying backoff...")
        await self.anti_detection.backoff_delay()
        return False

    # === Product Discovery Methods ===
    def get_search_url(self, query: str) -> str:
        """
        Build LDLC search URL.

        LDLC search URL format:
        https://www.ldlc.com/recherche/DDR5%2032Go/
        """
        encoded_query = urllib.parse.quote(query)
        return f"{self.base_url}/recherche/{encoded_query}/"

    async def extract_product_urls_from_search(self, page: Page) -> List[str]:
        """
        Extract product URLs from LDLC search results page.

        LDLC search results have links like:
        <a href="/fiche/PB00275038.html">Product Name</a>
        """
        urls = set()

        try:
            # Wait for search results to load
            await page.wait_for_selector('a[href*="/fiche/PB"]', timeout=10000)

            # Find all product links
            links = page.locator('a[href*="/fiche/PB"]')
            count = await links.count()

            for i in range(count):
                try:
                    href = await links.nth(i).get_attribute("href")
                    if href and "/fiche/PB" in href:
                        # Build full URL
                        if href.startswith("/"):
                            full_url = self.base_url + href
                        else:
                            full_url = href
                        # Remove query params and anchors
                        full_url = full_url.split("?")[0].split("#")[0]
                        urls.add(full_url)
                except Exception:
                    continue

            self.logger.debug(f"Found {len(urls)} product URLs on search page")

        except PlaywrightTimeout:
            self.logger.warning("No search results found (timeout)")
        except Exception as e:
            self.logger.error(f"Error extracting search results: {e}")

        return list(urls)

    async def discover_products(
        self,
        search_queries: List[str],
        max_products: int = 20
    ) -> List[str]:
        """
        Discover LDLC products by searching.

        Args:
            search_queries: List of search terms (e.g., ["DDR5 32Go"])
            max_products: Maximum total products to return

        Returns:
            List of discovered product URLs
        """
        all_urls = set()

        for query in search_queries:
            if len(all_urls) >= max_products:
                break

            search_url = self.get_search_url(query)
            self.logger.info(f"Searching LDLC: '{query}'")

            try:
                # Navigate to search results
                if await self.navigate_to_url(search_url):
                    # Handle cookie popup on first search
                    await self._handle_cookie_consent(self._page)

                    # Extract product URLs
                    urls = await self.extract_product_urls_from_search(self._page)

                    # Filter for RAM products (contain DDR in link text or nearby)
                    for url in urls:
                        if len(all_urls) >= max_products:
                            break
                        all_urls.add(url)

                    self.logger.info(f"  Found {len(urls)} products for '{query}'")

            except Exception as e:
                self.logger.error(f"Search failed for '{query}': {e}")

            # Delay between searches
            await self.anti_detection.random_delay()

        self.logger.info(f"Total discovered: {len(all_urls)} unique product URLs")
        return list(all_urls)[:max_products]
