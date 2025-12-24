"""
Módulo de integración con FlareSolverr para bypass de Cloudflare.

FlareSolverr es un servidor proxy que resuelve challenges de Cloudflare
usando un navegador real.

Uso:
    docker run -d -p 8191:8191 --name flaresolverr flaresolverr/flaresolverr
"""

import httpx
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class FlareSolverrResponse:
    """Respuesta de FlareSolverr"""
    status: str
    message: str
    solution: Optional[Dict[str, Any]] = None
    html: Optional[str] = None
    cookies: Optional[list] = None
    user_agent: Optional[str] = None


class FlareSolverr:
    """
    Cliente para FlareSolverr.

    FlareSolverr resuelve challenges de Cloudflare automáticamente
    usando un navegador headless.
    """

    def __init__(self, host: str = "http://localhost:8191"):
        """
        Inicializa el cliente.

        Args:
            host: URL del servidor FlareSolverr
        """
        self.host = host.rstrip("/")
        self.endpoint = f"{self.host}/v1"

    def is_available(self) -> bool:
        """Verifica si FlareSolverr está disponible."""
        try:
            response = httpx.get(f"{self.host}/", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get(
        self,
        url: str,
        max_timeout: int = 60000,
        cookies: Optional[list] = None,
    ) -> FlareSolverrResponse:
        """
        Obtiene una página resolviendo el challenge de Cloudflare.

        Args:
            url: URL a obtener
            max_timeout: Timeout máximo en ms
            cookies: Cookies opcionales a enviar

        Returns:
            FlareSolverrResponse con el HTML y cookies
        """
        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": max_timeout,
        }

        if cookies:
            payload["cookies"] = cookies

        try:
            response = httpx.post(
                self.endpoint,
                json=payload,
                timeout=max_timeout / 1000 + 10,  # Agregar margen
            )
            data = response.json()

            if data.get("status") == "ok":
                solution = data.get("solution", {})
                return FlareSolverrResponse(
                    status="ok",
                    message=data.get("message", "Success"),
                    solution=solution,
                    html=solution.get("response"),
                    cookies=solution.get("cookies"),
                    user_agent=solution.get("userAgent"),
                )
            else:
                return FlareSolverrResponse(
                    status="error",
                    message=data.get("message", "Unknown error"),
                )

        except httpx.TimeoutException:
            return FlareSolverrResponse(
                status="error",
                message="Timeout esperando respuesta de FlareSolverr",
            )
        except httpx.ConnectError:
            return FlareSolverrResponse(
                status="error",
                message="No se pudo conectar a FlareSolverr. ¿Está corriendo? docker run -p 8191:8191 flaresolverr/flaresolverr",
            )
        except Exception as e:
            return FlareSolverrResponse(
                status="error",
                message=f"Error: {str(e)}",
            )

    def create_session(self, session_id: str = "scrapani") -> bool:
        """
        Crea una sesión persistente en FlareSolverr.

        Las sesiones mantienen cookies entre requests.
        """
        try:
            response = httpx.post(
                self.endpoint,
                json={
                    "cmd": "sessions.create",
                    "session": session_id,
                },
                timeout=30,
            )
            return response.json().get("status") == "ok"
        except Exception:
            return False

    def destroy_session(self, session_id: str = "scrapani") -> bool:
        """Destruye una sesión."""
        try:
            response = httpx.post(
                self.endpoint,
                json={
                    "cmd": "sessions.destroy",
                    "session": session_id,
                },
                timeout=10,
            )
            return response.json().get("status") == "ok"
        except Exception:
            return False

    def get_with_session(
        self,
        url: str,
        session_id: str = "scrapani",
        max_timeout: int = 60000,
    ) -> FlareSolverrResponse:
        """
        Obtiene una página usando una sesión persistente.

        Útil para mantener cookies entre múltiples requests.
        """
        payload = {
            "cmd": "request.get",
            "url": url,
            "session": session_id,
            "maxTimeout": max_timeout,
        }

        try:
            response = httpx.post(
                self.endpoint,
                json=payload,
                timeout=max_timeout / 1000 + 10,
            )
            data = response.json()

            if data.get("status") == "ok":
                solution = data.get("solution", {})
                return FlareSolverrResponse(
                    status="ok",
                    message="Success",
                    solution=solution,
                    html=solution.get("response"),
                    cookies=solution.get("cookies"),
                    user_agent=solution.get("userAgent"),
                )
            else:
                return FlareSolverrResponse(
                    status="error",
                    message=data.get("message", "Unknown error"),
                )
        except Exception as e:
            return FlareSolverrResponse(
                status="error",
                message=str(e),
            )


# Instancia global para uso fácil
flaresolverr = FlareSolverr()


def fetch_with_flaresolverr(url: str, timeout: int = 60000) -> Optional[str]:
    """
    Función helper para obtener HTML usando FlareSolverr.

    Args:
        url: URL a obtener
        timeout: Timeout en ms

    Returns:
        HTML de la página o None si falla
    """
    if not flaresolverr.is_available():
        print("⚠️  FlareSolverr no está disponible.")
        print("   Ejecuta: docker run -d -p 8191:8191 flaresolverr/flaresolverr")
        return None

    result = flaresolverr.get(url, max_timeout=timeout)

    if result.status == "ok":
        return result.html
    else:
        print(f"❌ FlareSolverr error: {result.message}")
        return None
