#!/usr/bin/env python3
"""
MPN-based Hardware Price Comparator

Main ETL pipeline that:
1. Scrapes LDLC (master source) to discover products and extract MPNs
2. Uses Serper.dev API to find same products on other retailers
3. Dispatches scrapers to extract prices from discovered URLs
4. Aggregates data into MPN-keyed JSON with price trend tracking
5. Saves to output/data.json

Usage:
    python comparator.py                     # Full pipeline
    python comparator.py --ldlc-only         # Only scrape LDLC (no discovery)
    python comparator.py --skip-ldlc         # Only update competitor prices
    python comparator.py --max-products 10   # Limit products
    python comparator.py --verbose           # Debug logging
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from config.settings import settings
from config.products import RAM_SEARCH_QUERIES
from scrapers import ScraperFactory
from scrapers.ldlc import LDLCScraper
from scrapers.generic import GenericScraper, SITE_CONFIGS
from scrapers.amazon import AmazonScraper
from models.data_store import DataStore
from models.product import ProductInfo, Offer
from api.serper import SerperAPI, SerperResult
from utils.logger import setup_logger, get_logger

logger = get_logger("comparator")


class PriceComparator:
    """
    Main orchestrator for the MPN-based price comparison pipeline.

    Flow:
    1. Extract products from LDLC (master source) with MPNs
    2. For each MPN, search for competitor listings via Serper
    3. Scrape prices from discovered competitor URLs
    4. Store aggregated data with trend tracking
    """

    def __init__(
        self,
        data_path: Path = None,
        serper_api_key: str = None,
    ):
        """
        Initialize the comparator.

        Args:
            data_path: Path to store data.json
            serper_api_key: Optional Serper.dev API key
        """
        self.data_store = DataStore(data_path)
        self.serper = SerperAPI(api_key=serper_api_key)
        self.factory = ScraperFactory()

        # Track stats
        self.stats = {
            "ldlc_products": 0,
            "mpns_found": 0,
            "competitor_urls_discovered": 0,
            "competitor_prices_scraped": 0,
            "errors": 0,
        }

    async def run_full_pipeline(
        self,
        search_queries: List[str] = None,
        max_products: int = 20,
        skip_ldlc: bool = False,
        ldlc_only: bool = False,
    ) -> None:
        """
        Run the complete price comparison pipeline.

        Args:
            search_queries: Search queries for LDLC discovery
            max_products: Maximum products to process
            skip_ldlc: Skip LDLC scraping (use existing data)
            ldlc_only: Only scrape LDLC, skip competitor discovery
        """
        logger.info("=" * 60)
        logger.info("MPN-Based Hardware Price Comparator")
        logger.info("=" * 60)

        if search_queries is None:
            search_queries = RAM_SEARCH_QUERIES

        # Step 1: Scrape LDLC for products with MPNs
        if not skip_ldlc:
            await self._scrape_ldlc_products(search_queries, max_products)
        else:
            logger.info("Skipping LDLC scraping (using existing data)")

        if ldlc_only:
            logger.info("LDLC-only mode - skipping competitor discovery")
            self.data_store.save()
            self._print_summary()
            return

        # Step 2: Discover competitor URLs for each MPN
        mpns = self.data_store.get_all_mpns()
        if not mpns:
            logger.warning("No MPNs found - nothing to compare")
            return

        logger.info(f"\nDiscovering competitor prices for {len(mpns)} products...")

        # Step 3: For each MPN, find and scrape competitor prices
        for i, mpn in enumerate(mpns):
            logger.info(f"\n[{i+1}/{len(mpns)}] Processing MPN: {mpn}")
            await self._process_mpn(mpn)

            # Small delay between MPNs
            if i < len(mpns) - 1:
                await asyncio.sleep(1)

        # Step 4: Save final results
        self.data_store.save()
        self._print_summary()

    async def _scrape_ldlc_products(
        self,
        search_queries: List[str],
        max_products: int,
    ) -> None:
        """
        Scrape LDLC to discover products and extract MPNs.

        LDLC is the master source because:
        - Reliable product pages
        - Good MPN availability in product specs
        - Consistent page structure
        """
        logger.info("\n--- Phase 1: LDLC Product Discovery ---")
        logger.info(f"Search queries: {search_queries}")
        logger.info(f"Max products: {max_products}")

        scraper = LDLCScraper()

        try:
            # Discover product URLs via search
            await scraper.initialize()

            product_urls = []
            for query in search_queries:
                if len(product_urls) >= max_products:
                    break

                logger.info(f"Searching LDLC for: '{query}'")
                urls = await scraper.discover_products([query], max_products=max_products)

                for url in urls:
                    if url not in product_urls and len(product_urls) < max_products:
                        product_urls.append(url)

                await asyncio.sleep(1)  # Rate limiting

            logger.info(f"Discovered {len(product_urls)} LDLC product URLs")

            # Scrape each product for full data including MPN
            for i, url in enumerate(product_urls):
                logger.info(f"  [{i+1}/{len(product_urls)}] Scraping: {url[:60]}...")

                try:
                    if await scraper.navigate_to_url(url):
                        product_data = await scraper.extract_full_product_data(
                            scraper._page, url
                        )

                        if product_data and product_data.get("mpn"):
                            mpn = product_data["mpn"]

                            # Create ProductInfo
                            product_info = ProductInfo(
                                name=product_data.get("name", ""),
                                brand=product_data.get("brand", ""),
                                image_url=product_data.get("image_url", ""),
                            )

                            # Add to data store
                            self.data_store.add_or_update_product(
                                mpn=mpn,
                                retailer="ldlc",
                                price=product_data.get("price", 0),
                                url=url,
                                stock=product_data.get("stock", True),
                                product_info=product_info,
                            )

                            self.stats["mpns_found"] += 1
                            logger.info(f"    MPN: {mpn} | Price: {product_data.get('price', 0):.2f}€")
                        else:
                            logger.warning(f"    No MPN found - skipping")

                        self.stats["ldlc_products"] += 1

                except Exception as e:
                    logger.error(f"    Error scraping {url}: {e}")
                    self.stats["errors"] += 1

                # Rate limiting
                await asyncio.sleep(1.5)

        finally:
            await scraper.close()

        logger.info(f"\nLDLC Phase Complete: {self.stats['mpns_found']} products with MPNs")

    async def _process_mpn(self, mpn: str) -> None:
        """
        Find and scrape competitor prices for a single MPN.

        Args:
            mpn: Manufacturer Part Number to search for
        """
        # Search for this MPN across retailers
        results = await self.serper.search_product(mpn, num_results=10)

        if not results:
            logger.info(f"  No competitor listings found for {mpn}")
            return

        self.stats["competitor_urls_discovered"] += len(results)
        logger.info(f"  Found {len(results)} competitor listings")

        # Group by retailer
        by_retailer: Dict[str, List[SerperResult]] = {}
        for result in results:
            if result.retailer not in by_retailer:
                by_retailer[result.retailer] = []
            by_retailer[result.retailer].append(result)

        # Scrape each retailer (skip LDLC - already have it)
        for retailer, retailer_results in by_retailer.items():
            if retailer == "ldlc":
                continue  # Already have LDLC data

            # Take first (most relevant) result for this retailer
            result = retailer_results[0]
            await self._scrape_competitor_price(mpn, retailer, result.url)

    async def _scrape_competitor_price(
        self,
        mpn: str,
        retailer: str,
        url: str,
    ) -> None:
        """
        Scrape price from a competitor URL.

        Args:
            mpn: The MPN we're looking for
            retailer: Retailer name (amazon, topachat, etc.)
            url: Product URL to scrape
        """
        logger.info(f"    Scraping {retailer}: {url[:50]}...")

        try:
            scraper = self._get_scraper_for_retailer(retailer)
            if not scraper:
                logger.warning(f"    No scraper available for {retailer}")
                return

            await scraper.initialize()

            try:
                if await scraper.navigate_to_url(url):
                    # Extract product data
                    if hasattr(scraper, 'extract_full_product_data'):
                        product_data = await scraper.extract_full_product_data(
                            scraper._page, url
                        )
                    else:
                        # Fallback to basic extraction
                        price_str = await scraper.extract_price(scraper._page)
                        if price_str:
                            from utils.normalizer import PriceNormalizer
                            normalizer = PriceNormalizer()
                            price_val, _ = normalizer.normalize_price(price_str)
                            product_data = {
                                "price": price_val or 0,
                                "stock": await scraper.check_availability(scraper._page),
                            }
                        else:
                            product_data = None

                    if product_data and product_data.get("price", 0) > 0:
                        self.data_store.add_or_update_product(
                            mpn=mpn,
                            retailer=retailer,
                            price=product_data["price"],
                            url=url,
                            stock=product_data.get("stock", True),
                        )
                        self.stats["competitor_prices_scraped"] += 1
                        logger.info(f"      Price: {product_data['price']:.2f}€")
                    else:
                        logger.warning(f"      Could not extract price")

            finally:
                await scraper.close()

        except Exception as e:
            logger.error(f"      Error: {e}")
            self.stats["errors"] += 1

    def _get_scraper_for_retailer(self, retailer: str):
        """
        Get the appropriate scraper for a retailer.

        Args:
            retailer: Retailer name

        Returns:
            Scraper instance or None
        """
        if retailer == "amazon":
            return AmazonScraper()
        elif retailer in SITE_CONFIGS:
            return GenericScraper(site_name=retailer)
        else:
            # Try to create via factory
            return self.factory.create_scraper(retailer)

    def _print_summary(self) -> None:
        """Print final summary statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETE")
        logger.info("=" * 60)

        # Pipeline stats
        logger.info(f"LDLC products scraped: {self.stats['ldlc_products']}")
        logger.info(f"Products with MPNs: {self.stats['mpns_found']}")
        logger.info(f"Competitor URLs discovered: {self.stats['competitor_urls_discovered']}")
        logger.info(f"Competitor prices scraped: {self.stats['competitor_prices_scraped']}")
        logger.info(f"Errors: {self.stats['errors']}")

        # Data store stats
        store_stats = self.data_store.get_stats()
        logger.info(f"\nData Store:")
        logger.info(f"  Total products: {store_stats['total_products']}")
        logger.info(f"  Total offers: {store_stats['total_offers']}")
        logger.info(f"  Retailers: {', '.join(store_stats['retailers'])}")

        # Price trends
        trends = store_stats['price_trends']
        logger.info(f"\nPrice Trends:")
        logger.info(f"  ↑ Up: {trends.get('up', 0)}")
        logger.info(f"  ↓ Down: {trends.get('down', 0)}")
        logger.info(f"  → Stable: {trends.get('stable', 0)}")

        logger.info(f"\nData saved to: {self.data_store.data_path}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="MPN-based Hardware Price Comparator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python comparator.py                     Full pipeline
    python comparator.py --ldlc-only         Only scrape LDLC (master source)
    python comparator.py --skip-ldlc         Only update competitor prices
    python comparator.py --max-products 5    Limit to 5 products
    python comparator.py --verbose           Enable debug logging
        """
    )

    parser.add_argument(
        "--ldlc-only",
        action="store_true",
        help="Only scrape LDLC (skip competitor discovery)",
    )

    parser.add_argument(
        "--skip-ldlc",
        action="store_true",
        help="Skip LDLC scraping (use existing MPN data)",
    )

    parser.add_argument(
        "--max-products", "-m",
        type=int,
        default=20,
        help="Maximum products to process (default: 20)",
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Custom output file path",
    )

    parser.add_argument(
        "--headless",
        type=str,
        choices=["true", "false"],
        default="true",
        help="Run browser in headless mode (default: true)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose (debug) logging",
    )

    return parser.parse_args()


async def main() -> int:
    """
    Main entry point.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    args = parse_args()

    # Configure logging
    if args.verbose:
        settings.LOG_LEVEL = "DEBUG"
        setup_logger("comparator", level="DEBUG")
        setup_logger("scraper", level="DEBUG")
        setup_logger("serper", level="DEBUG")

    # Configure headless mode
    if args.headless:
        settings.HEADLESS = args.headless.lower() == "true"

    # Create comparator
    comparator = PriceComparator(data_path=args.output)

    try:
        await comparator.run_full_pipeline(
            max_products=args.max_products,
            skip_ldlc=args.skip_ldlc,
            ldlc_only=args.ldlc_only,
        )
        return 0

    except KeyboardInterrupt:
        logger.warning("Pipeline interrupted by user")
        # Save what we have
        comparator.data_store.save()
        return 1

    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run():
    """Entry point for the comparator."""
    import warnings
    warnings.filterwarnings("ignore", category=ResourceWarning)

    exit_code = asyncio.run(main())
    sys.exit(exit_code)


if __name__ == "__main__":
    run()
