"""
Security middleware:
- TrustedHostMiddleware: блокирует запросы с неизвестным Host-заголовком
- SecurityHeadersMiddleware: добавляет стандартные security-заголовки
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Добавляет security-заголовки ко всем ответам.

    Для /media/ (статические файлы-изображения) CSP не добавляется -
    он не влияет на отображение изображений, но может сбивать браузер.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        # CSP только для API-ответов, не для медиафайлов и не для health-check.
        # Медиафайлы - бинарные изображения, CSP на них бесполезен и иногда
        # мешает браузерам в нестандартных режимах.
        if not request.url.path.startswith("/media/") and request.url.path != "/health":
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        return response
