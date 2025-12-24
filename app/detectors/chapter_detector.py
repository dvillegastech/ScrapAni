"""
Detector de listas de capítulos

Especializado en encontrar y parsear listas de capítulos
en páginas de información de series.
"""

import re
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass
from datetime import datetime

from app.utils.helpers import normalize_url, clean_text, extract_chapter_number


@dataclass
class DetectedChapter:
    """Capítulo detectado"""
    title: str
    url: str
    number: Optional[str] = None
    date: Optional[str] = None
    views: Optional[int] = None
    is_new: bool = False
    confidence: float = 0.0


class ChapterListDetector:
    """
    Detector de listas de capítulos.

    Identifica y extrae listas de capítulos de páginas de series.
    """

    # Selectores comunes para contenedores de capítulos
    CONTAINER_SELECTORS = [
        '.chapter-list',
        '.chapters-list',
        '#chapter-list',
        '.list-chapters',
        'ul.chapters',
        '.episode-list',
        '.chapter-container',
        '.manga-chapters',
        '.chapter-items',
        '.series-chapter-list',
        '.content-list',
        '[class*="chapter"][class*="list"]',
    ]

    # Patrones para detectar capítulos en URLs
    CHAPTER_URL_PATTERNS = [
        r'/chapter[-_/]?\d+',
        r'/ch[-_/]?\d+',
        r'/cap[-_/]?\d+',
        r'/capitulo[-_/]?\d+',
        r'/episode[-_/]?\d+',
        r'/ep[-_/]?\d+',
        r'/\d+(?:\.\d+)?/?$',
    ]

    # Palabras clave que indican un capítulo
    CHAPTER_KEYWORDS = [
        'chapter', 'cap', 'ch', 'capitulo', 'capítulo',
        'episode', 'ep', 'episodio',
        '화', '話', '章',  # Coreano/Japonés
    ]

    # Indicadores de capítulo nuevo
    NEW_INDICATORS = ['new', 'nuevo', 'hot', '🔥', 'latest', 'último', 'nuevo']

    def __init__(self, min_chapters: int = 2):
        """
        Inicializa el detector.

        Args:
            min_chapters: Mínimo de capítulos para considerar válida una lista
        """
        self.min_chapters = min_chapters
        self._chapter_url_re = re.compile(
            '|'.join(self.CHAPTER_URL_PATTERNS),
            re.I
        )

    def detect(self, soup: BeautifulSoup, base_url: str) -> List[DetectedChapter]:
        """
        Detecta capítulos en la página.

        Args:
            soup: Documento parseado
            base_url: URL base

        Returns:
            Lista de capítulos detectados
        """
        chapters = []
        seen_urls = set()

        # Buscar en contenedores específicos primero
        container = self._find_chapter_container(soup)

        if container:
            chapters = self._extract_from_container(container, base_url, seen_urls)

        # Si no encontramos suficientes, buscar en toda la página
        if len(chapters) < self.min_chapters:
            all_chapters = self._extract_from_page(soup, base_url, seen_urls)
            chapters.extend(all_chapters)

        # Ordenar por número de capítulo si es posible
        chapters = self._sort_chapters(chapters)

        return chapters

    def _find_chapter_container(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Encuentra el contenedor de capítulos."""
        for selector in self.CONTAINER_SELECTORS:
            container = soup.select_one(selector)
            if container:
                return container

        # Buscar por heurísticas
        for tag in soup.find_all(['ul', 'ol', 'div']):
            links = tag.find_all('a', href=True)
            chapter_links = 0

            for link in links[:10]:  # Revisar primeros 10 enlaces
                href = link.get('href', '')
                if self._chapter_url_re.search(href):
                    chapter_links += 1

            if chapter_links >= 3:
                return tag

        return None

    def _extract_from_container(
        self,
        container: Tag,
        base_url: str,
        seen_urls: set
    ) -> List[DetectedChapter]:
        """Extrae capítulos de un contenedor."""
        chapters = []

        # Buscar enlaces
        for link in container.find_all('a', href=True):
            chapter = self._parse_chapter_link(link, base_url, seen_urls)
            if chapter:
                chapter.confidence += 0.2  # Bonus por estar en contenedor
                chapters.append(chapter)
                seen_urls.add(chapter.url)

        return chapters

    def _extract_from_page(
        self,
        soup: BeautifulSoup,
        base_url: str,
        seen_urls: set
    ) -> List[DetectedChapter]:
        """Extrae capítulos de toda la página."""
        chapters = []

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')

            # Verificar si parece un enlace de capítulo
            if not self._chapter_url_re.search(href):
                continue

            chapter = self._parse_chapter_link(link, base_url, seen_urls)
            if chapter and chapter.url not in seen_urls:
                chapters.append(chapter)
                seen_urls.add(chapter.url)

        return chapters

    def _parse_chapter_link(
        self,
        link: Tag,
        base_url: str,
        seen_urls: set
    ) -> Optional[DetectedChapter]:
        """Parsea un enlace de capítulo."""
        href = link.get('href', '')
        if not href or href == '#':
            return None

        url = normalize_url(href, base_url)
        if url in seen_urls:
            return None

        # Obtener texto
        text = clean_text(link.get_text())
        if not text:
            text = f"Capítulo"

        # Calcular confianza
        confidence = self._calculate_confidence(link, href, text)

        if confidence < 0.3:
            return None

        # Extraer número de capítulo
        number = extract_chapter_number(text)
        if not number:
            number = extract_chapter_number(href)

        # Buscar fecha
        date = self._find_date(link)

        # Verificar si es nuevo
        is_new = self._is_new_chapter(link)

        # Buscar vistas
        views = self._find_views(link)

        return DetectedChapter(
            title=text,
            url=url,
            number=number,
            date=date,
            views=views,
            is_new=is_new,
            confidence=confidence,
        )

    def _calculate_confidence(self, link: Tag, href: str, text: str) -> float:
        """Calcula la confianza de que es un capítulo."""
        score = 0.3

        # Verificar URL
        if self._chapter_url_re.search(href.lower()):
            score += 0.3

        # Verificar texto
        text_lower = text.lower()
        for keyword in self.CHAPTER_KEYWORDS:
            if keyword in text_lower:
                score += 0.2
                break

        # Verificar si tiene número
        if re.search(r'\d+', text):
            score += 0.1

        # Verificar clases CSS
        classes = ' '.join(link.get('class', [])).lower()
        if re.search(r'chapter|cap|episode|ep', classes):
            score += 0.15

        # Verificar contexto del padre
        parent = link.parent
        if parent:
            parent_classes = ' '.join(parent.get('class', [])).lower()
            if re.search(r'chapter|item|episode', parent_classes):
                score += 0.1

        return min(1.0, score)

    def _find_date(self, link: Tag) -> Optional[str]:
        """Busca la fecha de publicación."""
        parent = link.parent

        for _ in range(3):  # Subir hasta 3 niveles
            if not parent:
                break

            # Buscar elemento con clase de fecha
            date_elem = parent.find(class_=re.compile(r'date|time|release|upload', re.I))
            if date_elem:
                return clean_text(date_elem.get_text())

            # Buscar elemento <time>
            time_elem = parent.find('time')
            if time_elem:
                return time_elem.get('datetime') or clean_text(time_elem.get_text())

            parent = parent.parent

        return None

    def _is_new_chapter(self, link: Tag) -> bool:
        """Verifica si el capítulo está marcado como nuevo."""
        # Verificar en el enlace
        text = link.get_text().lower()
        for indicator in self.NEW_INDICATORS:
            if indicator in text:
                return True

        # Verificar en el padre
        parent = link.parent
        if parent:
            parent_text = parent.get_text().lower()
            for indicator in self.NEW_INDICATORS:
                if indicator in parent_text:
                    return True

            # Verificar si hay badge/etiqueta
            badge = parent.find(class_=re.compile(r'new|badge|label|hot', re.I))
            if badge:
                return True

        return False

    def _find_views(self, link: Tag) -> Optional[int]:
        """Busca el contador de vistas."""
        parent = link.parent

        for _ in range(3):
            if not parent:
                break

            view_elem = parent.find(class_=re.compile(r'view|eye|seen', re.I))
            if view_elem:
                text = view_elem.get_text()
                # Extraer número
                match = re.search(r'([\d,\.]+)\s*[kKmM]?', text)
                if match:
                    num_str = match.group(1).replace(',', '').replace('.', '')
                    try:
                        return int(num_str)
                    except ValueError:
                        pass

            parent = parent.parent

        return None

    def _sort_chapters(self, chapters: List[DetectedChapter]) -> List[DetectedChapter]:
        """Ordena los capítulos por número."""
        def sort_key(ch):
            if ch.number:
                try:
                    return float(ch.number)
                except ValueError:
                    pass
            return 9999

        return sorted(chapters, key=sort_key)
