"""
Endpoint de Análisis

Analiza una URL y determina qué tipo de contenido contiene,
sin extraer todo el contenido.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional

from app.models.schemas import SiteAnalysis, ContentType
from app.scrapers.intelligent_scraper import IntelligentMangaScraper

router = APIRouter()


class AnalyzeRequest(BaseModel):
    """Request para análisis"""
    url: str


class DetailedAnalysis(BaseModel):
    """Análisis detallado de una página"""
    site_analysis: SiteAnalysis
    image_count: int
    potential_manga_images: int
    chapter_links_found: int
    has_navigation: bool
    page_title: Optional[str]
    recommendations: List[str]


@router.post(
    "/",
    response_model=DetailedAnalysis,
    summary="Analizar una URL",
    description="""
    Analiza una URL para determinar:
    - Tipo de contenido (página de lectura, lista de capítulos, info de serie)
    - Cantidad de imágenes potenciales de manga
    - Si requiere JavaScript para funcionar
    - Recomendaciones de scraping
    """,
)
async def analyze_url(request: AnalyzeRequest):
    """
    Analiza una URL sin extraer todo el contenido.
    """
    try:
        scraper = IntelligentMangaScraper()

        # Obtener página
        html = scraper._fetch_page(request.url)
        if not html:
            raise HTTPException(
                status_code=422,
                detail="No se pudo acceder a la URL"
            )

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        # Análisis básico
        analysis = scraper._analyze_content_type(soup, request.url)

        # Conteos
        all_images = soup.find_all('img')
        manga_candidates = scraper._find_manga_image_candidates(soup, request.url)
        chapter_links = scraper._find_chapter_links(soup, request.url)
        navigation = scraper._extract_navigation(soup, request.url)

        # Título de la página
        title_tag = soup.find('title')
        page_title = title_tag.get_text().strip() if title_tag else None

        # Generar recomendaciones
        recommendations = []

        if analysis.requires_javascript:
            recommendations.append("Usar use_browser=true para mejor extracción")

        if analysis.detected_type == ContentType.MANGA_PAGE:
            if len(manga_candidates) < 5:
                recommendations.append("Pocas imágenes detectadas, el contenido podría cargarse por JavaScript")
            else:
                recommendations.append(f"Se detectaron {len(manga_candidates)} páginas de manga")

        if analysis.detected_type == ContentType.CHAPTER_LIST:
            recommendations.append(f"Lista de capítulos con {len(chapter_links)} capítulos")

        if analysis.confidence < 0.5:
            recommendations.append("Baja confianza en la detección, considerar verificar manualmente")

        if not navigation.next_chapter and not navigation.prev_chapter:
            if analysis.detected_type == ContentType.MANGA_PAGE:
                recommendations.append("No se detectó navegación entre capítulos")

        return DetailedAnalysis(
            site_analysis=analysis,
            image_count=len(all_images),
            potential_manga_images=len(manga_candidates),
            chapter_links_found=len(chapter_links),
            has_navigation=bool(navigation.next_chapter or navigation.prev_chapter),
            page_title=page_title,
            recommendations=recommendations,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error durante el análisis: {str(e)}"
        )


@router.get(
    "/quick",
    response_model=SiteAnalysis,
    summary="Análisis rápido",
    description="Análisis rápido de una URL por GET.",
)
async def quick_analyze(
    url: str = Query(..., description="URL a analizar"),
):
    """
    Análisis rápido usando GET.
    """
    result = await analyze_url(AnalyzeRequest(url=url))
    return result.site_analysis


@router.post(
    "/detect-type",
    summary="Detectar tipo de contenido",
    description="Solo detecta el tipo de contenido de la URL.",
)
async def detect_content_type(request: AnalyzeRequest):
    """
    Detecta únicamente el tipo de contenido.
    """
    try:
        scraper = IntelligentMangaScraper()

        html = scraper._fetch_page(request.url)
        if not html:
            raise HTTPException(status_code=422, detail="No se pudo acceder a la URL")

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'lxml')

        analysis = scraper._analyze_content_type(soup, request.url)

        return {
            "url": request.url,
            "detected_type": analysis.detected_type.value,
            "confidence": analysis.confidence,
            "requires_javascript": analysis.requires_javascript,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )
