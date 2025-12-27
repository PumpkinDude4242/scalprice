"""
Amazon France Scraper

COMPLEXITY LEVEL: HIGH
Amazon is one of the most difficult sites to scrape due to:
1. Aggressive bot detection
2. Dynamic pricing elements
3. Frequent HTML structure changes
4. Multiple price formats (regular, deal, prime-only)
5. Cookie consent popups
6. CAPTCHA challenges

ANTI-DETECTION STRATEGIES USED:
- Realistic browser fingerprinting
- Human-like delays and scrolling
- Cookie consent handling
- Multiple price selector fallbacks
- Session management
"""

import asyncio
import re
from typing import Optional
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from .base import BaseScraper, ScrapingResult
from utils.logger import get_logger


class AmazonScraper(BaseScraper):
    """
    Scraper for Amazon France (amazon.fr).

    Handles Amazon's complex structure with multiple fallback selectors
    for each data point, ensuring resilience to HTML changes.
    """

    @property
    def name(self) -> str:
        return "amazon_fr"

    @property
    def display_name(self) -> str:
        return "Amazon FR"

    @property
    def base_url(self) -> str:
        return "https://www.amazon.fr"

    # === CSS SELECTORS ===
    # Multiple selectors for each element (fallback chain)
    # Amazon frequently changes their HTML, so we need alternatives

    # Price selectors - tried in order
    PRICE_SELECTORS = [
        # Standard price (whole + fraction)
        "#corePrice_feature_div .a-price .a-offscreen",
        # Deal price
        "#dealsAccordionRow .a-price .a-offscreen",
        # Alternative layout
        "#price_inside_buybox",
        "#priceblock_ourprice",
        "#priceblock_dealprice",
        # Apex price (new layout 2024)
        "#apex_desktop .a-price .a-offscreen",
        "#apex_offerDisplay_desktop .a-price .a-offscreen",
        # Mobile fallback
        ".a-price .a-offscreen",
        # Raw price text
        ".a-price-whole",
    ]

    # Product name selectors
    NAME_SELECTORS = [
        "#productTitle",
        "#title",
        "h1.a-size-large",
        "#centerCol h1 span",
        ".product-title-word-break",
    ]

    # Image selectors
    IMAGE_SELECTORS = [
        "#landingImage",
        "#imgBlkFront",
        "#main-image",
        ".a-dynamic-image",
        "#imgTagWrapperId img",
    ]

    # Availability selectors
    AVAILABILITY_SELECTORS = [
        "#availability span",
        "#availability",
        "#add-to-cart-button",  # If exists, product is available
        "#buy-now-button",
    ]

    # Bot detection indicators
    BOT_DETECTION_SELECTORS = [
        "form[action*='validateCaptcha']",
        "#captchacharacters",
        "input[name='amzn']",  # CAPTCHA input
        ".a-box-inner h4",  # "Enter the characters" header
    ]

    def get_price_selector(self) -> str:
        """Return primary price selector."""
        return self.PRICE_SELECTORS[0]

    def get_product_name_selector(self) -> str:
        """Return primary name selector."""
        return self.NAME_SELECTORS[0]

    def get_image_selector(self) -> str:
        """Return primary image selector."""
        return self.IMAGE_SELECTORS[0]

    def get_availability_selector(self) -> str:
        """Return primary availability selector."""
        return self.AVAILABILITY_SELECTORS[0]

    async def pre_scrape_hook(self, page: Page, url: str) -> None:
        """
        Handle Amazon-specific pre-scrape tasks:
        1. Cookie consent popup
        2. Bot detection check
        3. Wait for dynamic content
        """
        # Handle cookie consent popup (GDPR)
        await self._handle_cookie_popup(page)

        # Check for bot detection
        if await self._is_bot_detected(page):
            self.logger.warning("Bot detection triggered on Amazon!")
            await self.handle_bot_detection(page)

        # Wait for price to load (dynamic)
        try:
            await page.wait_for_selector(
                ".a-price, #price, #priceblock_ourprice",
                timeout=5000,
            )
        except PlaywrightTimeout:
            self.logger.debug("Price selector timeout - may still be loading")

    async def _handle_cookie_popup(self, page: Page) -> None:
        """
        Dismiss Amazon's cookie consent popup.

        ANTI-DETECTION NOTE:
        Not accepting cookies looks suspicious.
        We accept them like a real user would.
        """
        try:
            # Look for the accept button
            accept_selectors = [
                "#sp-cc-accept",  # Primary
                "input[name='accept']",  # Alternative
                "button[data-action='sp-cc-accept']",
            ]

            for selector in accept_selectors:
                button = page.locator(selector)
                if await button.count() > 0:
                    await button.click()
                    self.logger.debug("Cookie popup dismissed")
                    await asyncio.sleep(0.5)  # Wait for popup to close
                    break

        except Exception as e:
            self.logger.debug(f"Cookie popup handling: {e}")

    async def _is_bot_detected(self, page: Page) -> bool:
        """
        Check if Amazon's bot detection has been triggered.

        Amazon uses several methods:
        1. CAPTCHA challenges
        2. "Enter characters" page
        3. Rate limiting responses
        """
        for selector in self.BOT_DETECTION_SELECTORS:
            try:
                element = page.locator(selector)
                if await element.count() > 0:
                    return True
            except Exception:
                pass

        # Check page title for captcha
        title = await page.title()
        if "robot" in title.lower() or "captcha" in title.lower():
            return True

        return False

    async def handle_bot_detection(self, page: Page) -> bool:
        """
        Handle Amazon's bot detection.

        NOTE: We cannot automatically solve CAPTCHAs (that would require
        paid services). Instead, we:
        1. Log the detection
        2. Wait longer
        3. Try to continue with a new session

        Returns:
            False always - manual intervention may be needed
        """
        self.logger.error(
            "Amazon CAPTCHA detected! Cannot bypass automatically. "
            "Consider increasing delays or reducing scrape frequency."
        )

        # Long backoff to avoid further detection
        await self.anti_detection.backoff_delay()

        # In a real scenario, you might:
        # 1. Rotate IP (if using rotating residential proxies)
        # 2. Alert the operator
        # 3. Skip this site temporarily

        return False

    async def extract_price(self, page: Page) -> Optional[str]:
        """
        Extract price from Amazon page.

        Amazon has MULTIPLE price displays:
        - Regular price
        - Deal price (red)
        - Prime-only price
        - Price range for variants

        We try multiple selectors and pick the best one.
        """
        for selector in self.PRICE_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    if text:
                        text = text.strip()
                        # Validate it looks like a price
                        if re.search(r"[\d,\.]+", text):
                            self.logger.debug(f"Found price with selector '{selector}': {text}")
                            return text
            except Exception as e:
                self.logger.debug(f"Price selector '{selector}' failed: {e}")
                continue

        # Last resort: search for any price-like pattern
        try:
            content = await page.content()
            # Look for price patterns in page source
            patterns = [
                r'"priceAmount":\s*"?([\d,\.]+)"?',
                r'"price":\s*"?([\d,\.]+)"?',
                r'>(\d+[,\.]\d{2})\s*€<',
            ]
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    return match.group(1) + " €"
        except Exception:
            pass

        return None

    async def extract_product_name(self, page: Page) -> Optional[str]:
        """
        Extract product name from Amazon page.
        """
        for selector in self.NAME_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.text_content()
                    if text and len(text.strip()) > 5:
                        return text.strip()
            except Exception:
                continue

        return None

    async def extract_image_url(self, page: Page) -> Optional[str]:
        """
        Extract product image URL from Amazon page.

        Amazon uses:
        - data-old-hires attribute for high-res
        - src attribute for standard
        - data-a-dynamic-image for multiple sizes
        """
        for selector in self.IMAGE_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    # Try data-old-hires first (highest quality)
                    url = await element.get_attribute("data-old-hires")
                    if url:
                        return url

                    # Try src
                    url = await element.get_attribute("src")
                    if url and not url.startswith("data:"):
                        return url

                    # Try data-a-dynamic-image (JSON with multiple sizes)
                    dynamic = await element.get_attribute("data-a-dynamic-image")
                    if dynamic:
                        # Parse JSON and get first URL
                        import json
                        try:
                            images = json.loads(dynamic)
                            if images:
                                return list(images.keys())[0]
                        except json.JSONDecodeError:
                            pass

            except Exception:
                continue

        return None

    async def check_availability(self, page: Page) -> bool:
        """
        Check if product is available on Amazon.

        Amazon shows:
        - "En stock" / "In Stock"
        - "Temporairement en rupture" (Out of stock)
        - "Habituellement expédié sous X jours"
        - Add to cart button presence

        Returns:
            True if product appears to be available
        """
        # Check for add-to-cart button (strongest indicator)
        try:
            add_to_cart = page.locator("#add-to-cart-button")
            if await add_to_cart.count() > 0:
                return True
        except Exception:
            pass

        # Check availability text
        try:
            for selector in self.AVAILABILITY_SELECTORS[:2]:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = (await element.text_content() or "").lower()

                    # Positive indicators
                    if any(word in text for word in ["en stock", "in stock", "disponible"]):
                        return True

                    # Negative indicators
                    if any(word in text for word in ["rupture", "indisponible", "out of stock"]):
                        return False
        except Exception:
            pass

        # Default to True if we can't determine
        # (better to list with a price than miss it)
        return True

    async def post_scrape_hook(self, page: Page, result: ScrapingResult) -> None:
        """
        Post-scrape cleanup and additional data extraction.
        """
        # Nothing special needed for Amazon
        pass
