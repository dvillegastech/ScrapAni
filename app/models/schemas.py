"""
Esquemas Pydantic para la API
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, HttpUrl, Field
from enum import Enum


class ContentType(str, Enum):
    """Tipo de contenido detectado"""
    MANGA_PAGE = "manga_page"      # Página individual de lectura
    CHAPTER_LIST = "chapter_list"  # Lista de capítulos
    SERIES_INFO = "series_info"    # Información de la serie
    UNKNOWN = "unknown"


class ScrapeRequest(BaseModel):
    """Request para scraping"""
    url: str = Field(..., description="URL del sitio de manga a scrapear")
    use_browser: bool = Field(
        default=False,
        description="Usar navegador para sitios con JavaScript pesado"
    )
    extract_all_pages: bool = Field(
        default=True,
        description="Extraer todas las páginas del capítulo automáticamente"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://ejemplo-manga.com/manga/one-piece/chapter-1",
                "use_browser": False,
                "extract_all_pages": True
            }
        }


class ImageInfo(BaseModel):
    """Información de una imagen"""
    url: str = Field(..., description="URL de la imagen")
    width: Optional[int] = Field(None, description="Ancho de la imagen")
    height: Optional[int] = Field(None, description="Alto de la imagen")
    page_number: Optional[int] = Field(None, description="Número de página")
    alt_text: Optional[str] = Field(None, description="Texto alternativo")


class MangaPage(BaseModel):
    """Página de manga extraída"""
    page_number: int = Field(..., description="Número de página")
    image_url: str = Field(..., description="URL de la imagen")
    image_urls_backup: List[str] = Field(
        default_factory=list,
        description="URLs alternativas de la imagen"
    )


class NavigationInfo(BaseModel):
    """Información de navegación"""
    next_chapter: Optional[str] = Field(None, description="URL del siguiente capítulo")
    prev_chapter: Optional[str] = Field(None, description="URL del capítulo anterior")
    chapter_list: Optional[str] = Field(None, description="URL de la lista de capítulos")


class MangaChapter(BaseModel):
    """Capítulo de manga"""
    title: Optional[str] = Field(None, description="Título del capítulo")
    chapter_number: Optional[str] = Field(None, description="Número del capítulo")
    pages: List[MangaPage] = Field(default_factory=list, description="Páginas del capítulo")
    total_pages: int = Field(0, description="Total de páginas")
    navigation: Optional[NavigationInfo] = Field(None, description="Navegación")


class ChapterInfo(BaseModel):
    """Info de un capítulo en lista"""
    title: str = Field(..., description="Título del capítulo")
    url: str = Field(..., description="URL del capítulo")
    chapter_number: Optional[str] = Field(None, description="Número")
    date: Optional[str] = Field(None, description="Fecha de publicación")


class MangaSeries(BaseModel):
    """Serie de manga completa"""
    title: Optional[str] = Field(None, description="Título de la serie")
    alternative_titles: List[str] = Field(default_factory=list, description="Títulos alternativos")
    description: Optional[str] = Field(None, description="Descripción/sinopsis")
    cover_image: Optional[str] = Field(None, description="URL de la portada")
    author: Optional[str] = Field(None, description="Autor")
    artist: Optional[str] = Field(None, description="Artista")
    genres: List[str] = Field(default_factory=list, description="Géneros")
    status: Optional[str] = Field(None, description="Estado (ongoing, completed, etc)")
    chapters: List[ChapterInfo] = Field(default_factory=list, description="Lista de capítulos")
    total_chapters: int = Field(0, description="Total de capítulos")


class SiteAnalysis(BaseModel):
    """Análisis del sitio"""
    detected_type: ContentType = Field(..., description="Tipo de contenido detectado")
    confidence: float = Field(..., description="Confianza de la detección (0-1)")
    site_domain: str = Field(..., description="Dominio del sitio")
    detected_patterns: List[str] = Field(
        default_factory=list,
        description="Patrones detectados"
    )
    requires_javascript: bool = Field(
        False,
        description="Si el sitio requiere JavaScript"
    )


class ScrapeResponse(BaseModel):
    """Respuesta del scraping"""
    success: bool = Field(..., description="Si el scraping fue exitoso")
    url: str = Field(..., description="URL original")
    analysis: SiteAnalysis = Field(..., description="Análisis del sitio")
    chapter: Optional[MangaChapter] = Field(None, description="Datos del capítulo si es página de lectura")
    series: Optional[MangaSeries] = Field(None, description="Datos de la serie si es página de info")
    error: Optional[str] = Field(None, description="Mensaje de error si falló")
    raw_data: Optional[Dict[str, Any]] = Field(None, description="Datos crudos adicionales")

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "url": "https://ejemplo-manga.com/manga/one-piece/chapter-1",
                "analysis": {
                    "detected_type": "manga_page",
                    "confidence": 0.95,
                    "site_domain": "ejemplo-manga.com",
                    "detected_patterns": ["image_sequence", "chapter_navigation"],
                    "requires_javascript": False
                },
                "chapter": {
                    "title": "Romance Dawn",
                    "chapter_number": "1",
                    "pages": [
                        {"page_number": 1, "image_url": "https://..."}
                    ],
                    "total_pages": 54
                }
            }
        }
