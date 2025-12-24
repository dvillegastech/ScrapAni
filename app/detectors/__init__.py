"""
Detectores de patrones para ScrapAni

Este módulo contiene detectores especializados para diferentes
patrones comunes en sitios de manga.
"""

from .image_detector import MangaImageDetector
from .navigation_detector import NavigationDetector
from .chapter_detector import ChapterListDetector

__all__ = [
    "MangaImageDetector",
    "NavigationDetector",
    "ChapterListDetector",
]
