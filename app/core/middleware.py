"""
Security middleware + observability middleware.

TraceIDMiddleware       — инжектирует X-Request-ID / uuid4 в ContextVar trace_id_var
                          (используется структурированным логером).
HTTPSRedirectMiddleware — редирект HTTP → HTTPS в продакшене.
SecurityHeadersMiddleware — стандартные security-заголовки.
MaxBodySizeMiddleware   — отклоняет запросы с Content-Length выше лимита.
"""
import re
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from app.logging_setup import trace_id_var

# Endpoints that accept large uploads (media archives up to 512 MB).
# MaxBodySizeMiddleware skips the body-size check for these paths.
_LARGE_UPLOAD_PATHS = ("/api/v1/import",)

# UUID v4 format: 8-4-4-4-12 hex digits, or any alphanumeric+dash up to 36 chars.
# Rejects newlines, control chars, and anything that could break JSON log entries.
_TRACE_ID_RE = re.compile(r"^[a-zA-Z0-9\-]{1,36}$")


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Читает X-Request-ID из входящего заголовка (nginx / upstream proxy),
    или генерирует uuid4 если заголовок отсутствует.
    Записывает trace_id в ContextVar — все логи этого запроса получат его.
    Добавляет X-Request-ID в ответ для трейсинга на клиенте.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        raw = request.headers.get("X-Request-ID", "")
        # Accept only safe characters to prevent log injection / JSON log poisoning.
        trace_id = raw if raw and _TRACE_ID_RE.match(raw) else str(uuid.uuid4())
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


class MaxBodySizeMiddleware:
    """
    Rejects requests whose Content-Length header exceeds max_bytes.

    Uses header inspection only — does NOT buffer the request body, so there
    is no memory overhead. nginx client_max_body_size enforces the real limit
    at the transport layer; this middleware is defence-in-depth for direct
    access to port 8000 (bot → app, internal network) and acts as an early
    rejection gate to avoid wasting app-worker time on oversized requests.

    Import paths (_LARGE_UPLOAD_PATHS) are excluded because they legitimately
    accept ZIP archives up to 512 MB.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = 32 * 1024 * 1024) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            path: str = scope.get("path", "")
            if not any(path.startswith(p) for p in _LARGE_UPLOAD_PATHS):
                headers: dict[bytes, bytes] = dict(scope.get("headers", []))
                cl = headers.get(b"content-length")
                if cl:
                    try:
                        if int(cl) > self.max_bytes:
                            response = JSONResponse(
                                {"detail": (
                                    f"Тело запроса слишком большое. "
                                    f"Максимум {self.max_bytes // 1024 // 1024} МБ."
                                )},
                                status_code=413,
                            )
                            await response(scope, receive, send)
                            return
                    except (ValueError, TypeError):
                        pass
        await self.app(scope, receive, send)
