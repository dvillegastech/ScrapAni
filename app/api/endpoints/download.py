"""
Endpoint de Descarga

Permite descargar las imágenes de manga en diferentes formatos.
"""

import io
import zipfile
import httpx
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

from app.models.schemas import ScrapeRequest
from app.scrapers.intelligent_scraper import IntelligentMangaScraper

router = APIRouter()


class DownloadRequest(BaseModel):
    """Request para descarga"""
    url: str
    format: str = "zip"  # zip, json, urls
    filename_prefix: Optional[str] = "manga"


class ImageDownloadResult(BaseModel):
    """Resultado de descarga de imagen"""
    page_number: int
    url: str
    success: bool
    size_bytes: Optional[int] = None
    error: Optional[str] = None


@router.post(
    "/prepare",
    summary="Preparar descarga",
    description="""
    Prepara los datos para descarga sin descargar las imágenes.
    Retorna las URLs y metadatos necesarios para descarga manual.
    """,
)
async def prepare_download(request: DownloadRequest):
    """
    Prepara los datos para descarga.
    """
    try:
        scraper = IntelligentMangaScraper()
        result = await scraper.scrape(request.url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "Error al obtener el manga")
            )

        chapter = result.get("chapter")
        if not chapter or not chapter.pages:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron páginas para descargar"
            )

        return {
            "success": True,
            "title": chapter.title,
            "chapter_number": chapter.chapter_number,
            "total_pages": chapter.total_pages,
            "images": [
                {
                    "page": page.page_number,
                    "url": page.image_url,
                    "filename": f"{request.filename_prefix}_{page.page_number:03d}.jpg",
                }
                for page in chapter.pages
            ],
            "download_script": _generate_download_script(chapter.pages, request.filename_prefix),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


@router.post(
    "/zip",
    summary="Descargar como ZIP",
    description="Descarga todas las imágenes del capítulo en un archivo ZIP.",
)
async def download_as_zip(request: DownloadRequest):
    """
    Descarga las imágenes como un archivo ZIP.
    """
    try:
        scraper = IntelligentMangaScraper()
        result = await scraper.scrape(request.url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "Error al obtener el manga")
            )

        chapter = result.get("chapter")
        if not chapter or not chapter.pages:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron páginas para descargar"
            )

        # Crear ZIP en memoria
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            async with httpx.AsyncClient(timeout=30) as client:
                for page in chapter.pages:
                    try:
                        # Descargar imagen
                        response = await client.get(
                            page.image_url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                                "Referer": request.url,
                            }
                        )
                        response.raise_for_status()

                        # Determinar extensión
                        content_type = response.headers.get("content-type", "image/jpeg")
                        ext = _get_extension_from_content_type(content_type)

                        # Agregar al ZIP
                        filename = f"{request.filename_prefix}_{page.page_number:03d}{ext}"
                        zip_file.writestr(filename, response.content)

                    except Exception as e:
                        # Agregar archivo de error
                        zip_file.writestr(
                            f"error_page_{page.page_number}.txt",
                            f"Error descargando: {page.image_url}\n{str(e)}"
                        )

        zip_buffer.seek(0)

        # Nombre del archivo
        chapter_name = chapter.chapter_number or "chapter"
        zip_filename = f"{request.filename_prefix}_{chapter_name}.zip"

        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


@router.get(
    "/urls",
    summary="Obtener URLs de imágenes",
    description="Retorna solo las URLs de las imágenes en texto plano.",
)
async def get_image_urls(
    url: str = Query(..., description="URL del capítulo"),
):
    """
    Retorna las URLs de imágenes en texto plano (una por línea).
    """
    try:
        scraper = IntelligentMangaScraper()
        result = await scraper.scrape(url)

        if not result.get("success"):
            raise HTTPException(
                status_code=422,
                detail=result.get("error", "Error al obtener el manga")
            )

        chapter = result.get("chapter")
        if not chapter or not chapter.pages:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron páginas"
            )

        urls_text = "\n".join(page.image_url for page in chapter.pages)

        return StreamingResponse(
            io.StringIO(urls_text),
            media_type="text/plain",
            headers={
                "Content-Disposition": "attachment; filename=image_urls.txt"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error: {str(e)}"
        )


def _get_extension_from_content_type(content_type: str) -> str:
    """Obtiene la extensión de archivo según el content-type."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
    }
    return mapping.get(content_type.lower(), ".jpg")


def _generate_download_script(pages, prefix: str) -> str:
    """Genera un script bash para descargar las imágenes."""
    lines = ["#!/bin/bash", f"# Script para descargar {len(pages)} páginas", ""]

    for page in pages:
        filename = f"{prefix}_{page.page_number:03d}.jpg"
        lines.append(f'curl -o "{filename}" "{page.image_url}"')

    return "\n".join(lines)
