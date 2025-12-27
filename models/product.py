"""
Data Models for MPN-based Price Comparator

These models define the structure of our data:
- Product: A unique product identified by MPN
- Offer: A price offer from a specific retailer
- TrendInfo: Price trend information (up/down/stable)
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Optional, Any
from enum import Enum


class PriceTrend(Enum):
    """Price trend direction."""
    UP = "up"       # Price increased (red)
    DOWN = "down"   # Price decreased (green)
    STABLE = "stable"  # Price unchanged (gray)


@dataclass
class TrendInfo:
    """
    Price trend information for a specific offer.
    """
    trend: str = "stable"  # "up", "down", "stable"
    previous_price: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trend": self.trend,
            "previous_price": self.previous_price
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TrendInfo':
        return cls(
            trend=data.get("trend", "stable"),
            previous_price=data.get("previous_price")
        )

    @classmethod
    def calculate(cls, current_price: float, previous_price: Optional[float]) -> 'TrendInfo':
        """
        Calculate trend based on price comparison.

        Args:
            current_price: Current product price
            previous_price: Previous product price (if any)

        Returns:
            TrendInfo with calculated trend
        """
        if previous_price is None:
            return cls(trend="stable", previous_price=None)

        if current_price > previous_price:
            return cls(trend="up", previous_price=previous_price)
        elif current_price < previous_price:
            return cls(trend="down", previous_price=previous_price)
        else:
            return cls(trend="stable", previous_price=previous_price)


@dataclass
class Offer:
    """
    A price offer from a specific retailer.
    """
    price: float
    currency: str = "EUR"
    stock: bool = True
    url: str = ""
    last_updated: str = ""
    trend_info: Optional[TrendInfo] = None

    def __post_init__(self):
        if not self.last_updated:
            self.last_updated = datetime.utcnow().isoformat()
        if self.trend_info is None:
            self.trend_info = TrendInfo()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": self.price,
            "currency": self.currency,
            "stock": self.stock,
            "url": self.url,
            "last_updated": self.last_updated,
            "trend_info": self.trend_info.to_dict() if self.trend_info else None
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Offer':
        trend_data = data.get("trend_info")
        trend_info = TrendInfo.from_dict(trend_data) if trend_data else None

        return cls(
            price=data.get("price", 0.0),
            currency=data.get("currency", "EUR"),
            stock=data.get("stock", True),
            url=data.get("url", ""),
            last_updated=data.get("last_updated", ""),
            trend_info=trend_info
        )

    def update_with_trend(self, new_price: float) -> 'Offer':
        """
        Create a new Offer with updated price and calculated trend.

        Args:
            new_price: The new price to set

        Returns:
            New Offer instance with trend calculated
        """
        trend_info = TrendInfo.calculate(new_price, self.price)

        return Offer(
            price=new_price,
            currency=self.currency,
            stock=self.stock,
            url=self.url,
            last_updated=datetime.utcnow().isoformat(),
            trend_info=trend_info
        )


@dataclass
class ProductInfo:
    """
    Basic product information (shared across all offers).
    """
    name: str
    brand: str = ""
    image_url: str = ""
    category: str = ""
    specifications: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "brand": self.brand,
            "image_url": self.image_url,
            "category": self.category,
            "specifications": self.specifications
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProductInfo':
        return cls(
            name=data.get("name", ""),
            brand=data.get("brand", ""),
            image_url=data.get("image_url", ""),
            category=data.get("category", ""),
            specifications=data.get("specifications", {})
        )


@dataclass
class Product:
    """
    A product identified by its MPN (Manufacturer Part Number).

    This is the main entity that groups offers from different retailers.
    """
    mpn: str  # Manufacturer Part Number - the unique key
    product_info: ProductInfo
    offers: Dict[str, Offer] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "product_info": self.product_info.to_dict(),
            "offers": {
                retailer: offer.to_dict()
                for retailer, offer in self.offers.items()
            }
        }

    @classmethod
    def from_dict(cls, mpn: str, data: Dict) -> 'Product':
        product_info = ProductInfo.from_dict(data.get("product_info", {}))
        offers = {
            retailer: Offer.from_dict(offer_data)
            for retailer, offer_data in data.get("offers", {}).items()
        }

        return cls(
            mpn=mpn,
            product_info=product_info,
            offers=offers
        )

    def add_offer(self, retailer: str, offer: Offer) -> None:
        """
        Add or update an offer from a retailer.

        If an offer already exists, calculates the trend.

        Args:
            retailer: Retailer name (e.g., "ldlc", "amazon", "topachat")
            offer: The new offer
        """
        if retailer in self.offers:
            # Update with trend calculation
            existing_offer = self.offers[retailer]
            offer = existing_offer.update_with_trend(offer.price)
            offer.url = offer.url or existing_offer.url
            offer.stock = offer.stock

        self.offers[retailer] = offer

    def get_best_price(self) -> Optional[tuple]:
        """
        Get the best (lowest) price across all retailers.

        Returns:
            Tuple of (retailer, price) or None if no offers
        """
        if not self.offers:
            return None

        available_offers = [
            (retailer, offer.price)
            for retailer, offer in self.offers.items()
            if offer.stock and offer.price > 0
        ]

        if not available_offers:
            return None

        return min(available_offers, key=lambda x: x[1])

    def get_price_range(self) -> Optional[tuple]:
        """
        Get min and max prices across all retailers.

        Returns:
            Tuple of (min_price, max_price) or None
        """
        prices = [
            offer.price for offer in self.offers.values()
            if offer.price > 0
        ]

        if not prices:
            return None

        return (min(prices), max(prices))
