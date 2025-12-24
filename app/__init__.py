"""
ScrapAni Application Package
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router


def create_app() -> FastAPI:
    """Crea y configura la aplicación FastAPI."""

    app = FastAPI(
        title="ScrapAni",
        description="API Inteligente de Scraping para Manga - Extrae manga de cualquier sitio automáticamente",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Registrar routers
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/")
    async def root():
        return {
            "name": "ScrapAni",
            "description": "API Inteligente de Scraping para Manga",
            "docs": "/docs",
            "version": "1.0.0"
        }

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    return app
