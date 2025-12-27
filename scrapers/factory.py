"""
Scraper Factory - Registry and Factory Pattern

This module provides:
1. A registry for all available scrapers
2. A factory to instantiate scrapers by name
3. Auto-discovery of scraper classes

DESIGN PATTERN: Factory Pattern
- Centralizes scraper instantiation
- Allows adding new scrapers without modifying existing code
- Enables configuration-based scraper selection

To add a new scraper:
1. Create the scraper class (e.g., scrapers/newegg.py)
2. Import it in scrapers/__init__.py
3. Register it: scraper_registry.register("newegg", NeweggScraper)
   OR use @register_scraper("newegg") decorator
"""

from typing import Dict, Type, Optional, List, Callable
from .base import BaseScraper


class ScraperRegistry:
    """
    Central registry for all scraper implementations.

    This allows:
    - Runtime discovery of available scrapers
    - Dynamic instantiation by name
    - Easy addition of new scrapers
    """

    def __init__(self):
        self._scrapers: Dict[str, Type[BaseScraper]] = {}

    def register(self, name: str, scraper_class: Type[BaseScraper]) -> None:
        """
        Register a scraper class with a given name.

        Args:
            name: Unique identifier for the scraper
            scraper_class: The scraper class (not instance)
        """
        if name in self._scrapers:
            raise ValueError(f"Scraper '{name}' is already registered")

        if not issubclass(scraper_class, BaseScraper):
            raise TypeError(f"{scraper_class} must be a subclass of BaseScraper")

        self._scrapers[name] = scraper_class

    def get(self, name: str) -> Optional[Type[BaseScraper]]:
        """
        Get a scraper class by name.

        Args:
            name: The scraper identifier

        Returns:
            The scraper class or None if not found
        """
        return self._scrapers.get(name)

    def create(self, name: str) -> Optional[BaseScraper]:
        """
        Create an instance of a scraper by name.

        Args:
            name: The scraper identifier

        Returns:
            A new scraper instance or None if not found
        """
        scraper_class = self.get(name)
        if scraper_class:
            return scraper_class()
        return None

    def list_available(self) -> List[str]:
        """
        List all registered scraper names.

        Returns:
            List of scraper identifiers
        """
        return list(self._scrapers.keys())

    def __contains__(self, name: str) -> bool:
        """Check if a scraper is registered."""
        return name in self._scrapers

    def __len__(self) -> int:
        """Return number of registered scrapers."""
        return len(self._scrapers)


# Global registry instance
scraper_registry = ScraperRegistry()


def register_scraper(name: str) -> Callable:
    """
    Decorator for registering scrapers.

    Usage:
    ```python
    @register_scraper("amazon_fr")
    class AmazonScraper(BaseScraper):
        ...
    ```
    """
    def decorator(cls: Type[BaseScraper]) -> Type[BaseScraper]:
        scraper_registry.register(name, cls)
        return cls
    return decorator


class ScraperFactory:
    """
    Factory for creating and managing scrapers.

    Provides high-level interface for the main engine.
    """

    def __init__(self, registry: ScraperRegistry = None):
        """
        Initialize factory with a registry.

        Args:
            registry: ScraperRegistry to use (defaults to global)
        """
        self.registry = registry or scraper_registry

    def create_scraper(self, name: str) -> Optional[BaseScraper]:
        """
        Create a scraper instance by name.

        Args:
            name: Scraper identifier

        Returns:
            Configured scraper instance or None
        """
        return self.registry.create(name)

    def create_all(self, names: List[str] = None) -> List[BaseScraper]:
        """
        Create instances of multiple scrapers.

        Args:
            names: List of scraper names (None = all available)

        Returns:
            List of scraper instances
        """
        if names is None:
            names = self.registry.list_available()

        scrapers = []
        for name in names:
            scraper = self.create_scraper(name)
            if scraper:
                scrapers.append(scraper)

        return scrapers

    def list_scrapers(self) -> Dict[str, str]:
        """
        List available scrapers with their display names.

        Returns:
            Dict of {identifier: display_name}
        """
        result = {}
        for name in self.registry.list_available():
            scraper = self.create_scraper(name)
            if scraper:
                result[name] = scraper.display_name
        return result


# === Register all built-in scrapers ===
# This is done at module import time

def _register_builtin_scrapers():
    """Register all built-in scraper implementations."""
    # Import here to avoid circular imports
    from .amazon import AmazonScraper
    from .ldlc import LDLCScraper

    scraper_registry.register("amazon_fr", AmazonScraper)
    scraper_registry.register("ldlc", LDLCScraper)

    # Add more scrapers here as they are developed:
    # scraper_registry.register("alternate", AlternateScraper)
    # scraper_registry.register("topachat", TopAchatScraper)
    # scraper_registry.register("materiel_net", MaterielNetScraper)


# Auto-register on import
_register_builtin_scrapers()
