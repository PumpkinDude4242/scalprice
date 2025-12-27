#!/usr/bin/env python3
"""
ScalPrice - RAM Price Scraper Engine

Main entry point for the scraping engine.
Orchestrates all scrapers and produces unified JSON output.

Usage:
    python main.py                    # Run all enabled scrapers
    python main.py --scrapers amazon_fr ldlc    # Run specific scrapers
    python main.py --list             # List available scrapers
    python main.py --help             # Show help

Output:
    Generates ram_prices_TIMESTAMP.json in the output directory
"""

import asyncio
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from config.settings import settings
from config.products import PRODUCT_URLS
from scrapers import ScraperFactory, scraper_registry
from utils.normalizer import NormalizedProduct
from utils.logger import setup_logger, get_logger


logger = get_logger("main")


async def run_scraper(scraper_name: str, urls: List[str]) -> List[NormalizedProduct]:
    """
    Run a single scraper for the given URLs.

    Args:
        scraper_name: Name of the scraper to run
        urls: List of product URLs to scrape

    Returns:
        List of scraped products
    """
    factory = ScraperFactory()
    scraper = factory.create_scraper(scraper_name)

    if not scraper:
        logger.error(f"Unknown scraper: {scraper_name}")
        return []

    logger.info(f"Starting {scraper.display_name} scraper with {len(urls)} URLs...")

    try:
        products = await scraper.scrape_all(urls)
        stats = scraper.get_stats()
        logger.info(
            f"{scraper.display_name} complete: "
            f"{stats['successful']}/{stats['total_urls']} successful"
        )
        return products
    except Exception as e:
        logger.error(f"Scraper {scraper_name} failed: {e}")
        return []


async def run_all_scrapers(
    scraper_names: Optional[List[str]] = None,
) -> List[NormalizedProduct]:
    """
    Run multiple scrapers and aggregate results.

    Args:
        scraper_names: List of scraper names (None = use settings.ENABLED_SCRAPERS)

    Returns:
        Combined list of all scraped products
    """
    if scraper_names is None:
        scraper_names = settings.ENABLED_SCRAPERS

    all_products: List[NormalizedProduct] = []

    for name in scraper_names:
        # Get URLs for this scraper
        urls = PRODUCT_URLS.get(name, [])
        if not urls:
            logger.warning(f"No URLs configured for scraper: {name}")
            continue

        # Run the scraper
        products = await run_scraper(name, urls)
        all_products.extend(products)

        # Small delay between scrapers
        if name != scraper_names[-1]:
            logger.debug("Delay between scrapers...")
            await asyncio.sleep(2)

    return all_products


def save_results(products: List[NormalizedProduct], output_path: Optional[Path] = None) -> Path:
    """
    Save scraped products to JSON file.

    Args:
        products: List of normalized products
        output_path: Custom output path (optional)

    Returns:
        Path to the saved file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{settings.OUTPUT_PREFIX}_{timestamp}.json"
        output_path = settings.OUTPUT_DIR / filename

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert products to dictionaries
    data = [product.to_dict() for product in products]

    # Write JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=settings.JSON_INDENT)

    logger.info(f"Results saved to: {output_path}")
    return output_path


def list_scrapers() -> None:
    """Print list of available scrapers."""
    factory = ScraperFactory()
    scrapers = factory.list_scrapers()

    print("\nAvailable Scrapers:")
    print("-" * 40)
    for name, display_name in scrapers.items():
        enabled = "✓" if name in settings.ENABLED_SCRAPERS else " "
        print(f"  [{enabled}] {name:15} - {display_name}")
    print()
    print("Enabled scrapers are marked with [✓]")
    print("Configure in config/settings.py or use --scrapers flag")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="ScalPrice - RAM Price Scraper Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                           Run all enabled scrapers
    python main.py --scrapers amazon_fr      Run only Amazon FR
    python main.py --scrapers amazon_fr ldlc Run Amazon and LDLC
    python main.py --list                    List available scrapers
    python main.py --headless false          Run with visible browser
        """
    )

    parser.add_argument(
        "--scrapers", "-s",
        nargs="+",
        help="Specific scrapers to run (space-separated)",
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List available scrapers and exit",
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
        setup_logger("scraper", level="DEBUG")

    # Handle --list
    if args.list:
        list_scrapers()
        return 0

    # Configure headless mode
    if args.headless:
        settings.HEADLESS = args.headless.lower() == "true"

    # Determine which scrapers to run
    scraper_names = args.scrapers if args.scrapers else settings.ENABLED_SCRAPERS

    # Validate scraper names
    for name in scraper_names:
        if name not in scraper_registry:
            logger.error(f"Unknown scraper: {name}")
            logger.info(f"Available scrapers: {scraper_registry.list_available()}")
            return 1

    logger.info("=" * 50)
    logger.info("ScalPrice - RAM Price Scraper Engine")
    logger.info("=" * 50)
    logger.info(f"Scrapers to run: {', '.join(scraper_names)}")
    logger.info(f"Headless mode: {settings.HEADLESS}")
    logger.info("")

    try:
        # Run scrapers
        products = await run_all_scrapers(scraper_names)

        if not products:
            logger.warning("No products were scraped!")
            return 1

        # Save results
        output_path = save_results(products, args.output)

        # Print summary
        logger.info("")
        logger.info("=" * 50)
        logger.info("SCRAPING COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Total products scraped: {len(products)}")
        logger.info(f"Output file: {output_path}")

        # Print price summary by source
        sources = {}
        for product in products:
            source = product.source_site
            if source not in sources:
                sources[source] = {"count": 0, "min_price": float('inf'), "max_price": 0}
            sources[source]["count"] += 1
            if product.prix_actuel > 0:
                sources[source]["min_price"] = min(sources[source]["min_price"], product.prix_actuel)
                sources[source]["max_price"] = max(sources[source]["max_price"], product.prix_actuel)

        logger.info("")
        logger.info("Summary by source:")
        for source, stats in sources.items():
            logger.info(
                f"  {source}: {stats['count']} products, "
                f"prices {stats['min_price']:.2f}€ - {stats['max_price']:.2f}€"
            )

        return 0

    except KeyboardInterrupt:
        logger.warning("Scraping interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
