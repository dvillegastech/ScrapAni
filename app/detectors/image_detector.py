"""
Detector de imágenes de manga

Especializado en identificar imágenes que son páginas de manga
vs imágenes de UI, banners, avatars, etc.
"""

import re
from typing import List, Tuple, Optional
from bs4 import BeautifulSoup, Tag
from dataclasses import dataclass

from app.utils.helpers import normalize_url, is_image_url


@dataclass
class DetectedImage:
    """Imagen detectada como potencial página de manga"""
    url: str
    confidence: float
    page_number: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    source_attribute: str = "src"


class MangaImageDetector:
    """
    Detector inteligente de imágenes de manga.

    Utiliza múltiples señales para determinar si una imagen es
    parte del contenido de manga o es UI/decoración.
    """

    # Patrones positivos (aumentan score)
    POSITIVE_URL_PATTERNS = [
        (r'/chapters?/', 0.25),
        (r'/pages?/', 0.25),
        (r'/manga/', 0.20),
        (r'/comics?/', 0.20),
        (r'/scans?/', 0.20),
        (r'/images?/\d+', 0.15),
        (r'/uploads?/', 0.15),
        (r'/\d{1,3}\.(jpg|jpeg|png|webp)', 0.20),
        (r'cdn.*manga', 0.15),
        (r'img.*chapter', 0.15),
    ]

    # Patrones negativos (disminuyen score)
    NEGATIVE_URL_PATTERNS = [
        (r'/icon', -0.4),
        (r'/logo', -0.4),
        (r'/avatar', -0.4),
        (r'/banner', -0.3),
        (r'/ad/', -0.5),
        (r'/thumb', -0.2),
        (r'/small', -0.3),
        (r'/mini', -0.3),
        (r'favicon', -0.5),
        (r'sprite', -0.4),
        (r'/emoji', -0.5),
        (r'\.gif$', -0.2),  # Los GIFs suelen ser UI
    ]

    # Clases CSS positivas
    POSITIVE_CSS_CLASSES = [
        (r'page', 0.25),
        (r'manga', 0.20),
        (r'chapter', 0.20),
        (r'reader', 0.20),
        (r'comic', 0.15),
        (r'content', 0.10),
        (r'scan', 0.15),
    ]

    # Clases CSS negativas
    NEGATIVE_CSS_CLASSES = [
        (r'icon', -0.3),
        (r'logo', -0.3),
        (r'avatar', -0.3),
        (r'thumb', -0.2),
        (r'banner', -0.3),
        (r'ad', -0.4),
        (r'header', -0.2),
        (r'footer', -0.2),
        (r'sidebar', -0.3),
        (r'nav', -0.3),
    ]

    # Atributos de lazy loading
    LAZY_LOAD_ATTRS = [
        'data-src',
        'data-lazy-src',
        'data-original',
        'data-image',
        'data-srcset',
        'lazy-src',
        'loading-src',
    ]

    def __init__(self, min_confidence: float = 0.35):
        """
        Inicializa el detector.

        Args:
            min_confidence: Confianza mínima para considerar una imagen
        """
        self.min_confidence = min_confidence

    def detect(self, soup: BeautifulSoup, base_url: str) -> List[DetectedImage]:
        """
        Detecta imágenes de manga en la página.

        Args:
            soup: Documento parseado
            base_url: URL base para resolver URLs relativas

        Returns:
            Lista de imágenes detectadas ordenadas por confianza
        """
        detected = []
        seen_urls = set()

        for img in soup.find_all('img'):
            # Obtener URL de la imagen
            url = self._get_image_url(img, base_url)
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            # Calcular confianza
            confidence = self._calculate_confidence(img, url)

            if confidence >= self.min_confidence:
                # Intentar obtener número de página
                page_num = self._extract_page_number(img, url)

                detected.append(DetectedImage(
                    url=url,
                    confidence=confidence,
                    page_number=page_num,
                    width=self._parse_dimension(img.get('width')),
                    height=self._parse_dimension(img.get('height')),
                    source_attribute=self._get_source_attribute(img),
                ))

        # Ordenar por confianza y luego por número de página
        detected.sort(key=lambda x: (-x.confidence, x.page_number or 999))

        return detected

    def _get_image_url(self, img: Tag, base_url: str) -> Optional[str]:
        """Obtiene la URL de la imagen, considerando lazy loading."""
        url = None

        # Primero verificar atributos de lazy loading
        for attr in self.LAZY_LOAD_ATTRS:
            url = img.get(attr)
            if url:
                break

        # Fallback a src
        if not url:
            url = img.get('src')

        if not url:
            return None

        url = normalize_url(url, base_url)

        # Verificar que es una URL de imagen válida
        if not is_image_url(url):
            return None

        return url

    def _calculate_confidence(self, img: Tag, url: str) -> float:
        """Calcula la confianza de que la imagen es manga."""
        score = 0.3  # Base score

        url_lower = url.lower()

        # Evaluar patrones en URL
        for pattern, weight in self.POSITIVE_URL_PATTERNS:
            if re.search(pattern, url_lower, re.I):
                score += weight

        for pattern, weight in self.NEGATIVE_URL_PATTERNS:
            if re.search(pattern, url_lower, re.I):
                score += weight  # weight es negativo

        # Evaluar clases CSS
        classes = ' '.join(img.get('class', []))
        for pattern, weight in self.POSITIVE_CSS_CLASSES:
            if re.search(pattern, classes, re.I):
                score += weight

        for pattern, weight in self.NEGATIVE_CSS_CLASSES:
            if re.search(pattern, classes, re.I):
                score += weight

        # Bonus por lazy loading (típico de readers de manga)
        if any(img.get(attr) for attr in self.LAZY_LOAD_ATTRS):
            score += 0.15

        # Evaluar dimensiones
        width = self._parse_dimension(img.get('width'))
        height = self._parse_dimension(img.get('height'))

        if width:
            if width > 600:
                score += 0.15
            elif width < 100:
                score -= 0.2

        if height:
            if height > 800:
                score += 0.15
            elif height < 100:
                score -= 0.2

        # Evaluar contexto del padre
        score += self._evaluate_parent_context(img)

        return max(0.0, min(1.0, score))

    def _evaluate_parent_context(self, img: Tag) -> float:
        """Evalúa el contexto del elemento padre."""
        score = 0.0
        parent = img.parent

        for _ in range(4):  # Subir hasta 4 niveles
            if not parent or parent.name == 'body':
                break

            parent_classes = ' '.join(parent.get('class', []))
            parent_id = parent.get('id', '')
            combined = f"{parent_classes} {parent_id}".lower()

            # Contextos positivos
            if re.search(r'reader|chapter|page|manga|content|viewer|comic', combined):
                score += 0.15
                break

            # Contextos negativos
            if re.search(r'sidebar|nav|header|footer|ad|banner|menu', combined):
                score -= 0.2
                break

            parent = parent.parent

        return score

    def _extract_page_number(self, img: Tag, url: str) -> Optional[int]:
        """Intenta extraer el número de página."""
        # Buscar en atributos
        for attr in ['data-page', 'data-index', 'data-number']:
            value = img.get(attr)
            if value:
                try:
                    return int(value)
                except ValueError:
                    pass

        # Buscar en la URL
        matches = re.findall(r'/(\d{1,3})\.(?:jpg|jpeg|png|webp)', url)
        if matches:
            return int(matches[-1])

        # Buscar patrón page=N o p=N
        match = re.search(r'[?&](?:page|p)=(\d+)', url)
        if match:
            return int(match.group(1))

        return None

    def _parse_dimension(self, value) -> Optional[int]:
        """Parsea una dimensión a entero."""
        if not value:
            return None
        try:
            if isinstance(value, str):
                value = value.replace('px', '').strip()
            return int(float(value))
        except (ValueError, TypeError):
            return None

    def _get_source_attribute(self, img: Tag) -> str:
        """Determina de qué atributo se obtuvo la URL."""
        for attr in self.LAZY_LOAD_ATTRS:
            if img.get(attr):
                return attr
        return "src"
