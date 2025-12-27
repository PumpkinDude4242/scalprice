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

MPN EXTRACTION:
LDLC displays the MPN (Référence constructeur) in the product specifications.
This is critical for cross-site matching.
"""

import asyncio
import re
import urllib.parse
from typing import Optional, List, Dict, Any
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapingResult
from utils.logger import get_logger


class LDLCScraper(BaseScraper):
    """
    Scraper for LDLC.com (French tech retailer).

    LDLC has a cleaner structure than Amazon, making it
    easier to scrape reliably. Also extracts MPN for cross-site matching.
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

    # MPN / Manufacturer Reference selectors
    # LDLC shows this in specs table as "Référence constructeur" or "MPN"
    MPN_SELECTORS = [
        # Specs table row with "Référence" label
        ".specs-table tr:has(th:text-matches('Réf.*constructeur', 'i')) td",
        ".product-specs tr:has(th:text-matches('Réf.*constructeur', 'i')) td",
        # Alternative: look for MPN pattern in page
        "[itemprop='mpn']",
        "[data-mpn]",
    ]

    # Brand selectors
    BRAND_SELECTORS = [
        ".product-brand",
        "[itemprop='brand']",
        ".brand-name",
        "a.brand",
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

    # === MPN Extraction Methods ===
    async def extract_mpn(self, page: Page) -> Optional[str]:
        """
        Extract the Manufacturer Part Number (MPN) from LDLC product page.

        LDLC displays the MPN as "Référence constructeur" in the specs table.
        This is CRITICAL for cross-site product matching.

        Returns:
            MPN string or None if not found
        """
        # Method 1: Try structured selectors
        for selector in self.MPN_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    mpn = await element.text_content()
                    if mpn:
                        mpn = mpn.strip()
                        if mpn and len(mpn) > 3:
                            self.logger.debug(f"Found MPN via selector: {mpn}")
                            return mpn
            except Exception:
                continue

        # Method 2: Parse the specs table manually
        try:
            # Look for all table rows in specs section
            rows = page.locator(".product-sheet table tr, .specs tr, .characteristics tr")
            count = await rows.count()

            for i in range(count):
                row = rows.nth(i)
                try:
                    # Get header/label cell
                    header = await row.locator("th, td:first-child").first.text_content()
                    if header and any(kw in header.lower() for kw in [
                        "référence constructeur",
                        "ref constructeur",
                        "réf. constructeur",
                        "mpn",
                        "part number",
                        "numéro de modèle"
                    ]):
                        # Get value cell
                        value = await row.locator("td:last-child, td:nth-child(2)").first.text_content()
                        if value:
                            mpn = value.strip()
                            if mpn and len(mpn) > 3:
                                self.logger.debug(f"Found MPN in specs table: {mpn}")
                                return mpn
                except Exception:
                    continue

        except Exception as e:
            self.logger.debug(f"Specs table parsing failed: {e}")

        # Method 3: Search in page content with regex
        try:
            content = await page.content()

            # Common MPN patterns for RAM:
            # Kingston: KF564S38IBK2-32, KVR32S22D8/32
            # Corsair: CMK32GX5M2B5600C36
            # G.Skill: F5-6000J3636F16GX2-TZ5N
            patterns = [
                r'"mpn":\s*"([A-Z0-9][A-Z0-9\-_]{5,30})"',
                r'Réf(?:érence)?\.?\s*constructeur[:\s]+([A-Z0-9][A-Z0-9\-_]{5,30})',
                r'MPN[:\s]+([A-Z0-9][A-Z0-9\-_]{5,30})',
            ]

            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    mpn = match.group(1).strip()
                    if len(mpn) > 5:
                        self.logger.debug(f"Found MPN via regex: {mpn}")
                        return mpn

        except Exception as e:
            self.logger.debug(f"Content regex search failed: {e}")

        self.logger.warning("Could not extract MPN from page")
        return None

    async def extract_brand(self, page: Page) -> Optional[str]:
        """
        Extract the brand/manufacturer name from LDLC product page.

        Returns:
            Brand name or None
        """
        for selector in self.BRAND_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    brand = await element.text_content()
                    if brand:
                        return brand.strip()
            except Exception:
                continue

        # Try to extract from product name
        try:
            name = await self.extract_product_name(page)
            if name:
                # Common brands at the start of product names
                brands = [
                    "Kingston", "Corsair", "G.Skill", "Crucial", "Samsung",
                    "HyperX", "TeamGroup", "Patriot", "ADATA", "PNY",
                    "Lexar", "Western Digital", "Seagate", "Toshiba"
                ]
                for brand in brands:
                    if name.lower().startswith(brand.lower()):
                        return brand
        except Exception:
            pass

        return None

    async def extract_full_product_data(self, page: Page, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract all product data including MPN for the comparator pipeline.

        Returns:
            Dict with all product data or None if MPN extraction fails
        """
        mpn = await self.extract_mpn(page)

        if not mpn:
            self.logger.warning(f"Skipping product (no MPN): {url}")
            return None

        name = await self.extract_product_name(page)
        price_str = await self.extract_price(page)
        image_url = await self.extract_image_url(page)
        available = await self.check_availability(page)
        brand = await self.extract_brand(page)

        # Parse price
        price = 0.0
        if price_str:
            price_val, _ = self.normalizer.normalize_price(price_str)
            price = price_val or 0.0

        return {
            "mpn": mpn,
            "name": name or f"Product {mpn}",
            "brand": brand or "",
            "price": price,
            "currency": "EUR",
            "stock": available,
            "url": url,
            "image_url": image_url or "",
            "retailer": self.name,
        }

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
