"""
Funciones auxiliares para ScrapAni
"""

import re
from urllib.parse import urlparse, urljoin
from typing import Optional


# Extensiones de imagen comunes
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.bmp'}

# Patrones de CDN de imágenes de manga conocidos
MANGA_IMAGE_PATTERNS = [
    r'/manga/',
    r'/chapters?/',
    r'/pages?/',
    r'/images?/',
    r'/uploads?/',
    r'/cdn/',
    r'/img/',
    r'/scans?/',
    r'\d{2,3}\.(jpg|jpeg|png|webp)',  # Archivos numerados
]


def normalize_url(url: str, base_url: Optional[str] = None) -> str:
    """
    Normaliza una URL, convirtiéndola en absoluta si es necesario.

    Args:
        url: URL a normalizar
        base_url: URL base para resolver URLs relativas

    Returns:
        URL normalizada
    """
    if not url:
        return ""

    url = url.strip()

    # Si la URL empieza con //, agregar https:
    if url.startswith('//'):
        return 'https:' + url

    # Si es una URL relativa y tenemos base_url
    if base_url and not url.startswith(('http://', 'https://')):
        return urljoin(base_url, url)

    return url


def get_domain(url: str) -> str:
    """
    Extrae el dominio de una URL.

    Args:
        url: URL completa

    Returns:
        Dominio (ej: "manga-site.com")
    """
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        # Remover www. si está presente
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def is_image_url(url: str) -> bool:
    """
    Determina si una URL apunta a una imagen.

    Args:
        url: URL a verificar

    Returns:
        True si parece ser una imagen
    """
    if not url:
        return False

    url_lower = url.lower()

    # Verificar extensión
    parsed = urlparse(url_lower)
    path = parsed.path

    for ext in IMAGE_EXTENSIONS:
        if path.endswith(ext):
            return True

    # Verificar parámetros de imagen en query string
    if any(x in url_lower for x in ['format=', 'image', '.jpg', '.png', '.webp']):
        return True

    return False


def is_manga_image_url(url: str) -> float:
    """
    Calcula la probabilidad de que una URL sea una imagen de manga.

    Args:
        url: URL a verificar

    Returns:
        Score de 0 a 1
    """
    if not is_image_url(url):
        return 0.0

    score = 0.3  # Base score por ser imagen
    url_lower = url.lower()

    # Verificar patrones de manga
    for pattern in MANGA_IMAGE_PATTERNS:
        if re.search(pattern, url_lower):
            score += 0.15

    # Bonus si tiene números secuenciales en el nombre
    if re.search(r'/\d{1,3}\.(jpg|jpeg|png|webp)', url_lower):
        score += 0.2

    # Bonus si está en un CDN típico de manga
    if any(cdn in url_lower for cdn in ['cdn', 'img', 'images', 'uploads']):
        score += 0.1

    return min(score, 1.0)


def clean_text(text: str) -> str:
    """
    Limpia texto removiendo espacios extra y caracteres especiales.

    Args:
        text: Texto a limpiar

    Returns:
        Texto limpiado
    """
    if not text:
        return ""

    # Remover espacios múltiples y saltos de línea
    text = re.sub(r'\s+', ' ', text)
    # Remover espacios al inicio y final
    text = text.strip()

    return text


def extract_number_from_string(text: str) -> Optional[str]:
    """
    Extrae el primer número de un string.

    Args:
        text: Texto del que extraer el número

    Returns:
        Número como string o None
    """
    if not text:
        return None

    # Buscar números (incluyendo decimales)
    match = re.search(r'(\d+(?:\.\d+)?)', text)
    if match:
        return match.group(1)

    return None


def extract_chapter_number(text: str) -> Optional[str]:
    """
    Extrae el número de capítulo de un texto.

    Args:
        text: Texto (ej: "Chapter 123", "Cap. 45", "Ch 67")

    Returns:
        Número del capítulo
    """
    if not text:
        return None

    # Patrones comunes para capítulos
    patterns = [
        r'(?:chapter|cap(?:itulo)?|ch)[\s.:_-]*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*(?:章|화)',  # Japonés/Coreano
        r'#(\d+(?:\.\d+)?)',
        r'ep(?:isode)?[\s.:_-]*(\d+(?:\.\d+)?)',
    ]

    text_lower = text.lower()

    for pattern in patterns:
        match = re.search(pattern, text_lower)
        if match:
            return match.group(1)

    # Fallback: buscar cualquier número
    return extract_number_from_string(text)


def similarity_score(text1: str, text2: str) -> float:
    """
    Calcula un score de similitud simple entre dos textos.

    Args:
        text1: Primer texto
        text2: Segundo texto

    Returns:
        Score de 0 a 1
    """
    if not text1 or not text2:
        return 0.0

    text1 = text1.lower()
    text2 = text2.lower()

    if text1 == text2:
        return 1.0

    # Palabras en común
    words1 = set(text1.split())
    words2 = set(text2.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)
