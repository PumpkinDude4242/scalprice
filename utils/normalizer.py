"""
Data Normalizer Module

Handles cleaning and standardization of scraped data:
- Price normalization (various formats to float)
- Currency extraction and standardization
- Product name cleaning
- RAM type and capacity extraction
"""

import re
import hashlib
from typing import Optional, Tuple, Dict, Any
from datetime import datetime, timezone
from dataclasses import dataclass, asdict


@dataclass
class NormalizedProduct:
    """
    Standardized product data structure.

    This is the FINAL format that all scrapers must produce,
    regardless of source site format.
    """
    id_unique: str
    nom_produit: str
    type_ram: str
    capacite: str
    prix_actuel: float
    devise: str
    source_site: str
    url_produit: str
    url_image: str
    timestamp_scan: str
    disponible: bool

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class DataNormalizer:
    """
    Normalizes scraped data into consistent format.

    Handles various price formats:
    - "145,99 €" (French)
    - "145.99€" (International)
    - "EUR 145,99" (Prefix)
    - "145.99 EUR" (Suffix)
    """

    # === Currency Patterns ===
    CURRENCY_SYMBOLS = {
        "€": "EUR",
        "EUR": "EUR",
        "£": "GBP",
        "GBP": "GBP",
        "$": "USD",
        "USD": "USD",
        "CHF": "CHF",
    }

    # === Price Extraction Patterns ===
    # Matches prices in various European formats
    PRICE_PATTERNS = [
        # 145,99 € or 145,99€
        r"([\d\s]+[,.][\d]{2})\s*€",
        # € 145,99 or €145,99
        r"€\s*([\d\s]+[,.][\d]{2})",
        # 145.99 EUR or 145,99 EUR
        r"([\d\s]+[,.][\d]{2})\s*EUR",
        # EUR 145.99
        r"EUR\s*([\d\s]+[,.][\d]{2})",
        # Plain number with comma decimal (French)
        r"([\d\s]+,[\d]{2})(?!\d)",
        # Plain number with period decimal (International)
        r"([\d\s]+\.[\d]{2})(?!\d)",
    ]

    # === RAM Type Detection ===
    RAM_TYPE_PATTERNS = {
        "DDR5": [r"DDR[\s-]?5", r"DDR5"],
        "DDR4": [r"DDR[\s-]?4", r"DDR4"],
        "DDR3": [r"DDR[\s-]?3", r"DDR3"],
    }

    # === Capacity Detection ===
    CAPACITY_PATTERNS = [
        # 32 Go, 32Go, 32 GB, 32GB
        r"(\d+)\s*(?:Go|GB|Gio)",
        # 2x16 Go format (kit)
        r"(\d+)\s*x\s*(\d+)\s*(?:Go|GB)",
        # "32G" shorthand
        r"(\d+)\s*G(?:\s|$)",
    ]

    def normalize_price(self, price_str: str) -> Tuple[Optional[float], str]:
        """
        Extract and normalize price from various formats.

        Args:
            price_str: Raw price string from website

        Returns:
            Tuple of (price_float, currency_code)
            Returns (None, "EUR") if parsing fails
        """
        if not price_str:
            return None, "EUR"

        # Clean the input
        price_str = price_str.strip()

        # Detect currency
        currency = "EUR"  # Default for European sites
        for symbol, code in self.CURRENCY_SYMBOLS.items():
            if symbol in price_str:
                currency = code
                break

        # Try each pattern to extract price
        for pattern in self.PRICE_PATTERNS:
            match = re.search(pattern, price_str, re.IGNORECASE)
            if match:
                price_raw = match.group(1)
                # Clean and convert to float
                price_float = self._convert_price_string(price_raw)
                if price_float is not None:
                    return price_float, currency

        # Fallback: try to find any number
        numbers = re.findall(r"[\d\s]+[,.]?[\d]*", price_str)
        for num in numbers:
            price_float = self._convert_price_string(num)
            if price_float and price_float > 10:  # RAM prices are > 10€
                return price_float, currency

        return None, currency

    def _convert_price_string(self, price_str: str) -> Optional[float]:
        """
        Convert a price string to float.

        Handles:
        - French format: "1 234,56" -> 1234.56
        - International: "1,234.56" -> 1234.56
        - Simple: "1234.56" or "1234,56"
        """
        if not price_str:
            return None

        # Remove spaces (thousand separators in French)
        price_str = price_str.replace(" ", "").replace("\u00a0", "")

        # Determine decimal separator
        # If both comma and period exist, the last one is decimal
        has_comma = "," in price_str
        has_period = "." in price_str

        if has_comma and has_period:
            # Format like "1.234,56" (European) or "1,234.56" (US)
            comma_pos = price_str.rfind(",")
            period_pos = price_str.rfind(".")
            if comma_pos > period_pos:
                # European: comma is decimal (1.234,56)
                price_str = price_str.replace(".", "").replace(",", ".")
            else:
                # US: period is decimal (1,234.56)
                price_str = price_str.replace(",", "")
        elif has_comma:
            # French format: "1234,56"
            price_str = price_str.replace(",", ".")
        # else: already in float format or integer

        try:
            return float(price_str)
        except ValueError:
            return None

    def detect_ram_type(self, text: str) -> str:
        """
        Detect RAM type (DDR3/DDR4/DDR5) from product text.

        Args:
            text: Product name or description

        Returns:
            "DDR5", "DDR4", "DDR3", or "Unknown"
        """
        text_upper = text.upper()

        for ram_type, patterns in self.RAM_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text_upper):
                    return ram_type

        return "Unknown"

    def detect_capacity(self, text: str) -> str:
        """
        Extract RAM capacity from product text.

        Handles:
        - "32 Go" -> "32Go"
        - "2x16 GB" -> "32Go" (calculates total)
        - "64GB Kit" -> "64Go"

        Returns:
            Normalized capacity string (e.g., "32Go") or "Unknown"
        """
        text_upper = text.upper()

        for pattern in self.CAPACITY_PATTERNS:
            match = re.search(pattern, text_upper, re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 2:
                    # Kit format: 2x16 = 32
                    try:
                        total = int(groups[0]) * int(groups[1])
                        return f"{total}Go"
                    except ValueError:
                        pass
                elif len(groups) == 1:
                    try:
                        return f"{int(groups[0])}Go"
                    except ValueError:
                        pass

        return "Unknown"

    def clean_product_name(self, name: str) -> str:
        """
        Clean and standardize product name.

        Removes:
        - Extra whitespace
        - Special characters
        - Marketing fluff
        """
        if not name:
            return "Unknown Product"

        # Remove extra whitespace
        name = " ".join(name.split())

        # Remove common marketing terms
        remove_terms = [
            r"\[.*?\]",           # [Exclusive] etc.
            r"\(.*?offre.*?\)",   # (offre spéciale)
            r"- livraison.*",     # shipping info
            r"★.*$",              # Star ratings
        ]

        for pattern in remove_terms:
            name = re.sub(pattern, "", name, flags=re.IGNORECASE)

        return name.strip()

    def generate_unique_id(self, url: str) -> str:
        """
        Generate a unique, deterministic ID from product URL.

        Uses SHA256 hash truncated to 12 chars for readability.
        Same URL always produces same ID (for deduplication).
        """
        return hashlib.sha256(url.encode()).hexdigest()[:12]

    def get_current_timestamp(self) -> str:
        """
        Get current UTC timestamp in ISO 8601 format.
        """
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def normalize_product(
        self,
        raw_name: str,
        raw_price: str,
        url: str,
        image_url: str,
        source_site: str,
        available: bool = True,
    ) -> NormalizedProduct:
        """
        Main normalization function - converts raw scraped data to standard format.

        Args:
            raw_name: Product name as scraped
            raw_price: Price string as scraped
            url: Product URL
            image_url: Product image URL
            source_site: Source site name (e.g., "Amazon FR")
            available: Product availability

        Returns:
            NormalizedProduct with all fields standardized
        """
        # Clean product name
        clean_name = self.clean_product_name(raw_name)

        # Extract price and currency
        price, currency = self.normalize_price(raw_price)

        # Detect RAM type and capacity
        combined_text = f"{raw_name} {raw_price}"
        ram_type = self.detect_ram_type(combined_text)
        capacity = self.detect_capacity(combined_text)

        return NormalizedProduct(
            id_unique=self.generate_unique_id(url),
            nom_produit=clean_name,
            type_ram=ram_type,
            capacite=capacity,
            prix_actuel=price if price else 0.0,
            devise=currency,
            source_site=source_site,
            url_produit=url,
            url_image=image_url or "",
            timestamp_scan=self.get_current_timestamp(),
            disponible=available if price else False,
        )


# Global instance
normalizer = DataNormalizer()
