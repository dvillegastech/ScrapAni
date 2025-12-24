"""
Módulo de Scrapers para ScrapAni
"""

from .intelligent_scraper import IntelligentMangaScraper
from .browser_scraper import BrowserScraper

__all__ = [
    "IntelligentMangaScraper",
    "BrowserScraper",
]
