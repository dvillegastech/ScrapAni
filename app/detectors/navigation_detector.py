"""
Detector de navegación entre capítulos

Especializado en encontrar enlaces de navegación:
- Siguiente capítulo
- Capítulo anterior
- Lista de capítulos
"""

import re
from typing import Optional, Dict
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass

from app.utils.helpers import normalize_url


@dataclass
class NavigationLinks:
    """Enlaces de navegación detectados"""
    next_chapter: Optional[str] = None
    prev_chapter: Optional[str] = None
    chapter_list: Optional[str] = None
    first_chapter: Optional[str] = None
    last_chapter: Optional[str] = None
    confidence: float = 0.0


class NavigationDetector:
    """
    Detector de enlaces de navegación entre capítulos.

    Soporta múltiples idiomas y patrones comunes.
    """

    # Patrones para navegación en múltiples idiomas
    NEXT_PATTERNS = [
        r'\bnext\b',
        r'\bsiguiente\b',
        r'\bpróximo\b',
        r'\bproximo\b',
        r'\b次\b',  # Japonés
        r'\b다음\b',  # Coreano
        r'>>',
        r'→',
        r'►',
        r'\bforward\b',
    ]

    PREV_PATTERNS = [
        r'\bprev(?:ious)?\b',
        r'\banterior\b',
        r'\b前\b',  # Japonés
        r'\b이전\b',  # Coreano
        r'<<',
        r'←',
        r'◄',
        r'\bback\b',
    ]

    CHAPTER_LIST_PATTERNS = [
        r'\bchapter\s*list\b',
        r'\ball\s*chapters?\b',
        r'\blista.*cap',
        r'\bíndice\b',
        r'\bindice\b',
        r'\bindex\b',
        r'\btoc\b',
        r'\b目次\b',  # Japonés (tabla de contenidos)
        r'\bcontents?\b',
    ]

    FIRST_PATTERNS = [
        r'\bfirst\b',
        r'\bprimero\b',
        r'\binicio\b',
        r'\b最初\b',
        r'<<\s*1',
    ]

    LAST_PATTERNS = [
        r'\blast\b',
        r'\blatest\b',
        r'\búltimo\b',
        r'\bultimo\b',
        r'\b最新\b',
        r'\bnewest\b',
    ]

    # Selectores CSS comunes para navegación
    NAV_SELECTORS = [
        '.chapter-nav',
        '.reader-nav',
        '.navigation',
        '#chapter-navigation',
        '.nav-buttons',
        '.chapter-buttons',
        '.reader-controls',
        '.page-navigation',
    ]

    def __init__(self):
        """Inicializa el detector."""
        # Compilar patrones para eficiencia
        self._next_re = re.compile('|'.join(self.NEXT_PATTERNS), re.I)
        self._prev_re = re.compile('|'.join(self.PREV_PATTERNS), re.I)
        self._list_re = re.compile('|'.join(self.CHAPTER_LIST_PATTERNS), re.I)
        self._first_re = re.compile('|'.join(self.FIRST_PATTERNS), re.I)
        self._last_re = re.compile('|'.join(self.LAST_PATTERNS), re.I)

    def detect(self, soup: BeautifulSoup, base_url: str) -> NavigationLinks:
        """
        Detecta enlaces de navegación en la página.

        Args:
            soup: Documento parseado
            base_url: URL base

        Returns:
            NavigationLinks con los enlaces encontrados
        """
        result = NavigationLinks()
        confidence_scores = []

        # Primero buscar en contenedores de navegación
        nav_container = self._find_nav_container(soup)

        if nav_container:
            links = nav_container.find_all('a', href=True)
            confidence_scores.append(0.3)  # Bonus por encontrar contenedor
        else:
            links = soup.find_all('a', href=True)

        # Buscar cada tipo de enlace
        for link in links:
            href = link.get('href', '')
            if not href or href == '#':
                continue

            url = normalize_url(href, base_url)
            text = link.get_text().strip().lower()
            classes = ' '.join(link.get('class', [])).lower()
            title = (link.get('title') or '').lower()
            combined = f"{text} {classes} {title}"

            # Verificar siguiente capítulo
            if not result.next_chapter and self._next_re.search(combined):
                result.next_chapter = url
                confidence_scores.append(0.2)

            # Verificar capítulo anterior
            elif not result.prev_chapter and self._prev_re.search(combined):
                result.prev_chapter = url
                confidence_scores.append(0.2)

            # Verificar lista de capítulos
            elif not result.chapter_list and self._list_re.search(combined):
                result.chapter_list = url
                confidence_scores.append(0.15)

            # Verificar primer capítulo
            elif not result.first_chapter and self._first_re.search(combined):
                result.first_chapter = url
                confidence_scores.append(0.1)

            # Verificar último capítulo
            elif not result.last_chapter and self._last_re.search(combined):
                result.last_chapter = url
                confidence_scores.append(0.1)

        # Calcular confianza total
        result.confidence = min(1.0, sum(confidence_scores))

        return result

    def _find_nav_container(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Busca un contenedor de navegación."""
        for selector in self.NAV_SELECTORS:
            container = soup.select_one(selector)
            if container:
                return container

        # Buscar por patrones en clases/IDs
        for tag in soup.find_all(['div', 'nav', 'section']):
            classes = ' '.join(tag.get('class', []))
            tag_id = tag.get('id', '')
            combined = f"{classes} {tag_id}".lower()

            if re.search(r'nav|chapter.*button|reader.*control', combined):
                return tag

        return None

    def detect_pagination(self, soup: BeautifulSoup, base_url: str) -> Dict[str, str]:
        """
        Detecta paginación dentro del capítulo (para readers paginados).

        Args:
            soup: Documento parseado
            base_url: URL base

        Returns:
            Dict con enlaces de paginación
        """
        pagination = {}

        # Buscar selector de páginas
        page_selectors = soup.find_all(['select', 'ul'], class_=re.compile(r'page|selector', re.I))

        for selector in page_selectors:
            if selector.name == 'select':
                # Es un dropdown de páginas
                options = selector.find_all('option')
                for opt in options:
                    value = opt.get('value')
                    if value:
                        text = opt.get_text().strip()
                        pagination[text] = normalize_url(value, base_url)
            else:
                # Es una lista de páginas
                links = selector.find_all('a', href=True)
                for link in links:
                    text = link.get_text().strip()
                    if text.isdigit():
                        pagination[text] = normalize_url(link['href'], base_url)

        return pagination
