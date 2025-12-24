"""
Módulo de Scrapers para ScrapAni
"""

from .intelligent_scraper import IntelligentMangaScraper
from .browser_scraper import BrowserScraper
from .flaresolverr import FlareSolverr, fetch_with_flaresolverr

__all__ = [
    "IntelligentMangaScraper",
    "BrowserScraper",
    "FlareSolverr",
    "fetch_with_flaresolverr",
]
