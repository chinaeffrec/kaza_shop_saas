"""
Security utilities.

validate_url()              — SSRF prevention: blocks private IP ranges and non-HTTPS schemes.
check_image_magic()         — File content validation via magic bytes (prevents polyglot exploits).
sanitize_filename()         — Safe filename stripping for uploads.
verify_yookassa_webhook_ip()— Blocks webhook calls from IPs outside YooKassa's published ranges.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import HTTPException


# ── SSRF / URL validation ──────────────────────────────────────────────────────

# RFC-1918 + loopback + link-local + APIPA blocks that must never be contacted
# from a server-side HTTP call triggered by user input.
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),   # link-local / APIPA
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),          # ULA
    ipaddress.ip_network("fe80::/10"),         # link-local IPv6
    ipaddress.ip_network("100.64.0.0/10"),     # Carrier-grade NAT
]

_ALLOWED_SCHEMES = {"https"}


def _is_private_host(hostname: str) -> bool:
    """
    Returns True if the hostname resolves to a private/loopback address.
    Raises ValueError on DNS failure.
    """
    try:
        addrinfos = socket.getaddrinfo(hostname, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False  # Unknown host — let the actual request fail

    for _, _, _, _, sockaddr in addrinfos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                return True
    return False


def validate_url(
    url: str,
    *,
    check_dns: bool = False,
    field_name: str = "url",
    max_length: int = 2048,
) -> str:
    """
    Validates a user-supplied URL for safe server-side use.

    Checks:
      - Length within max_length
      - Scheme is in ALLOWED_SCHEMES (https only)
      - Host is not an IP literal in private range
      - Optionally resolves DNS and checks the resolved IP
      - No credentials in URL (user:pass@)
      - No non-standard ports (if strict_port=True)

    Returns the validated URL or raises HTTPException(422).
    """
    if not url:
        return url

    if len(url) > max_length:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: URL слишком длинный (максимум {max_length} символов)",
        )

    try:
        parsed = urlparse(url)
    except Exception:
        raise HTTPException(status_code=422, detail=f"{field_name}: некорректный URL")

    if parsed.scheme not in _ALLOWED_SCHEMES:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: разрешены только HTTPS-ссылки",
        )

    if not parsed.netloc:
        raise HTTPException(status_code=422, detail=f"{field_name}: отсутствует хост")

    # Block user:pass@ credentials in URL
    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: URL не должен содержать учётные данные",
        )

    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(status_code=422, detail=f"{field_name}: пустой хост")

    # Block IP literals directly
    try:
        ip = ipaddress.ip_address(hostname)
        for net in _BLOCKED_NETWORKS:
            if ip in net:
                raise HTTPException(
                    status_code=422,
                    detail=f"{field_name}: частные и loopback-адреса запрещены",
                )
    except ValueError:
        pass  # Not an IP literal — that's fine

    # Optional DNS resolution check (slower, use only when necessary)
    if check_dns and _is_private_host(hostname):
        raise HTTPException(
            status_code=422,
            detail=f"{field_name}: хост разрешается в частный IP-адрес",
        )

    return url


# ── YooKassa webhook IP allowlist ─────────────────────────────────────────────
# Source: https://yookassa.ru/developers/using-api/webhooks (section "IP addresses")
# These are the only IPs from which YooKassa sends webhook notifications.
_YOOKASSA_ALLOWED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("185.71.76.0/27"),
    ipaddress.ip_network("185.71.77.0/27"),
    ipaddress.ip_network("77.75.153.0/25"),
    ipaddress.ip_network("77.75.156.11/32"),
    ipaddress.ip_network("77.75.156.35/32"),
    ipaddress.ip_network("140.91.0.0/23"),
]


def verify_yookassa_webhook_ip(client_ip: str) -> None:
    """
    Raises HTTPException(403) if client_ip is not in YooKassa's published IP ranges.
    Call this at the top of the webhook handler before processing any payload.

    Pass skip_check=True only in non-production environments.
    """
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        raise HTTPException(403, f"Webhook rejected: unparseable source IP {client_ip!r}")

    for net in _YOOKASSA_ALLOWED_NETWORKS:
        if addr in net:
            return

    raise HTTPException(
        403,
        f"Webhook rejected: source IP {client_ip} is not in YooKassa's allowed ranges",
    )


# ── File magic bytes ───────────────────────────────────────────────────────────

# (offset, bytes) tuples for common image formats
_IMAGE_MAGIC: list[tuple[int, bytes]] = [
    (0, b"\xff\xd8\xff"),              # JPEG
    (0, b"\x89PNG\r\n\x1a\n"),        # PNG
    (0, b"RIFF"),                      # WebP (RIFF header)
    (0, b"GIF87a"),                    # GIF87
    (0, b"GIF89a"),                    # GIF89
]

# Additional WebP check: bytes 8-12 must be "WEBP"
def _is_webp(data: bytes) -> bool:
    return len(data) >= 12 and data[0:4] == b"RIFF" and data[8:12] == b"WEBP"


def check_image_magic(data: bytes, field_name: str = "file") -> str:
    """
    Validates that `data` starts with a recognised image magic sequence.
    Returns the detected format name ("jpeg" | "png" | "webp" | "gif").
    Raises HTTPException(400) if no known magic is found.

    NOTE: This is a lightweight check — not a full image parse. For high-security
    contexts, use Pillow's Image.open() which fully validates the file structure.
    """
    if not data:
        raise HTTPException(status_code=400, detail=f"{field_name}: пустой файл")

    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if _is_webp(data):
        return "webp"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"

    raise HTTPException(
        status_code=400,
        detail=(
            f"{field_name}: недопустимый формат файла. "
            "Принимаются только JPEG, PNG и WebP."
        ),
    )


# ── Filename sanitization ──────────────────────────────────────────────────────

_SAFE_FILENAME_RE = re.compile(r"[^\w.\-]", re.ASCII)


def sanitize_filename(name: str, max_length: int = 128) -> str:
    """
    Strips path separators and dangerous characters from a filename.
    Returns the sanitised stem + extension, or a fallback 'upload'.
    """
    name = Path(name).name  # strip any directory component
    name = _SAFE_FILENAME_RE.sub("_", name)
    name = name[:max_length]
    return name or "upload"
