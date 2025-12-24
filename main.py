"""
ScrapAni - API Inteligente de Scraping para Manga
==================================================

Esta API puede extraer manga de cualquier sitio web de forma inteligente,
detectando automáticamente la estructura del sitio.
"""

import uvicorn
from app import create_app

app = create_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
