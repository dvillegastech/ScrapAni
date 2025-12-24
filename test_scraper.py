#!/usr/bin/env python3
"""
Script de prueba para ScrapAni

Ejecuta pruebas básicas del scraper sin necesidad de levantar la API.
"""

import asyncio
import json
from app.scrapers.intelligent_scraper import IntelligentMangaScraper


async def test_scrape(url: str):
    """Prueba el scraping de una URL."""
    print(f"\n{'='*60}")
    print(f"Probando: {url}")
    print('='*60)

    scraper = IntelligentMangaScraper()
    result = await scraper.scrape(url)

    if result["success"]:
        print(f"✅ Scraping exitoso!")
        print(f"\n📊 Análisis:")
        analysis = result["analysis"]
        print(f"   - Tipo detectado: {analysis.detected_type.value}")
        print(f"   - Confianza: {analysis.confidence:.2%}")
        print(f"   - Dominio: {analysis.site_domain}")
        print(f"   - Patrones detectados: {', '.join(analysis.detected_patterns)}")
        print(f"   - Requiere JavaScript: {analysis.requires_javascript}")

        if result.get("chapter"):
            chapter = result["chapter"]
            print(f"\n📖 Capítulo:")
            print(f"   - Título: {chapter.title}")
            print(f"   - Número: {chapter.chapter_number}")
            print(f"   - Total páginas: {chapter.total_pages}")

            if chapter.pages:
                print(f"\n🖼️  Primeras 3 imágenes:")
                for page in chapter.pages[:3]:
                    print(f"   {page.page_number}. {page.image_url[:80]}...")

            if chapter.navigation:
                nav = chapter.navigation
                print(f"\n🧭 Navegación:")
                if nav.next_chapter:
                    print(f"   - Siguiente: {nav.next_chapter[:50]}...")
                if nav.prev_chapter:
                    print(f"   - Anterior: {nav.prev_chapter[:50]}...")

        if result.get("series"):
            series = result["series"]
            print(f"\n📚 Serie:")
            print(f"   - Título: {series.title}")
            print(f"   - Descripción: {(series.description or '')[:100]}...")
            print(f"   - Total capítulos: {series.total_chapters}")
            if series.genres:
                print(f"   - Géneros: {', '.join(series.genres[:5])}")

    else:
        print(f"❌ Error: {result.get('error', 'Error desconocido')}")

    return result


async def main():
    """Función principal de prueba."""
    print("🎌 ScrapAni - Prueba de Scraping Inteligente")
    print("=" * 60)

    # URLs de prueba (puedes agregar más)
    test_urls = [
        # Agrega aquí URLs para probar
        # "https://ejemplo.com/manga/titulo/capitulo-1",
    ]

    if not test_urls:
        print("\n⚠️  No hay URLs de prueba configuradas.")
        print("Edita este archivo y agrega URLs al array 'test_urls'")
        print("\nEjemplo de uso directo:")
        print('  python -c "import asyncio; from test_scraper import test_scrape; asyncio.run(test_scrape(\'https://tu-url.com\'))"')
        return

    for url in test_urls:
        try:
            await test_scrape(url)
        except Exception as e:
            print(f"❌ Error procesando {url}: {e}")

    print("\n" + "=" * 60)
    print("✅ Pruebas completadas")


if __name__ == "__main__":
    asyncio.run(main())
