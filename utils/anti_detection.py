"""
Anti-Detection Module - FREE Bot Evasion Techniques

This module implements various techniques to avoid bot detection WITHOUT
using any paid proxy services or anti-bot APIs. All methods are "homemade".

Techniques used:
1. User-Agent Rotation: Mimics different browsers/devices
2. Random Delays: Human-like timing between requests
3. Browser Fingerprint Randomization: Varies viewport, timezone, etc.
4. Cookie/Session Management: Maintains realistic sessions
5. Request Header Randomization: Varies Accept-Language, etc.
"""

import random
import time
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from fake_useragent import UserAgent

from config.settings import settings


@dataclass
class BrowserProfile:
    """
    Represents a complete browser fingerprint for anti-detection.
    Each scraping session uses a different profile.
    """
    user_agent: str
    viewport: Dict[str, int]
    timezone_id: str
    locale: str
    accept_language: str
    platform: str


class AntiDetection:
    """
    Anti-detection manager providing FREE bot evasion capabilities.

    NO PAID SERVICES - Everything is handled locally:
    - fake-useragent library for User-Agent rotation
    - Native Python random for timing variations
    - Custom header rotation logic
    """

    # === Common European Timezones ===
    TIMEZONES = [
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/London",
        "Europe/Madrid",
        "Europe/Rome",
        "Europe/Amsterdam",
        "Europe/Brussels",
    ]

    # === Accept-Language Headers (European focus) ===
    ACCEPT_LANGUAGES = [
        "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "fr-FR,fr;q=0.9,en;q=0.8",
        "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "en-GB,en;q=0.9,fr-FR;q=0.8,fr;q=0.7",
        "es-ES,es;q=0.9,en;q=0.8",
        "it-IT,it;q=0.9,en;q=0.8",
        "nl-NL,nl;q=0.9,en;q=0.8",
    ]

    # === Common Viewport Sizes ===
    # Mimics real desktop resolutions to avoid fingerprinting
    VIEWPORTS = [
        {"width": 1920, "height": 1080},  # Full HD - Most common
        {"width": 1366, "height": 768},   # HD - Laptops
        {"width": 1536, "height": 864},   # Common laptop
        {"width": 1440, "height": 900},   # MacBook
        {"width": 1680, "height": 1050},  # Larger desktop
        {"width": 2560, "height": 1440},  # QHD
    ]

    # === Platform Strings ===
    PLATFORMS = [
        "Win32",
        "MacIntel",
        "Linux x86_64",
    ]

    def __init__(self):
        """
        Initialize anti-detection with fake-useragent.

        fake-useragent fetches REAL User-Agent strings from browsers,
        making detection much harder than using static strings.
        """
        # Initialize User-Agent rotator
        # fallback ensures we always have a valid UA even if fetch fails
        try:
            self._ua = UserAgent(fallback="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                         "AppleWebKit/537.36 (KHTML, like Gecko) "
                                         "Chrome/120.0.0.0 Safari/537.36")
        except Exception:
            # Fallback if fake-useragent can't fetch data
            self._ua = None
            self._fallback_uas = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
            ]

        self._request_count = 0
        self._last_request_time: Optional[float] = None

    def get_random_user_agent(self) -> str:
        """
        Get a random, realistic User-Agent string.

        Uses fake-useragent library which maintains an updated list
        of REAL browser User-Agents, making detection harder.
        """
        if self._ua:
            # Get random UA from recent Chrome, Firefox, or Safari
            ua_type = random.choice(['chrome', 'firefox', 'safari', 'edge'])
            return getattr(self._ua, ua_type)
        else:
            return random.choice(self._fallback_uas)

    def get_browser_profile(self) -> BrowserProfile:
        """
        Generate a complete, consistent browser profile.

        Important: All attributes should be consistent with each other.
        E.g., a Windows User-Agent shouldn't have a MacIntel platform.
        """
        user_agent = self.get_random_user_agent()

        # Determine platform from User-Agent for consistency
        if "Windows" in user_agent:
            platform = "Win32"
        elif "Macintosh" in user_agent or "Mac OS" in user_agent:
            platform = "MacIntel"
        else:
            platform = "Linux x86_64"

        return BrowserProfile(
            user_agent=user_agent,
            viewport=random.choice(self.VIEWPORTS),
            timezone_id=random.choice(self.TIMEZONES),
            locale=random.choice(["fr-FR", "de-DE", "en-GB", "es-ES"]),
            accept_language=random.choice(self.ACCEPT_LANGUAGES),
            platform=platform,
        )

    def get_request_headers(self, profile: Optional[BrowserProfile] = None) -> Dict[str, str]:
        """
        Generate realistic HTTP headers for requests.

        These headers mimic a real browser to avoid detection.
        Headers are randomized to avoid pattern detection.
        """
        if not profile:
            profile = self.get_browser_profile()

        headers = {
            "User-Agent": profile.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": profile.accept_language,
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": random.choice(["1", "0"]),  # Do Not Track - randomized
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": random.choice(["none", "same-origin", "cross-site"]),
            "Sec-Fetch-User": "?1",
            "Cache-Control": random.choice(["max-age=0", "no-cache"]),
        }

        return headers

    async def random_delay(self, multiplier: float = 1.0) -> None:
        """
        Wait a random amount of time to mimic human behavior.

        CRITICAL for anti-detection:
        - Bots typically request pages at fixed intervals
        - Humans have variable timing between actions
        - Random delays make patterns harder to detect

        Args:
            multiplier: Scale factor for delay (2.0 = double the wait)
        """
        # Calculate random delay within configured bounds
        base_delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
        actual_delay = base_delay * multiplier

        # Add micro-variations to avoid round number patterns
        actual_delay += random.uniform(0.1, 0.5)

        # Log the delay for debugging
        # (commented to avoid console spam in production)
        # print(f"[AntiDetection] Waiting {actual_delay:.2f}s...")

        await asyncio.sleep(actual_delay)

    def sync_random_delay(self, multiplier: float = 1.0) -> None:
        """
        Synchronous version of random_delay for non-async code.
        """
        base_delay = random.uniform(settings.MIN_DELAY, settings.MAX_DELAY)
        actual_delay = base_delay * multiplier + random.uniform(0.1, 0.5)
        time.sleep(actual_delay)

    async def backoff_delay(self) -> None:
        """
        Longer delay when bot detection is suspected.

        Called when:
        - CAPTCHA is detected
        - Rate limiting response received
        - Multiple consecutive failures
        """
        backoff = settings.BACKOFF_DELAY + random.uniform(5, 15)
        print(f"[AntiDetection] Backoff triggered - waiting {backoff:.1f}s...")
        await asyncio.sleep(backoff)

    def get_playwright_context_options(self, profile: Optional[BrowserProfile] = None) -> Dict:
        """
        Get Playwright browser context options for anti-detection.

        These settings configure Playwright to look like a real browser:
        - Realistic viewport size
        - Proper timezone
        - Geolocation (approximate)
        - WebGL and Canvas fingerprint variations
        """
        if not profile:
            profile = self.get_browser_profile()

        return {
            "viewport": profile.viewport,
            "user_agent": profile.user_agent,
            "locale": profile.locale,
            "timezone_id": profile.timezone_id,
            # Disable automation detection flags
            "bypass_csp": True,
            # Add some randomness to geolocation (European coordinates)
            "geolocation": {
                "latitude": random.uniform(43.0, 52.0),   # Europe latitude range
                "longitude": random.uniform(-5.0, 15.0),  # Europe longitude range
            },
            "permissions": ["geolocation"],
        }

    def get_stealth_scripts(self) -> List[str]:
        """
        Return JavaScript snippets to inject for stealth mode.

        These scripts override browser APIs that sites use to detect automation:
        - navigator.webdriver (set by Selenium/Playwright)
        - navigator.plugins (empty in headless)
        - navigator.languages
        - And more fingerprinting vectors
        """
        return [
            # Override webdriver detection
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            """,

            # Fake plugins array (headless browsers have none)
            """
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' },
                ],
            });
            """,

            # Override permissions API
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            """,

            # Fake languages
            """
            Object.defineProperty(navigator, 'languages', {
                get: () => ['fr-FR', 'fr', 'en-US', 'en'],
            });
            """,

            # Hide automation in Chrome
            """
            window.chrome = {
                runtime: {},
            };
            """,
        ]

    def should_rotate_profile(self) -> bool:
        """
        Determine if browser profile should be rotated.

        Rotation strategy:
        - Every N requests
        - After detection/blocking
        - Randomly for unpredictability
        """
        self._request_count += 1

        # Rotate every 10-20 requests (randomized)
        rotation_threshold = random.randint(10, 20)
        if self._request_count >= rotation_threshold:
            self._request_count = 0
            return True

        # 5% chance of random rotation
        return random.random() < 0.05


# Global instance for convenience
anti_detection = AntiDetection()
