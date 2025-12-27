"""
Data Store - Persistence Layer for MPN-based Product Data

Handles:
- Loading existing data from JSON
- Saving updated data to JSON
- Merging new scraped data with existing data
- Price trend calculations
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from .product import Product, Offer, ProductInfo, TrendInfo
from utils.logger import get_logger

logger = get_logger("data_store")


class DataStore:
    """
    Manages persistent storage of product data.

    Data is stored as a JSON file with MPN as the primary key.
    Supports incremental updates with price trend tracking.
    """

    def __init__(self, data_path: Path = None):
        """
        Initialize the data store.

        Args:
            data_path: Path to the JSON data file
        """
        if data_path is None:
            data_path = Path(__file__).parent.parent / "output" / "data.json"

        self.data_path = Path(data_path)
        self.products: Dict[str, Product] = {}
        self._load()

    def _load(self) -> None:
        """Load existing data from JSON file."""
        if not self.data_path.exists():
            logger.info(f"No existing data file at {self.data_path}")
            return

        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                raw_data = json.load(f)

            for mpn, product_data in raw_data.items():
                self.products[mpn] = Product.from_dict(mpn, product_data)

            logger.info(f"Loaded {len(self.products)} products from {self.data_path}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {self.data_path}: {e}")
        except Exception as e:
            logger.error(f"Error loading data: {e}")

    def save(self) -> None:
        """Save current data to JSON file."""
        # Ensure directory exists
        self.data_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to serializable dict
        data = {
            mpn: product.to_dict()
            for mpn, product in self.products.items()
        }

        # Write with backup
        backup_path = self.data_path.with_suffix('.json.bak')
        if self.data_path.exists():
            self.data_path.rename(backup_path)

        try:
            with open(self.data_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            logger.info(f"Saved {len(self.products)} products to {self.data_path}")

            # Remove backup on success
            if backup_path.exists():
                backup_path.unlink()

        except Exception as e:
            logger.error(f"Error saving data: {e}")
            # Restore backup
            if backup_path.exists():
                backup_path.rename(self.data_path)
            raise

    def get_product(self, mpn: str) -> Optional[Product]:
        """Get a product by its MPN."""
        return self.products.get(mpn)

    def add_or_update_product(
        self,
        mpn: str,
        retailer: str,
        price: float,
        url: str,
        stock: bool = True,
        product_info: ProductInfo = None,
    ) -> Product:
        """
        Add a new product or update an existing one.

        Automatically calculates price trends when updating.

        Args:
            mpn: Manufacturer Part Number
            retailer: Retailer name (e.g., "ldlc", "amazon")
            price: Current price
            url: Product URL on the retailer site
            stock: Is the product in stock?
            product_info: Product information (name, brand, etc.)

        Returns:
            The updated Product object
        """
        # Get or create product
        if mpn in self.products:
            product = self.products[mpn]
            # Update product info if provided and better
            if product_info and product_info.name:
                if not product.product_info.name or len(product_info.name) > len(product.product_info.name):
                    product.product_info = product_info
        else:
            if product_info is None:
                product_info = ProductInfo(name=f"Product {mpn}")
            product = Product(mpn=mpn, product_info=product_info)
            self.products[mpn] = product

        # Create new offer
        new_offer = Offer(
            price=price,
            currency="EUR",
            stock=stock,
            url=url,
            last_updated=datetime.utcnow().isoformat()
        )

        # Add with trend calculation
        product.add_offer(retailer, new_offer)

        return product

    def get_all_mpns(self) -> List[str]:
        """Get list of all known MPNs."""
        return list(self.products.keys())

    def get_products_by_retailer(self, retailer: str) -> List[Product]:
        """Get all products that have an offer from a specific retailer."""
        return [
            product for product in self.products.values()
            if retailer in product.offers
        ]

    def get_stats(self) -> Dict:
        """Get statistics about stored data."""
        total_products = len(self.products)
        retailers = set()
        total_offers = 0
        price_trends = {"up": 0, "down": 0, "stable": 0}

        for product in self.products.values():
            for retailer, offer in product.offers.items():
                retailers.add(retailer)
                total_offers += 1
                if offer.trend_info:
                    price_trends[offer.trend_info.trend] = price_trends.get(offer.trend_info.trend, 0) + 1

        return {
            "total_products": total_products,
            "total_offers": total_offers,
            "retailers": list(retailers),
            "price_trends": price_trends
        }

    def export_for_frontend(self) -> Dict:
        """
        Export data in a format optimized for frontend consumption.

        Returns dict with products and metadata.
        """
        return {
            "metadata": {
                "last_updated": datetime.utcnow().isoformat(),
                "stats": self.get_stats()
            },
            "products": {
                mpn: product.to_dict()
                for mpn, product in self.products.items()
            }
        }
