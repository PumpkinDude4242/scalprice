"""
Base Scraper - Abstract Class for Strategy Pattern

This is the foundation for all site-specific scrapers.
New scrapers should:
1. Inherit from BaseScraper
2. Implement abstract methods
3. Register themselves in the factory

Design Pattern: Strategy Pattern
- Each scraper implements the same interface
- Scrapers can be swapped without changing the main engine
- Easy to add new sites by creating new classes
"""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, Page, BrowserContext

from utils.anti_detection import AntiDetection, BrowserProfile
from utils.normalizer import DataNormalizer, NormalizedProduct
from utils.logger import get_logger
from config.settings import settings


@dataclass
class ScrapingResult:
    """
    Result of a single product scrape attempt.
    """
    success: bool
    product: Optional[NormalizedProduct] = None
    error: Optional[str] = None
    url: str = ""


class BaseScraper(ABC):
    """
    Abstract base class for all site scrapers.

    Strategy Pattern Implementation:
    - Defines the interface all scrapers must follow
    - Common functionality (browser setup, anti-detection) is here
    - Site-specific logic is in child classes

    To create a new scraper:
    1. Create a new file (e.g., scrapers/newegg.py)
    2. Create class inheriting BaseScraper
    3. Implement all @abstractmethod methods
    4. Register in factory.py

    Example:
    ```python
    class NeweggScraper(BaseScraper):
        @property
        def name(self) -> str:
            return "newegg"

        def get_price_selector(self) -> str:
            return "li.price-current"
        # ... implement other methods
    ```
    """

    def __init__(self):
        """Initialize scraper with common dependencies."""
        self.anti_detection = AntiDetection()
        self.normalizer = DataNormalizer()
        self.logger = get_logger(self.name)

        # Browser instances (initialized on run)
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._profile: Optional[BrowserProfile] = None

        # Statistics
        self.stats = {
            "total_urls": 0,
            "successful": 0,
            "failed": 0,
            "skipped": 0,
        }

    # === Abstract Properties ===
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for this scraper.
        Used in logging and configuration.
        Example: "amazon_fr", "ldlc", "alternate"
        """
        pass

    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable name for output.
        Example: "Amazon FR", "LDLC", "Alternate"
        """
        pass

    @property
    @abstractmethod
    def base_url(self) -> str:
        """
        Base URL of the target site.
        Example: "https://www.amazon.fr"
        """
        pass

    # === Abstract Methods - Must be implemented by child classes ===
    @abstractmethod
    def get_price_selector(self) -> str:
        """
        Return CSS selector for the price element.
        This is SITE-SPECIFIC and must be determined by inspecting the site.

        Returns:
            CSS selector string
        """
        pass

    @abstractmethod
    def get_product_name_selector(self) -> str:
        """
        Return CSS selector for the product name/title.
        """
        pass

    @abstractmethod
    def get_image_selector(self) -> str:
        """
        Return CSS selector for product image.
        """
        pass

    @abstractmethod
    def get_availability_selector(self) -> str:
        """
        Return CSS selector for availability indicator.
        Can return empty string if site doesn't have clear indicator.
        """
        pass

    @abstractmethod
    async def extract_price(self, page: Page) -> Optional[str]:
        """
        Extract price from the page.

        This method may need custom logic for sites with complex pricing
        (e.g., multiple prices, hidden elements, dynamic loading).

        Args:
            page: Playwright page object

        Returns:
            Price string or None if not found
        """
        pass

    @abstractmethod
    async def extract_product_name(self, page: Page) -> Optional[str]:
        """
        Extract product name from the page.
        """
        pass

    @abstractmethod
    async def extract_image_url(self, page: Page) -> Optional[str]:
        """
        Extract product image URL from the page.
        """
        pass

    @abstractmethod
    async def check_availability(self, page: Page) -> bool:
        """
        Check if product is available/in stock.
        """
        pass

    # === Product Discovery Methods ===
    async def discover_products(self, search_queries: List[str], max_products: int = 20) -> List[str]:
        """
        Discover product URLs by searching the site.

        This method should be overridden by child classes to implement
        site-specific search functionality.

        Args:
            search_queries: List of search terms (e.g., ["DDR5 32Go", "Corsair Vengeance"])
            max_products: Maximum number of product URLs to return

        Returns:
            List of discovered product URLs
        """
        self.logger.warning(f"discover_products() not implemented for {self.name}")
        return []

    def get_search_url(self, query: str) -> str:
        """
        Build search URL for a given query.
        Override in child classes with site-specific URL format.

        Args:
            query: Search term

        Returns:
            Full search URL
        """
        # Default implementation - override in child classes
        return f"{self.base_url}/search?q={query}"

    async def extract_product_urls_from_search(self, page: Page) -> List[str]:
        """
        Extract product URLs from a search results page.
        Override in child classes with site-specific selectors.

        Args:
            page: Playwright page on search results

        Returns:
            List of product URLs found on the page
        """
        return []

    # === Optional Methods - Can be overridden for site-specific behavior ===
    async def pre_scrape_hook(self, page: Page, url: str) -> None:
        """
        Hook called before scraping each URL.
        Override for site-specific setup (closing popups, etc.)
        """
        pass

    async def post_scrape_hook(self, page: Page, result: ScrapingResult) -> None:
        """
        Hook called after scraping each URL.
        Override for cleanup or additional data extraction.
        """
        pass

    async def handle_bot_detection(self, page: Page) -> bool:
        """
        Handle bot detection if detected.

        Override for site-specific CAPTCHA handling.
        Default implementation waits and returns False.

        Returns:
            True if detection was bypassed, False otherwise
        """
        self.logger.warning("Bot detection suspected, applying backoff...")
        await self.anti_detection.backoff_delay()
        return False

    # === Core Methods - Common implementation ===
    async def setup_browser(self) -> None:
        """
        Initialize Playwright browser with anti-detection settings.

        ANTI-DETECTION MEASURES:
        1. Random viewport size
        2. Random User-Agent
        3. Timezone and locale matching
        4. Stealth scripts injection
        5. WebDriver flag removal
        """
        self.logger.info(f"Setting up browser for {self.display_name}...")

        # Generate new browser profile
        self._profile = self.anti_detection.get_browser_profile()
        context_options = self.anti_detection.get_playwright_context_options(self._profile)

        # Launch Playwright
        playwright = await async_playwright().start()

        # Choose browser type from settings
        browser_type = getattr(playwright, settings.BROWSER_TYPE)

        # Launch browser with stealth settings
        self._browser = await browser_type.launch(
            headless=settings.HEADLESS,
            args=[
                # Additional stealth arguments
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--ignore-certificate-errors-spki-list",
            ]
        )

        # Create context with anti-detection profile
        self._context = await self._browser.new_context(**context_options)

        # Inject stealth scripts into every page
        for script in self.anti_detection.get_stealth_scripts():
            await self._context.add_init_script(script)

        # Create main page
        self._page = await self._context.new_page()

        # Set extra headers
        headers = self.anti_detection.get_request_headers(self._profile)
        await self._page.set_extra_http_headers(headers)

        self.logger.debug(f"Browser ready with UA: {self._profile.user_agent[:50]}...")

    async def close_browser(self) -> None:
        """Clean up browser resources."""
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()

        self._page = None
        self._context = None
        self._browser = None

        self.logger.debug("Browser closed")

    async def navigate_to_url(self, url: str) -> bool:
        """
        Navigate to URL with retry logic.

        ANTI-DETECTION:
        - Random delay before navigation
        - Human-like scroll after page load
        - Wait for network idle

        Returns:
            True if navigation successful, False otherwise
        """
        if not self._page:
            self.logger.error("Browser not initialized!")
            return False

        for attempt in range(settings.MAX_RETRIES):
            try:
                # Random delay before request (mimics human)
                await self.anti_detection.random_delay()

                self.logger.debug(f"Navigating to: {url[:60]}... (attempt {attempt + 1})")

                # Navigate with timeout
                response = await self._page.goto(
                    url,
                    wait_until="networkidle",
                    timeout=settings.REQUEST_TIMEOUT,
                )

                # Check response status
                if response and response.status >= 400:
                    self.logger.warning(f"HTTP {response.status} for {url}")
                    if response.status == 403 or response.status == 429:
                        # Likely bot detection
                        await self.handle_bot_detection(self._page)
                        continue
                    return False

                # Simulate human behavior: random scroll
                await self._human_like_scroll()

                return True

            except Exception as e:
                self.logger.warning(f"Navigation failed (attempt {attempt + 1}): {str(e)[:100]}")
                if attempt < settings.MAX_RETRIES - 1:
                    await self.anti_detection.random_delay(multiplier=2)

        return False

    async def _human_like_scroll(self) -> None:
        """
        Perform human-like scrolling to appear natural.

        ANTI-DETECTION:
        - Bots often don't scroll
        - Random scroll amounts
        - Variable timing
        """
        import random

        if not self._page:
            return

        # Random number of scrolls (1-3)
        num_scrolls = random.randint(1, 3)

        for _ in range(num_scrolls):
            # Random scroll distance
            scroll_amount = random.randint(100, 400)
            await self._page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            await asyncio.sleep(random.uniform(0.3, 0.8))

    async def scrape_url(self, url: str) -> ScrapingResult:
        """
        Scrape a single URL and extract product data.

        This is the main scraping method that orchestrates:
        1. Navigation
        2. Pre-scrape hook
        3. Data extraction
        4. Normalization
        5. Post-scrape hook

        Returns:
            ScrapingResult with success status and product data
        """
        result = ScrapingResult(success=False, url=url)

        try:
            # Navigate to the page
            if not await self.navigate_to_url(url):
                result.error = "Navigation failed"
                return result

            # Run pre-scrape hook (popup handling, etc.)
            await self.pre_scrape_hook(self._page, url)

            # Extract data using abstract methods
            price_str = await self.extract_price(self._page)
            name_str = await self.extract_product_name(self._page)
            image_url = await self.extract_image_url(self._page)
            available = await self.check_availability(self._page)

            # Validate minimum required data
            if not price_str or not name_str:
                result.error = f"Missing data: price={bool(price_str)}, name={bool(name_str)}"
                self.logger.warning(f"Incomplete data for {url}: {result.error}")
                return result

            # Normalize the data
            product = self.normalizer.normalize_product(
                raw_name=name_str,
                raw_price=price_str,
                url=url,
                image_url=image_url or "",
                source_site=self.display_name,
                available=available,
            )

            result.success = True
            result.product = product

            # Run post-scrape hook
            await self.post_scrape_hook(self._page, result)

            self.logger.info(f"✓ {product.nom_produit[:40]}... → {product.prix_actuel} {product.devise}")

        except Exception as e:
            result.error = str(e)
            self.logger.error(f"Scraping error for {url}: {str(e)[:100]}")

        return result

    async def scrape_all(self, urls: List[str]) -> List[NormalizedProduct]:
        """
        Scrape all URLs and return list of products.

        Main entry point for scraping a batch of URLs.

        Args:
            urls: List of product URLs to scrape

        Returns:
            List of successfully scraped and normalized products
        """
        products: List[NormalizedProduct] = []
        self.stats["total_urls"] = len(urls)

        self.logger.info(f"Starting scrape of {len(urls)} URLs from {self.display_name}")

        try:
            await self.setup_browser()

            for i, url in enumerate(urls, 1):
                self.logger.info(f"[{i}/{len(urls)}] Processing: {url[:50]}...")

                result = await self.scrape_url(url)

                if result.success and result.product:
                    products.append(result.product)
                    self.stats["successful"] += 1
                else:
                    self.stats["failed"] += 1
                    self.logger.warning(f"Failed: {result.error}")

                # Check if we should rotate browser profile
                if self.anti_detection.should_rotate_profile():
                    self.logger.info("Rotating browser profile...")
                    await self.close_browser()
                    await self.setup_browser()

        except Exception as e:
            self.logger.error(f"Critical error during scrape: {e}")
        finally:
            await self.close_browser()

        # Log summary
        self.logger.info(
            f"Scrape complete: {self.stats['successful']}/{self.stats['total_urls']} successful, "
            f"{self.stats['failed']} failed"
        )

        return products

    def get_stats(self) -> Dict[str, int]:
        """Return scraping statistics."""
        return self.stats.copy()

    async def run(
        self,
        urls: List[str] = None,
        search_queries: List[str] = None,
        max_products: int = 20,
    ) -> List[NormalizedProduct]:
        """
        Main entry point: discover products via search OR scrape provided URLs.

        This is the recommended way to run the scraper:
        1. If search_queries provided: discover products first, then scrape
        2. If urls provided: scrape those URLs directly
        3. If both: combine discovered URLs with provided URLs

        Args:
            urls: Optional list of direct product URLs
            search_queries: Optional list of search terms for discovery
            max_products: Max products to discover per search

        Returns:
            List of scraped products
        """
        all_urls = set()

        # Add direct URLs if provided
        if urls:
            all_urls.update(urls)
            self.logger.info(f"Added {len(urls)} direct URLs")

        # Discover products via search if queries provided
        if search_queries:
            self.logger.info(f"Discovering products via {len(search_queries)} search queries...")
            try:
                await self.setup_browser()
                discovered = await self.discover_products(search_queries, max_products)
                all_urls.update(discovered)
                self.logger.info(f"Discovered {len(discovered)} product URLs")
                await self.close_browser()
            except Exception as e:
                self.logger.error(f"Discovery failed: {e}")

        if not all_urls:
            self.logger.warning("No URLs to scrape!")
            return []

        # Now scrape all collected URLs
        return await self.scrape_all(list(all_urls))
