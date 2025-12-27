"""
Serper.dev API Integration

Uses Google Search API to find products across multiple retailers
based on their MPN (Manufacturer Part Number).

API Documentation: https://serper.dev/docs
"""

import os
import httpx
import asyncio
from dataclasses import dataclass
from typing import List, Optional, Dict
from urllib.parse import urlparse

from utils.logger import get_logger

logger = get_logger("serper")


# Supported retailers for discovery
SUPPORTED_RETAILERS = {
    "amazon.fr": "amazon",
    "www.amazon.fr": "amazon",
    "topachat.com": "topachat",
    "www.topachat.com": "topachat",
    "materiel.net": "materiel_net",
    "www.materiel.net": "materiel_net",
    "ldlc.com": "ldlc",
    "www.ldlc.com": "ldlc",
    "cdiscount.com": "cdiscount",
    "www.cdiscount.com": "cdiscount",
    "rueducommerce.fr": "rueducommerce",
    "www.rueducommerce.fr": "rueducommerce",
    "cybertek.fr": "cybertek",
    "www.cybertek.fr": "cybertek",
    "grosbill.com": "grosbill",
    "www.grosbill.com": "grosbill",
}


@dataclass
class SerperResult:
    """
    A single search result from Serper.
    """
    title: str
    url: str
    snippet: str
    retailer: str  # Normalized retailer name

    @classmethod
    def from_organic_result(cls, result: Dict) -> Optional['SerperResult']:
        """
        Create from Serper organic result.

        Args:
            result: Raw result from Serper API

        Returns:
            SerperResult or None if not a supported retailer
        """
        url = result.get("link", "")
        if not url:
            return None

        # Parse domain
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        # Check if supported retailer
        retailer = SUPPORTED_RETAILERS.get(domain)
        if not retailer:
            return None

        return cls(
            title=result.get("title", ""),
            url=url,
            snippet=result.get("snippet", ""),
            retailer=retailer
        )


class SerperAPI:
    """
    Client for the Serper.dev Google Search API.

    Usage:
        api = SerperAPI(api_key="your_key")
        results = await api.search_product("KF564S38IBK2-32")
    """

    BASE_URL = "https://google.serper.dev/search"

    # Target sites for Google dork query
    TARGET_SITES = [
        "amazon.fr",
        "topachat.com",
        "materiel.net",
        "cdiscount.com",
        "rueducommerce.fr",
        "cybertek.fr",
        "grosbill.com",
    ]

    def __init__(self, api_key: str = None):
        """
        Initialize Serper API client.

        Args:
            api_key: Serper.dev API key. If not provided, reads from SERPER_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("SERPER_API_KEY")

        if not self.api_key:
            logger.warning(
                "No Serper API key provided. Set SERPER_API_KEY env var or pass api_key parameter."
            )

    def _build_query(self, mpn: str, include_sites: List[str] = None) -> str:
        """
        Build an optimized Google dork query for MPN search.

        Args:
            mpn: Manufacturer Part Number
            include_sites: List of sites to search (None = all supported)

        Returns:
            Google dork query string
        """
        sites = include_sites or self.TARGET_SITES

        # Build site: OR chain
        site_query = " OR ".join([f"site:{site}" for site in sites])

        # Quote the MPN for exact match
        return f'"{mpn}" ({site_query})'

    async def search_product(
        self,
        mpn: str,
        num_results: int = 10,
        include_sites: List[str] = None,
    ) -> List[SerperResult]:
        """
        Search for a product by MPN across multiple retailers.

        Args:
            mpn: Manufacturer Part Number to search
            num_results: Maximum number of results
            include_sites: Limit search to specific sites

        Returns:
            List of SerperResult objects
        """
        if not self.api_key:
            logger.error("Cannot search: No API key configured")
            return []

        query = self._build_query(mpn, include_sites)
        logger.info(f"Searching for MPN: {mpn}")
        logger.debug(f"Query: {query}")

        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "q": query,
            "gl": "fr",  # France
            "hl": "fr",  # French language
            "num": num_results
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.BASE_URL,
                    headers=headers,
                    json=payload
                )

                if response.status_code != 200:
                    logger.error(f"Serper API error: {response.status_code} - {response.text}")
                    return []

                data = response.json()

                # Parse organic results
                results = []
                for item in data.get("organic", []):
                    result = SerperResult.from_organic_result(item)
                    if result:
                        results.append(result)
                        logger.debug(f"  Found: {result.retailer} - {result.url[:60]}...")

                logger.info(f"Found {len(results)} retailer results for {mpn}")
                return results

        except httpx.TimeoutException:
            logger.error(f"Serper API timeout for MPN: {mpn}")
            return []
        except Exception as e:
            logger.error(f"Serper API error: {e}")
            return []

    async def search_multiple(
        self,
        mpns: List[str],
        delay_between: float = 1.0,
    ) -> Dict[str, List[SerperResult]]:
        """
        Search for multiple MPNs with rate limiting.

        Args:
            mpns: List of MPNs to search
            delay_between: Delay between requests in seconds

        Returns:
            Dict mapping MPN to list of results
        """
        results = {}

        for i, mpn in enumerate(mpns):
            logger.info(f"[{i+1}/{len(mpns)}] Searching MPN: {mpn}")
            results[mpn] = await self.search_product(mpn)

            # Rate limiting
            if i < len(mpns) - 1:
                await asyncio.sleep(delay_between)

        return results

    def get_retailer_from_url(self, url: str) -> Optional[str]:
        """
        Extract retailer name from URL.

        Args:
            url: Product URL

        Returns:
            Normalized retailer name or None
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            return SUPPORTED_RETAILERS.get(domain)
        except Exception:
            return None


# Convenience function for quick searches
async def search_mpn(mpn: str, api_key: str = None) -> List[SerperResult]:
    """
    Quick search for a single MPN.

    Args:
        mpn: Manufacturer Part Number
        api_key: Optional API key

    Returns:
        List of SerperResult
    """
    api = SerperAPI(api_key=api_key)
    return await api.search_product(mpn)
