"""
API Routes para ScrapAni
"""

from fastapi import APIRouter
from .endpoints import scrape, analyze, download

router = APIRouter()

router.include_router(scrape.router, prefix="/scrape", tags=["Scraping"])
router.include_router(analyze.router, prefix="/analyze", tags=["Análisis"])
router.include_router(download.router, prefix="/download", tags=["Descarga"])
