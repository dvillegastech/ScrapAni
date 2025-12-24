"""
Browser Scraper para sitios con JavaScript pesado

Usa Playwright para renderizar páginas que requieren JavaScript
para mostrar el contenido.
"""

import asyncio
from typing import Optional, Dict, Any
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from app.scrapers.intelligent_scraper import IntelligentMangaScraper


class BrowserScraper:
    """
    Scraper que usa un navegador real (Playwright) para obtener
    contenido de páginas que requieren JavaScript.
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        """
        Inicializa el browser scraper.

        Args:
            headless: Ejecutar navegador sin interfaz gráfica
            timeout: Timeout en milisegundos
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright no está instalado. "
                "Ejecuta: pip install playwright && playwright install chromium"
            )

        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self._intelligent_scraper = IntelligentMangaScraper()

    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()

    async def start(self):
        """Inicia el navegador."""
        self._playwright = await async_playwright().start()
        self.browser = await self._playwright.chromium.launch(
            headless=self.headless,
        )

    async def close(self):
        """Cierra el navegador."""
        if self.browser:
            await self.browser.close()
        if hasattr(self, '_playwright'):
            await self._playwright.stop()

    async def scrape(self, url: str, wait_for_images: bool = True) -> Dict[str, Any]:
        """
        Scrape una página usando el navegador.

        Args:
            url: URL a scrapear
            wait_for_images: Esperar a que carguen las imágenes

        Returns:
            Diccionario con los datos extraídos
        """
        if not self.browser:
            await self.start()

        try:
            # Crear nueva página
            page = await self.browser.new_page()

            # Configurar headers
            await page.set_extra_http_headers({
                "Accept-Language": "en-US,en;q=0.9",
            })

            # Navegar a la URL
            await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)

            # Esperar un poco para que cargue el contenido dinámico
            await asyncio.sleep(2)

            # Si necesitamos esperar por imágenes
            if wait_for_images:
                await self._wait_for_manga_images(page)

            # Scroll para cargar lazy content
            await self._scroll_page(page)

            # Obtener el HTML renderizado
            html = await page.content()

            # Cerrar página
            await page.close()

            # Usar el scraper inteligente con el HTML renderizado
            soup = BeautifulSoup(html, 'lxml')

            # Reutilizar la lógica del scraper inteligente
            analysis = self._intelligent_scraper._analyze_content_type(soup, url)
            analysis.requires_javascript = True  # Marcamos que se usó JS

            from app.models.schemas import ContentType

            result = {
                "success": True,
                "url": url,
                "analysis": analysis,
            }

            if analysis.detected_type == ContentType.MANGA_PAGE:
                chapter = self._intelligent_scraper._extract_chapter(soup, url)
                result["chapter"] = chapter
            elif analysis.detected_type in [ContentType.CHAPTER_LIST, ContentType.SERIES_INFO]:
                series = self._intelligent_scraper._extract_series_info(soup, url)
                result["series"] = series
            else:
                # Intentar extraer capítulo de todas formas
                chapter = self._intelligent_scraper._extract_chapter(soup, url)
                if chapter and chapter.pages:
                    result["chapter"] = chapter

            return result

        except Exception as e:
            return {
                "success": False,
                "url": url,
                "error": f"Error en browser scraping: {str(e)}"
            }

    async def _wait_for_manga_images(self, page: Page, max_wait: int = 10):
        """
        Espera a que carguen las imágenes de manga.

        Args:
            page: Página de Playwright
            max_wait: Máximo tiempo de espera en segundos
        """
        try:
            # Esperar a que haya al menos algunas imágenes cargadas
            await page.wait_for_function(
                """
                () => {
                    const images = document.querySelectorAll('img');
                    let loaded = 0;
                    for (const img of images) {
                        if (img.complete && img.naturalWidth > 100) {
                            loaded++;
                        }
                    }
                    return loaded >= 3;
                }
                """,
                timeout=max_wait * 1000,
            )
        except Exception:
            # Si timeout, continuamos con lo que tenemos
            pass

    async def _scroll_page(self, page: Page):
        """
        Hace scroll en la página para cargar contenido lazy.

        Args:
            page: Página de Playwright
        """
        try:
            # Obtener altura de la página
            height = await page.evaluate("document.body.scrollHeight")

            # Scroll gradual
            current = 0
            step = 500
            while current < height:
                await page.evaluate(f"window.scrollTo(0, {current})")
                await asyncio.sleep(0.3)
                current += step

                # Actualizar altura por si cargó más contenido
                new_height = await page.evaluate("document.body.scrollHeight")
                if new_height > height:
                    height = new_height

            # Volver arriba
            await page.evaluate("window.scrollTo(0, 0)")

        except Exception:
            pass

    async def get_page_screenshot(self, url: str) -> Optional[bytes]:
        """
        Obtiene un screenshot de la página.

        Args:
            url: URL de la página

        Returns:
            Bytes del screenshot en PNG
        """
        if not self.browser:
            await self.start()

        try:
            page = await self.browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)
            screenshot = await page.screenshot(full_page=True)
            await page.close()
            return screenshot
        except Exception:
            return None
