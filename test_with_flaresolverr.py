#!/usr/bin/env python3
"""
Script de prueba con FlareSolverr

Antes de ejecutar:
    docker run -d -p 8191:8191 --name flaresolverr flaresolverr/flaresolverr

Uso:
    python test_with_flaresolverr.py
    python test_with_flaresolverr.py "https://tu-url-de-manga.com/capitulo-1"
"""

import sys
import asyncio


def check_flaresolverr():
    """Verifica si FlareSolverr está corriendo."""
    from app.scrapers.flaresolverr import FlareSolverr

    solver = FlareSolverr()
    if solver.is_available():
        print("✅ FlareSolverr está corriendo en http://localhost:8191")
        return True
    else:
        print("❌ FlareSolverr NO está disponible")
        print("")
        print("Para iniciarlo, ejecuta:")
        print("  docker run -d -p 8191:8191 --name flaresolverr flaresolverr/flaresolverr")
        print("")
        print("Verificar que está corriendo:")
        print("  docker ps | grep flaresolverr")
        print("  curl http://localhost:8191/")
        return False


async def test_url(url: str):
    """Prueba el scraping de una URL."""
    from app.scrapers.intelligent_scraper import IntelligentMangaScraper

    print(f"\n{'='*60}")
    print(f"🔍 Probando: {url}")
    print('='*60)

    scraper = IntelligentMangaScraper()
    result = await scraper.scrape(url)

    if result["success"]:
        print(f"\n✅ ¡ÉXITO!")

        analysis = result["analysis"]
        print(f"\n📊 Análisis:")
        print(f"   Tipo detectado: {analysis.detected_type.value}")
        print(f"   Confianza: {analysis.confidence:.1%}")
        print(f"   Dominio: {analysis.site_domain}")
        print(f"   Patrones: {', '.join(analysis.detected_patterns[:5])}")

        if result.get("chapter"):
            chapter = result["chapter"]
            print(f"\n📖 Capítulo encontrado:")
            print(f"   Título: {chapter.title}")
            print(f"   Número: {chapter.chapter_number}")
            print(f"   Total páginas: {chapter.total_pages}")

            if chapter.pages:
                print(f"\n🖼️  Imágenes extraídas:")
                for page in chapter.pages[:10]:
                    url_short = page.image_url[:70] + "..." if len(page.image_url) > 70 else page.image_url
                    print(f"   {page.page_number:3d}. {url_short}")

                if len(chapter.pages) > 10:
                    print(f"   ... y {len(chapter.pages) - 10} más")

            if chapter.navigation:
                nav = chapter.navigation
                print(f"\n🧭 Navegación:")
                if nav.prev_chapter:
                    print(f"   ← Anterior: {nav.prev_chapter[:50]}...")
                if nav.next_chapter:
                    print(f"   → Siguiente: {nav.next_chapter[:50]}...")

        if result.get("series"):
            series = result["series"]
            print(f"\n📚 Serie encontrada:")
            print(f"   Título: {series.title}")
            print(f"   Capítulos: {series.total_chapters}")
            if series.genres:
                print(f"   Géneros: {', '.join(series.genres[:5])}")
    else:
        print(f"\n❌ Error: {result.get('error', 'Error desconocido')}")

    return result


async def main():
    print("🎌 ScrapAni - Prueba con FlareSolverr")
    print("="*60)

    # Verificar FlareSolverr
    flare_ok = check_flaresolverr()

    # URLs de prueba
    if len(sys.argv) > 1:
        test_urls = sys.argv[1:]
    else:
        test_urls = [
            "https://manhwa-latino.com/manga/tokidoki-bosotto-russia-go-de-dereru-tonari-no-alya-san/capitulo-1/",
            "https://es.novelcool.com/chapter/Capitulo-1/12685604/",
        ]

    if not flare_ok:
        print("\n⚠️  Continuando sin FlareSolverr (puede fallar en sitios con Cloudflare)")

    # Probar cada URL
    for url in test_urls:
        try:
            await test_url(url)
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")

    print("\n" + "="*60)
    print("✅ Pruebas completadas")


if __name__ == "__main__":
    asyncio.run(main())
