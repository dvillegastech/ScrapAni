"""
Motor de Scraping Inteligente para Manga

Este módulo contiene la lógica principal para extraer contenido de manga
de cualquier sitio web de forma inteligente, detectando patrones automáticamente.
"""

import re
import ssl
import httpx
import random
from bs4 import BeautifulSoup, Tag
from typing import Optional, List, Dict, Any, Tuple
from urllib.parse import urlparse, urljoin
from dataclasses import dataclass
from collections import Counter

# Intentar importar cloudscraper para bypass de Cloudflare
try:
    import cloudscraper
    CLOUDSCRAPER_AVAILABLE = True
except ImportError:
    CLOUDSCRAPER_AVAILABLE = False

from app.models.schemas import (
    ContentType,
    SiteAnalysis,
    MangaPage,
    MangaChapter,
    MangaSeries,
    ChapterInfo,
    NavigationInfo,
    ImageInfo,
)
from app.utils.helpers import (
    normalize_url,
    get_domain,
    is_image_url,
    clean_text,
    extract_chapter_number,
)


@dataclass
class ImageCandidate:
    """Candidato a imagen de manga"""
    url: str
    element: Tag
    score: float
    width: Optional[int] = None
    height: Optional[int] = None
    container: Optional[Tag] = None


class IntelligentMangaScraper:
    """
    Scraper inteligente que analiza y extrae manga de cualquier sitio.

    Usa heurísticas y análisis de patrones para detectar:
    - Imágenes de manga (páginas)
    - Navegación entre capítulos
    - Información de la serie
    - Lista de capítulos
    """

    # Lista de User-Agents para rotación (ayuda a evitar bloqueos)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    # Headers para simular un navegador real
    DEFAULT_HEADERS = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,es;q=0.8,ja;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
    }

    # Patrones que indican imágenes de manga
    MANGA_IMAGE_PATTERNS = [
        r'(?:chapter|cap|ch)[\-_/]?\d+',
        r'(?:page|pag|p)[\-_/]?\d+',
        r'/\d{1,4}\.(jpg|jpeg|png|webp|gif)',
        r'(?:manga|comic|scan).*\d+',
        r'/images?/.*\d+',
        r'/uploads?/.*\d+',
    ]

    # Patrones de navegación
    NAV_PATTERNS = {
        'next': [
            r'next\s*(?:chapter|ch|cap)?',
            r'siguiente',
            r'próximo',
            r'>>',
            r'→',
        ],
        'prev': [
            r'prev(?:ious)?\s*(?:chapter|ch|cap)?',
            r'anterior',
            r'<<',
            r'←',
        ],
        'chapter_list': [
            r'chapter\s*list',
            r'all\s*chapters?',
            r'lista.*cap',
            r'índice',
            r'index',
        ]
    }

    # Selectores CSS comunes para contenedores de manga
    READER_CONTAINER_SELECTORS = [
        '.reader-area',
        '.reading-content',
        '.chapter-content',
        '.manga-reader',
        '.page-container',
        '#manga-reader',
        '#reader-container',
        '#content-reader',
        '.viewer-container',
        '#viewer',
        '.comic-reader',
        'article.content',
        '.entry-content',
        'main',
    ]

    # Selectores para listas de capítulos
    CHAPTER_LIST_SELECTORS = [
        '.chapter-list',
        '.chapters-list',
        '#chapter-list',
        '.list-chapters',
        'ul.chapters',
        '.episode-list',
        '.chapter-container',
        '.manga-chapters',
    ]

    def __init__(self, timeout: int = 30):
        """
        Inicializa el scraper.

        Args:
            timeout: Timeout para requests en segundos
        """
        self.timeout = timeout
        # Crear contexto SSL más permisivo para sitios con configuración problemática
        self._ssl_context = self._create_ssl_context()
        self.client = None  # Se crea lazy

    def _create_ssl_context(self):
        """Crea un contexto SSL más permisivo."""
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        # Habilitar más protocolos para compatibilidad
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        return ctx

    def _get_client(self) -> httpx.Client:
        """Obtiene o crea el cliente HTTP."""
        if self.client is None:
            self.client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                verify=False,  # Deshabilitar verificación SSL estricta
            )
        return self.client

    def __del__(self):
        """Cierra el cliente HTTP al destruir el objeto."""
        if hasattr(self, 'client') and self.client is not None:
            self.client.close()

    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Método principal de scraping.

        Args:
            url: URL del sitio de manga

        Returns:
            Diccionario con los datos extraídos
        """
        # Obtener el HTML
        html = self._fetch_page(url)
        if not html:
            return {
                "success": False,
                "error": "No se pudo obtener el contenido de la página"
            }

        # Parsear el HTML
        soup = BeautifulSoup(html, 'lxml')

        # Analizar el tipo de contenido
        analysis = self._analyze_content_type(soup, url)

        result = {
            "success": True,
            "url": url,
            "analysis": analysis,
        }

        # Extraer contenido según el tipo detectado
        if analysis.detected_type == ContentType.MANGA_PAGE:
            chapter = self._extract_chapter(soup, url)
            result["chapter"] = chapter
        elif analysis.detected_type == ContentType.CHAPTER_LIST:
            series = self._extract_series_with_chapters(soup, url)
            result["series"] = series
        elif analysis.detected_type == ContentType.SERIES_INFO:
            series = self._extract_series_info(soup, url)
            result["series"] = series
        else:
            # Intentar extraer lo que podamos
            chapter = self._extract_chapter(soup, url)
            if chapter and chapter.pages:
                result["chapter"] = chapter
                analysis.detected_type = ContentType.MANGA_PAGE

        return result

    def _fetch_page(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Obtiene el HTML de una página con reintentos y bypass de Cloudflare.

        Usa cloudscraper como método primario (mejor para Cloudflare),
        con fallback a httpx para sitios sin protección.

        Args:
            url: URL a obtener
            max_retries: Número máximo de reintentos

        Returns:
            HTML de la página o None si falla
        """
        import time
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        parsed = urlparse(url)

        # Método 1: Intentar con cloudscraper (mejor para Cloudflare)
        if CLOUDSCRAPER_AVAILABLE:
            result = self._fetch_with_cloudscraper(url, max_retries)
            if result:
                return result

        # Método 2: Fallback a httpx estándar
        return self._fetch_with_httpx(url, max_retries)

    def _fetch_with_cloudscraper(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Obtiene página usando cloudscraper (bypass Cloudflare)."""
        import time

        parsed = urlparse(url)

        for attempt in range(max_retries):
            try:
                # Crear scraper con browser emulado
                scraper = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'mobile': False,
                    },
                    delay=5,
                )

                headers = self.DEFAULT_HEADERS.copy()
                headers["User-Agent"] = random.choice(self.USER_AGENTS)
                headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

                response = scraper.get(url, headers=headers, timeout=self.timeout)

                if response.status_code == 200:
                    return response.text
                elif response.status_code in [403, 503, 520, 521, 522, 523, 524]:
                    print(f"Cloudflare block (intento {attempt + 1}): {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(2 + attempt * 2)
                        continue
                else:
                    response.raise_for_status()
                    return response.text

            except Exception as e:
                print(f"CloudScraper error (intento {attempt + 1}): {type(e).__name__}")
                if attempt < max_retries - 1:
                    time.sleep(1 + attempt)
                    continue

        return None

    def _fetch_with_httpx(self, url: str, max_retries: int = 3) -> Optional[str]:
        """Obtiene página usando httpx estándar."""
        import time

        parsed = urlparse(url)

        for attempt in range(max_retries):
            try:
                headers = self.DEFAULT_HEADERS.copy()
                headers["User-Agent"] = random.choice(self.USER_AGENTS)
                headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"
                headers["Host"] = parsed.netloc

                with httpx.Client(
                    timeout=self.timeout,
                    follow_redirects=True,
                    verify=False,
                ) as client:
                    response = client.get(url, headers=headers)

                    if response.status_code in [403, 503]:
                        if attempt < max_retries - 1:
                            time.sleep(1 + attempt)
                            continue
                        return None

                    response.raise_for_status()
                    return response.text

            except Exception as e:
                print(f"HTTPX error (intento {attempt + 1}): {type(e).__name__}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue

        return None

    def _analyze_content_type(self, soup: BeautifulSoup, url: str) -> SiteAnalysis:
        """
        Analiza el tipo de contenido de la página.

        Args:
            soup: BeautifulSoup parseado
            url: URL original

        Returns:
            SiteAnalysis con el tipo detectado
        """
        domain = get_domain(url)
        detected_patterns = []
        scores = {
            ContentType.MANGA_PAGE: 0.0,
            ContentType.CHAPTER_LIST: 0.0,
            ContentType.SERIES_INFO: 0.0,
        }

        # Analizar imágenes
        images = soup.find_all('img')
        large_images = self._find_manga_image_candidates(soup, url)

        if len(large_images) >= 3:
            scores[ContentType.MANGA_PAGE] += 0.4
            detected_patterns.append("multiple_large_images")

        # Buscar contenedores de lectura
        for selector in self.READER_CONTAINER_SELECTORS:
            if soup.select_one(selector):
                scores[ContentType.MANGA_PAGE] += 0.2
                detected_patterns.append(f"reader_container:{selector}")
                break

        # Buscar listas de capítulos
        chapter_links = self._find_chapter_links(soup, url)
        if len(chapter_links) >= 5:
            scores[ContentType.CHAPTER_LIST] += 0.4
            detected_patterns.append("chapter_links")

        for selector in self.CHAPTER_LIST_SELECTORS:
            if soup.select_one(selector):
                scores[ContentType.CHAPTER_LIST] += 0.2
                detected_patterns.append(f"chapter_list_container:{selector}")
                break

        # Buscar información de serie
        title_tag = soup.find(['h1', 'h2'], class_=re.compile(r'title|name|manga', re.I))
        if title_tag:
            detected_patterns.append("series_title")
            scores[ContentType.SERIES_INFO] += 0.15

        # Buscar sinopsis/descripción
        desc_element = soup.find(class_=re.compile(r'desc|synopsis|summary|about', re.I))
        if desc_element:
            detected_patterns.append("description")
            scores[ContentType.SERIES_INFO] += 0.15

        # Buscar navegación de capítulos (indica página de lectura)
        nav_elements = soup.find_all(['a', 'button'], string=re.compile(r'next|prev|siguiente|anterior', re.I))
        if nav_elements:
            scores[ContentType.MANGA_PAGE] += 0.15
            detected_patterns.append("chapter_navigation")

        # Analizar URL para patrones
        url_lower = url.lower()
        if re.search(r'/chapter[-_/]?\d+|/ch[-_/]?\d+|/cap[-_/]?\d+', url_lower):
            scores[ContentType.MANGA_PAGE] += 0.25
            detected_patterns.append("chapter_url_pattern")
        elif re.search(r'/manga/[^/]+/?$|/series/[^/]+/?$|/comic/[^/]+/?$', url_lower):
            scores[ContentType.SERIES_INFO] += 0.2
            detected_patterns.append("series_url_pattern")

        # Determinar tipo con mayor score
        max_type = max(scores, key=scores.get)
        max_score = scores[max_type]

        # Si ningún score es significativo, marcar como desconocido
        if max_score < 0.2:
            max_type = ContentType.UNKNOWN
            max_score = 0.0

        # Detectar si requiere JavaScript
        requires_js = self._detect_javascript_requirement(soup)
        if requires_js:
            detected_patterns.append("requires_javascript")

        return SiteAnalysis(
            detected_type=max_type,
            confidence=min(max_score, 1.0),
            site_domain=domain,
            detected_patterns=detected_patterns,
            requires_javascript=requires_js,
        )

    def _detect_javascript_requirement(self, soup: BeautifulSoup) -> bool:
        """
        Detecta si la página requiere JavaScript para mostrar contenido.

        Args:
            soup: BeautifulSoup parseado

        Returns:
            True si parece requerir JavaScript
        """
        # Buscar indicadores comunes de contenido cargado por JS
        indicators = [
            soup.find('noscript'),  # Tiene alternativa sin JS
            soup.find(string=re.compile(r'javascript.*required|enable.*javascript', re.I)),
            soup.find('div', {'id': re.compile(r'^app$|^root$|^__next')}),  # Apps SPA
        ]

        # Verificar si hay muy pocas imágenes (podrían cargarse por JS)
        images = soup.find_all('img')
        if len(images) < 3:
            return True

        return any(indicators)

    def _find_manga_image_candidates(self, soup: BeautifulSoup, base_url: str) -> List[ImageCandidate]:
        """
        Encuentra imágenes candidatas a ser páginas de manga.

        Usa heurísticas como:
        - Tamaño de imagen (manga suele ser más grande)
        - Patrones en URL
        - Posición en el DOM
        - Atributos del elemento

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base para resolver URLs relativas

        Returns:
            Lista de candidatos ordenados por score
        """
        candidates = []

        # Buscar todas las imágenes
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src') or ''
            src = normalize_url(src, base_url)

            if not src or not is_image_url(src):
                continue

            score = self._calculate_image_score(img, src)

            if score > 0.3:  # Solo considerar candidatos con score mínimo
                width = self._parse_dimension(img.get('width'))
                height = self._parse_dimension(img.get('height'))

                candidates.append(ImageCandidate(
                    url=src,
                    element=img,
                    score=score,
                    width=width,
                    height=height,
                    container=img.parent,
                ))

        # Ordenar por score descendente
        candidates.sort(key=lambda x: x.score, reverse=True)

        return candidates

    def _calculate_image_score(self, img: Tag, src: str) -> float:
        """
        Calcula el score de una imagen para determinar si es manga.

        Args:
            img: Elemento img
            src: URL de la imagen

        Returns:
            Score de 0 a 1
        """
        score = 0.0
        src_lower = src.lower()

        # Verificar patrones de URL de manga
        for pattern in self.MANGA_IMAGE_PATTERNS:
            if re.search(pattern, src_lower):
                score += 0.2
                break

        # Verificar tamaño (manga suele ser grande)
        width = self._parse_dimension(img.get('width'))
        height = self._parse_dimension(img.get('height'))

        if width and width > 600:
            score += 0.15
        if height and height > 800:
            score += 0.15

        # Verificar clases CSS
        classes = ' '.join(img.get('class', []))
        if re.search(r'page|manga|chapter|reader|comic|scan', classes, re.I):
            score += 0.2

        # Verificar atributos data
        for attr, value in img.attrs.items():
            if attr.startswith('data-') and isinstance(value, str):
                if re.search(r'page|chapter|src|lazy', attr, re.I):
                    score += 0.1
                    break

        # Verificar si está en un contenedor de lectura
        parent = img.parent
        for _ in range(5):  # Subir hasta 5 niveles
            if parent:
                parent_classes = ' '.join(parent.get('class', []))
                parent_id = parent.get('id', '')
                if re.search(r'reader|chapter|page|manga|content|viewer',
                           f"{parent_classes} {parent_id}", re.I):
                    score += 0.15
                    break
                parent = parent.parent

        # Penalizar si parece ser UI/icono/banner
        if re.search(r'icon|logo|avatar|banner|ad|thumb|small|mini', src_lower):
            score -= 0.3
        if re.search(r'icon|logo|avatar|banner|ad|thumb', classes, re.I):
            score -= 0.3

        # Bonus si tiene data-src (lazy loading típico de manga)
        if img.get('data-src') or img.get('data-lazy-src'):
            score += 0.1

        return max(0, min(score, 1.0))

    def _parse_dimension(self, value) -> Optional[int]:
        """Parsea una dimensión (width/height) a entero."""
        if not value:
            return None
        try:
            # Remover 'px' si está presente
            if isinstance(value, str):
                value = value.replace('px', '').strip()
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _find_chapter_links(self, soup: BeautifulSoup, base_url: str) -> List[ChapterInfo]:
        """
        Encuentra enlaces a capítulos en la página.

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base

        Returns:
            Lista de capítulos encontrados
        """
        chapters = []
        seen_urls = set()

        # Buscar en contenedores de capítulos
        for selector in self.CHAPTER_LIST_SELECTORS:
            container = soup.select_one(selector)
            if container:
                links = container.find_all('a', href=True)
                for link in links:
                    chapter = self._parse_chapter_link(link, base_url)
                    if chapter and chapter.url not in seen_urls:
                        chapters.append(chapter)
                        seen_urls.add(chapter.url)
                if chapters:
                    break

        # Si no encontramos en contenedores, buscar por patrones en URL
        if not chapters:
            all_links = soup.find_all('a', href=True)
            for link in all_links:
                href = link.get('href', '')
                if re.search(r'/chapter[-_/]?\d+|/ch[-_/]?\d+|/cap[-_/]?\d+|/episode[-_/]?\d+',
                           href, re.I):
                    chapter = self._parse_chapter_link(link, base_url)
                    if chapter and chapter.url not in seen_urls:
                        chapters.append(chapter)
                        seen_urls.add(chapter.url)

        return chapters

    def _parse_chapter_link(self, link: Tag, base_url: str) -> Optional[ChapterInfo]:
        """
        Parsea un enlace de capítulo.

        Args:
            link: Elemento <a>
            base_url: URL base

        Returns:
            ChapterInfo o None
        """
        href = link.get('href', '')
        if not href:
            return None

        url = normalize_url(href, base_url)
        text = clean_text(link.get_text())

        if not text:
            text = f"Chapter"

        chapter_num = extract_chapter_number(text) or extract_chapter_number(url)

        # Buscar fecha si existe
        date = None
        parent = link.parent
        if parent:
            date_elem = parent.find(class_=re.compile(r'date|time|release', re.I))
            if date_elem:
                date = clean_text(date_elem.get_text())

        return ChapterInfo(
            title=text,
            url=url,
            chapter_number=chapter_num,
            date=date,
        )

    def _extract_chapter(self, soup: BeautifulSoup, base_url: str) -> MangaChapter:
        """
        Extrae las páginas de un capítulo de manga.

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base

        Returns:
            MangaChapter con las páginas extraídas
        """
        # Encontrar candidatos de imagen
        candidates = self._find_manga_image_candidates(soup, base_url)

        # Filtrar y ordenar las mejores imágenes
        pages = []
        seen_urls = set()

        for i, candidate in enumerate(candidates):
            if candidate.url in seen_urls:
                continue
            if candidate.score < 0.35:  # Umbral mínimo
                continue

            seen_urls.add(candidate.url)
            pages.append(MangaPage(
                page_number=len(pages) + 1,
                image_url=candidate.url,
                image_urls_backup=[],
            ))

        # Intentar extraer más imágenes de scripts (lazy loading)
        extra_images = self._extract_images_from_scripts(soup, base_url)
        for img_url in extra_images:
            if img_url not in seen_urls:
                seen_urls.add(img_url)
                pages.append(MangaPage(
                    page_number=len(pages) + 1,
                    image_url=img_url,
                    image_urls_backup=[],
                ))

        # Extraer título del capítulo
        title = self._extract_chapter_title(soup)
        chapter_num = extract_chapter_number(title) or extract_chapter_number(base_url)

        # Extraer navegación
        navigation = self._extract_navigation(soup, base_url)

        return MangaChapter(
            title=title,
            chapter_number=chapter_num,
            pages=pages,
            total_pages=len(pages),
            navigation=navigation,
        )

    def _extract_images_from_scripts(self, soup: BeautifulSoup, base_url: str) -> List[str]:
        """
        Extrae URLs de imágenes de scripts JavaScript.

        Muchos sitios de manga cargan las imágenes dinámicamente desde
        arrays o objetos JSON en los scripts.

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base

        Returns:
            Lista de URLs de imágenes
        """
        images = []

        for script in soup.find_all('script'):
            script_text = script.string or ''

            # Buscar arrays de imágenes
            patterns = [
                r'"(https?://[^"]+\.(?:jpg|jpeg|png|webp|gif))"',
                r"'(https?://[^']+\.(?:jpg|jpeg|png|webp|gif))'",
                r'"([^"]+/(?:chapter|manga|page|images?)[^"]+\.(?:jpg|jpeg|png|webp|gif))"',
            ]

            for pattern in patterns:
                matches = re.findall(pattern, script_text, re.I)
                for match in matches:
                    url = normalize_url(match, base_url)
                    if url and is_image_url(url):
                        images.append(url)

        # Eliminar duplicados manteniendo orden
        seen = set()
        unique_images = []
        for img in images:
            if img not in seen:
                seen.add(img)
                unique_images.append(img)

        return unique_images

    def _extract_chapter_title(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extrae el título del capítulo.

        Args:
            soup: BeautifulSoup parseado

        Returns:
            Título del capítulo o None
        """
        # Buscar en diferentes lugares
        selectors = [
            'h1',
            '.chapter-title',
            '.chapter-name',
            '#chapter-title',
            '.entry-title',
            'title',
        ]

        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = clean_text(element.get_text())
                if text and len(text) < 200:  # Evitar textos muy largos
                    return text

        return None

    def _extract_navigation(self, soup: BeautifulSoup, base_url: str) -> NavigationInfo:
        """
        Extrae enlaces de navegación (siguiente/anterior capítulo).

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base

        Returns:
            NavigationInfo
        """
        next_url = None
        prev_url = None
        chapter_list_url = None

        # Buscar enlaces de navegación
        all_links = soup.find_all('a', href=True)

        for link in all_links:
            href = link.get('href', '')
            text = clean_text(link.get_text()).lower()
            classes = ' '.join(link.get('class', [])).lower()
            combined = f"{text} {classes}"

            # Next chapter
            for pattern in self.NAV_PATTERNS['next']:
                if re.search(pattern, combined, re.I):
                    next_url = normalize_url(href, base_url)
                    break

            # Previous chapter
            for pattern in self.NAV_PATTERNS['prev']:
                if re.search(pattern, combined, re.I):
                    prev_url = normalize_url(href, base_url)
                    break

            # Chapter list
            for pattern in self.NAV_PATTERNS['chapter_list']:
                if re.search(pattern, combined, re.I):
                    chapter_list_url = normalize_url(href, base_url)
                    break

        return NavigationInfo(
            next_chapter=next_url,
            prev_chapter=prev_url,
            chapter_list=chapter_list_url,
        )

    def _extract_series_info(self, soup: BeautifulSoup, base_url: str) -> MangaSeries:
        """
        Extrae información de una serie de manga.

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base

        Returns:
            MangaSeries
        """
        # Título
        title = None
        for selector in ['h1', '.manga-title', '.series-title', '.entry-title', '.post-title']:
            elem = soup.select_one(selector)
            if elem:
                title = clean_text(elem.get_text())
                if title:
                    break

        # Descripción
        description = None
        for selector in ['.description', '.synopsis', '.summary', '.manga-description']:
            elem = soup.select_one(selector)
            if elem:
                description = clean_text(elem.get_text())
                if description:
                    break

        # Portada
        cover = None
        cover_selectors = ['.manga-cover img', '.series-cover img', '.thumb img', '.poster img']
        for selector in cover_selectors:
            elem = soup.select_one(selector)
            if elem:
                cover = normalize_url(elem.get('src') or elem.get('data-src', ''), base_url)
                if cover:
                    break

        # Géneros
        genres = []
        genre_container = soup.find(class_=re.compile(r'genres?|tags?|categories', re.I))
        if genre_container:
            genre_links = genre_container.find_all('a')
            genres = [clean_text(g.get_text()) for g in genre_links if g.get_text().strip()]

        # Autor/Artista
        author = None
        artist = None
        for label in soup.find_all(['span', 'div', 'li']):
            text = label.get_text().lower()
            if 'author' in text or 'autor' in text:
                # Buscar el valor en el siguiente elemento o mismo elemento
                value = label.find('a') or label.find(class_=re.compile(r'value'))
                if value:
                    author = clean_text(value.get_text())
            if 'artist' in text or 'artista' in text:
                value = label.find('a') or label.find(class_=re.compile(r'value'))
                if value:
                    artist = clean_text(value.get_text())

        # Estado
        status = None
        status_elem = soup.find(class_=re.compile(r'status', re.I))
        if status_elem:
            status = clean_text(status_elem.get_text())

        # Capítulos
        chapters = self._find_chapter_links(soup, base_url)

        return MangaSeries(
            title=title,
            description=description,
            cover_image=cover,
            author=author,
            artist=artist,
            genres=genres,
            status=status,
            chapters=chapters,
            total_chapters=len(chapters),
        )

    def _extract_series_with_chapters(self, soup: BeautifulSoup, base_url: str) -> MangaSeries:
        """
        Extrae una serie enfocándose en la lista de capítulos.

        Args:
            soup: BeautifulSoup parseado
            base_url: URL base

        Returns:
            MangaSeries
        """
        # Similar a _extract_series_info pero priorizando capítulos
        series = self._extract_series_info(soup, base_url)
        return series
