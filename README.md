# ScrapAni 🎌

**API Inteligente de Scraping para Manga**

ScrapAni es una API que puede extraer manga de **cualquier sitio web** de forma inteligente, detectando automáticamente la estructura del sitio sin necesidad de configuración específica.

## ✨ Características

- **Scraping Inteligente**: Detecta automáticamente el tipo de contenido (páginas de manga, lista de capítulos, info de serie)
- **Multi-sitio**: Funciona con cualquier sitio de manga sin necesidad de adaptadores específicos
- **Detección de Patrones**: Usa heurísticas avanzadas para identificar imágenes de manga vs UI
- **Soporte JavaScript**: Opción de usar navegador real para sitios con contenido dinámico
- **API REST**: Interfaz simple y documentada con FastAPI
- **Descarga**: Endpoints para descargar capítulos como ZIP o lista de URLs

## 🚀 Instalación

```bash
# Clonar el repositorio
git clone https://github.com/your-username/ScrapAni.git
cd ScrapAni

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Linux/Mac
# o
.\venv\Scripts\activate  # Windows

# Instalar dependencias
pip install -r requirements.txt

# (Opcional) Para soporte de sitios con JavaScript pesado
pip install playwright
playwright install chromium
```

## 🏃 Ejecución

```bash
# Iniciar el servidor
python main.py

# O con uvicorn directamente
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

La API estará disponible en `http://localhost:8000`

- Documentación interactiva: `http://localhost:8000/docs`
- Documentación alternativa: `http://localhost:8000/redoc`

## 📖 Uso de la API

### Scraping Básico

```bash
# Extraer un capítulo de manga
curl -X POST "http://localhost:8000/api/v1/scrape/" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://ejemplo-manga.com/manga/one-piece/chapter-1"}'
```

### Respuesta

```json
{
  "success": true,
  "url": "https://ejemplo-manga.com/manga/one-piece/chapter-1",
  "analysis": {
    "detected_type": "manga_page",
    "confidence": 0.85,
    "site_domain": "ejemplo-manga.com",
    "detected_patterns": ["multiple_large_images", "chapter_navigation"],
    "requires_javascript": false
  },
  "chapter": {
    "title": "Chapter 1: Romance Dawn",
    "chapter_number": "1",
    "pages": [
      {"page_number": 1, "image_url": "https://..."},
      {"page_number": 2, "image_url": "https://..."}
    ],
    "total_pages": 54,
    "navigation": {
      "next_chapter": "https://ejemplo-manga.com/manga/one-piece/chapter-2",
      "prev_chapter": null
    }
  }
}
```

### Endpoints Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/v1/scrape/` | POST | Scraping completo de una URL |
| `/api/v1/scrape/quick` | GET | Scraping rápido por parámetros |
| `/api/v1/scrape/chapter` | POST | Extraer solo páginas del capítulo |
| `/api/v1/scrape/series` | POST | Extraer info de la serie |
| `/api/v1/scrape/images` | POST | Extraer solo URLs de imágenes |
| `/api/v1/analyze/` | POST | Analizar URL sin extraer contenido |
| `/api/v1/download/prepare` | POST | Preparar descarga (obtener URLs) |
| `/api/v1/download/zip` | POST | Descargar capítulo como ZIP |
| `/api/v1/download/urls` | GET | Obtener URLs en texto plano |

### Ejemplos con Python

```python
import httpx

# Scraping básico
response = httpx.post(
    "http://localhost:8000/api/v1/scrape/",
    json={"url": "https://manga-site.com/manga/titulo/cap-1"}
)
data = response.json()

# Obtener solo las imágenes
if data["success"] and data.get("chapter"):
    for page in data["chapter"]["pages"]:
        print(f"Página {page['page_number']}: {page['image_url']}")
```

```python
# Para sitios con JavaScript
response = httpx.post(
    "http://localhost:8000/api/v1/scrape/",
    json={
        "url": "https://manga-site.com/manga/titulo/cap-1",
        "use_browser": True  # Usar navegador real
    }
)
```

### Ejemplo con cURL

```bash
# Analizar una URL
curl "http://localhost:8000/api/v1/analyze/quick?url=https://manga-site.com/manga/titulo"

# Obtener solo URLs de imágenes como texto plano
curl "http://localhost:8000/api/v1/download/urls?url=https://manga-site.com/manga/titulo/cap-1"

# Descargar como ZIP
curl -X POST "http://localhost:8000/api/v1/download/zip" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://manga-site.com/manga/titulo/cap-1", "filename_prefix": "one-piece-ch1"}' \
  -o chapter.zip
```

## 🧠 Cómo Funciona

ScrapAni usa un sistema de **detección inteligente** basado en heurísticas:

### 1. Análisis de Tipo de Contenido

El sistema analiza la página para determinar si es:
- **Página de lectura**: Contiene las imágenes del manga
- **Lista de capítulos**: Lista con enlaces a capítulos
- **Info de serie**: Información de la serie (sinopsis, géneros, etc.)

### 2. Detección de Imágenes de Manga

Para identificar qué imágenes son páginas de manga, el sistema evalúa:
- **Patrones de URL**: `/chapter/`, `/page/`, nombres numéricos
- **Dimensiones**: Las páginas de manga suelen ser grandes (>600px ancho)
- **Contexto CSS**: Clases como `.page`, `.manga`, `.reader`
- **Lazy loading**: Atributos como `data-src` típicos de readers
- **Posición en el DOM**: Imágenes dentro de contenedores de lectura

### 3. Detección de Navegación

Busca enlaces de navegación usando:
- Patrones de texto: "Next", "Siguiente", "Previous", "Anterior"
- Clases CSS: `.next-chapter`, `.prev-chapter`
- Iconos: `>>`, `<<`, `→`, `←`
- Soporte multiidioma: Español, Inglés, Japonés, Coreano

### 4. Extracción de Capítulos

Para listas de capítulos:
- Detecta contenedores de lista (`.chapter-list`, etc.)
- Analiza patrones de URL de capítulos
- Extrae metadatos: número, fecha, estado

## 🔧 Configuración Avanzada

### Variables de Entorno

```bash
# Timeout para requests (segundos)
SCRAPER_TIMEOUT=30

# Puerto del servidor
PORT=8000

# Modo debug
DEBUG=true
```

### Personalizar Headers

El scraper usa headers realistas por defecto, pero puedes personalizarlos:

```python
from app.scrapers import IntelligentMangaScraper

scraper = IntelligentMangaScraper()
scraper.DEFAULT_HEADERS["User-Agent"] = "Mi User Agent"
```

## 📁 Estructura del Proyecto

```
ScrapAni/
├── main.py                 # Punto de entrada
├── requirements.txt        # Dependencias
├── app/
│   ├── __init__.py        # Factory de la app FastAPI
│   ├── api/
│   │   ├── __init__.py
│   │   └── endpoints/
│   │       ├── scrape.py  # Endpoints de scraping
│   │       ├── analyze.py # Endpoints de análisis
│   │       └── download.py# Endpoints de descarga
│   ├── scrapers/
│   │   ├── intelligent_scraper.py  # Scraper principal
│   │   └── browser_scraper.py      # Scraper con Playwright
│   ├── detectors/
│   │   ├── image_detector.py       # Detector de imágenes
│   │   ├── navigation_detector.py  # Detector de navegación
│   │   └── chapter_detector.py     # Detector de capítulos
│   ├── models/
│   │   └── schemas.py     # Modelos Pydantic
│   └── utils/
│       └── helpers.py     # Funciones auxiliares
```

## ⚠️ Notas Importantes

1. **Uso Responsable**: Esta herramienta es para uso educativo y personal. Respeta los términos de servicio de los sitios web.

2. **Rate Limiting**: Algunos sitios pueden bloquear IPs que hacen muchas solicitudes. Considera agregar delays entre requests.

3. **JavaScript**: Para sitios que cargan contenido dinámicamente, usa `use_browser=true`. Esto es más lento pero más preciso.

4. **No todos los sitios funcionarán**: Algunos sitios tienen protecciones anti-scraping avanzadas (Cloudflare, etc.) que pueden bloquear el acceso.

## 🤝 Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el repositorio
2. Crea una rama para tu feature (`git checkout -b feature/nueva-caracteristica`)
3. Commit tus cambios (`git commit -m 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/nueva-caracteristica`)
5. Abre un Pull Request

## 📄 Licencia

MIT License - ver [LICENSE](LICENSE) para más detalles.
