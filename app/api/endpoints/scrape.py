"""
Endpoint principal de Scraping

Este endpoint recibe una URL y extrae automáticamente el contenido de manga.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional

from app.models.schemas import (
    ScrapeRequest,
    ScrapeResponse,
    MangaChapter,
    MangaSeries,
    SiteAnalysis,
    ContentType,
)
from app.scrapers.intelligent_scraper import IntelligentMangaScraper

router = APIRouter()


@router.post(
    "/",
    response_model=ScrapeResponse,
    summary="Extraer manga de una URL",
    description="""
    Extrae automáticamente el contenido de manga de cualquier sitio web.

    El sistema detectará automáticamente si la URL corresponde a:
    - **Página de lectura**: Extrae todas las imágenes/páginas del capítulo
    - **Lista de capítulos**: Extrae la lista de capítulos disponibles
    - **Info de serie**: Extrae metadatos de la serie (título, sinopsis, etc.)

    ## Uso

    Simplemente envía la URL del manga y el sistema hará el resto:

    ```json
    {
        "url": "https://manga-site.com/manga/titulo/chapter-1"
    }
    ```

    ## Opciones

    - `use_browser`: Usar navegador real para sitios con JavaScript pesado
    - `extract_all_pages`: Extraer todas las páginas automáticamente
    """,
)
async def scrape_manga(request: ScrapeRequest):
    """
    Extrae manga de una URL de forma inteligente.
    """
    try:
        if request.use_browser:
            # Usar browser scraper para sitios con JS
            from app.scrapers.browser_scraper import BrowserScraper, PLAYWRIGHT_AVAILABLE

            if not PLAYWRIGHT_AVAILABLE:
                raise HTTPException(
                    status_code=503,
                    detail="El scraping con navegador no está disponible. Instala playwright: pip install playwright && playwright install chromium"
                )

            async with BrowserScraper() as scraper:
                result = await scraper.scrape(request.url)
        else:
            # Usar scraper básico
            scraper = IntelligentMangaScraper()
            result = await scraper.scrape(request.url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "Error desconocido durante el scraping")
            )

        return ScrapeResponse(
            success=True,
            url=request.url,
            analysis=result["analysis"],
            chapter=result.get("chapter"),
            series=result.get("series"),
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )


@router.get(
    "/quick",
    response_model=ScrapeResponse,
    summary="Scraping rápido por GET",
    description="Versión GET del endpoint de scraping para pruebas rápidas.",
)
async def quick_scrape(
    url: str = Query(..., description="URL del manga a scrapear"),
    use_browser: bool = Query(False, description="Usar navegador para JS"),
):
    """
    Scraping rápido usando GET (para pruebas).
    """
    request = ScrapeRequest(url=url, use_browser=use_browser)
    return await scrape_manga(request)


@router.post(
    "/chapter",
    response_model=MangaChapter,
    summary="Extraer solo el capítulo",
    description="Extrae únicamente las páginas/imágenes de un capítulo.",
)
async def scrape_chapter(request: ScrapeRequest):
    """
    Extrae solo las páginas de un capítulo.
    """
    try:
        scraper = IntelligentMangaScraper()
        result = await scraper.scrape(request.url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "No se pudo extraer el capítulo")
            )

        chapter = result.get("chapter")
        if not chapter:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron páginas de manga en esta URL"
            )

        return chapter

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )


@router.post(
    "/series",
    response_model=MangaSeries,
    summary="Extraer info de serie",
    description="Extrae la información y lista de capítulos de una serie.",
)
async def scrape_series(request: ScrapeRequest):
    """
    Extrae información de una serie de manga.
    """
    try:
        scraper = IntelligentMangaScraper()
        result = await scraper.scrape(request.url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "No se pudo extraer la información")
            )

        series = result.get("series")
        if not series:
            raise HTTPException(
                status_code=404,
                detail="No se encontró información de serie en esta URL"
            )

        return series

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )


@router.post(
    "/images",
    summary="Extraer solo URLs de imágenes",
    description="Extrae únicamente las URLs de las imágenes del manga.",
    response_model=dict,
)
async def scrape_images_only(request: ScrapeRequest):
    """
    Extrae solo las URLs de imágenes.
    """
    try:
        scraper = IntelligentMangaScraper()
        result = await scraper.scrape(request.url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "No se pudieron extraer las imágenes")
            )

        chapter = result.get("chapter")
        if not chapter or not chapter.pages:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron imágenes de manga en esta URL"
            )

        return {
            "success": True,
            "url": request.url,
            "total_images": len(chapter.pages),
            "images": [page.image_url for page in chapter.pages],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )
