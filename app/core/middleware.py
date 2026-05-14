"""
Security middleware + observability middleware.

TraceIDMiddleware     — инжектирует X-Request-ID / uuid4 в ContextVar trace_id_var
                        (используется структурированным логером).
HTTPSRedirectMiddleware — редирект HTTP → HTTPS в продакшене.
SecurityHeadersMiddleware — стандартные security-заголовки.
"""
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from app.logging_setup import trace_id_var


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Читает X-Request-ID из входящего заголовка (nginx / upstream proxy),
    или генерирует uuid4 если заголовок отсутствует.
    Записывает trace_id в ContextVar — все логи этого запроса получат его.
    Добавляет X-Request-ID в ответ для трейсинга на клиенте.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        trace_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = trace_id_var.set(trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = trace_id
            return response
        finally:
            trace_id_var.reset(token)


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """
    Перенаправляет HTTP → HTTPS в продакшене.
    Пропускает запросы с X-Forwarded-Proto: https (за reverse proxy) и
    health-check (/health) чтобы не ломать liveness probe.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # За nginx/Cloudflare — смотрим на forwarded proto
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if (
            request.url.scheme == "http"
            and forwarded_proto != "https"
            and request.url.path != "/health"
        ):
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=301)
        return await call_next(request)


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
        # HSTS включается если запрос пришёл по HTTPS или за HTTPS proxy
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "")
        if request.url.scheme == "https" or forwarded_proto == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        path = request.url.path
        # Skip CSP for static media (doesn't apply to binary assets)
        if not path.startswith("/media/") and path != "/health":
            if path.startswith("/api/v1/miniapp"):
                # Mini App embeds in Telegram WebView; needs relaxed CSP.
                # eval is explicitly forbidden even here — Telegram WebView
                # doesn't require it and many XSS payloads rely on it.
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "connect-src 'self' https://api.telegram.org; "
                    "frame-ancestors https://web.telegram.org"
                )
            else:
                # All other API responses: strict deny-all
                response.headers["Content-Security-Policy"] = (
                    "default-src 'none'; frame-ancestors 'none'"
                )
        return response
