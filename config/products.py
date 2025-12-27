"""
Product URLs and search queries configuration.
Add or modify targets here without touching scraper code.
"""

# === Direct Product URLs ===
# These URLs will be scraped directly for price extraction
PRODUCT_URLS = {
    "amazon_fr": [
        # Corsair Vengeance DDR5
        "https://www.amazon.fr/dp/B09PHJG4ML",
        "https://www.amazon.fr/dp/B09PHLTQBV",
        # Kingston Fury DDR5
        "https://www.amazon.fr/dp/B09NQGY5YH",
        # G.Skill Trident Z5 DDR5
        "https://www.amazon.fr/dp/B09PTJC2NJ",
        # Crucial DDR5
        "https://www.amazon.fr/dp/B09MTKWYM7",
    ],
    "ldlc": [
        # Corsair Vengeance DDR5
        "https://www.ldlc.com/fiche/PB00503891.html",
        # Kingston Fury DDR5
        "https://www.ldlc.com/fiche/PB00508821.html",
        # G.Skill DDR5
        "https://www.ldlc.com/fiche/PB00525547.html",
        # Crucial DDR5
        "https://www.ldlc.com/fiche/PB00497041.html",
    ],
    "alternate": [
        # Corsair Vengeance DDR5
        "https://www.alternate.fr/Corsair/Vengeance-DDR5-5600-MHz-32-Go-2x-16-Go-m%C3%A9moire-vive/html/product/1825050",
    ],
}

# === Search Queries ===
# For scrapers that support search-based extraction
RAM_SEARCH_QUERIES = [
    # DDR5 Kits
    "DDR5 32Go kit",
    "DDR5 64Go kit",
    "DDR5 5600MHz 32Go",
    "DDR5 6000MHz 32Go",
    # DDR4 Kits (still popular)
    "DDR4 32Go 3200MHz",
    "DDR4 64Go kit",
    # Popular brands
    "Corsair Vengeance DDR5",
    "Kingston Fury Beast DDR5",
    "G.Skill Trident Z5",
    "Crucial DDR5",
    "TeamGroup T-Force DDR5",
]

# === RAM Type Patterns ===
# Used for classification and normalization
RAM_TYPE_PATTERNS = {
    "DDR5": [
        r"DDR5",
        r"DDR\s*5",
    ],
    "DDR4": [
        r"DDR4",
        r"DDR\s*4",
    ],
    "DDR3": [
        r"DDR3",
        r"DDR\s*3",
    ],
}

# === Capacity Patterns ===
# Regex patterns for extracting RAM capacity
CAPACITY_PATTERNS = [
    r"(\d+)\s*Go",
    r"(\d+)\s*GB",
    r"(\d+)\s*Gio",
    r"(\d+)Go",
    r"(\d+)GB",
]
