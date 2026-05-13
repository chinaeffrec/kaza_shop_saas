"""
Симметричное шифрование чувствительных полей БД (bot_token).

Ключ Fernet (32 байта) выводится из SECRET_KEY через SHA-256.
Это значит:
  - при смене SECRET_KEY все зашифрованные токены станут нечитаемыми
  - SECRET_KEY должен быть зафиксирован до первой записи в БД
  - ротация ключа требует re-encrypt всех строк (отдельная утилита)
"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    secret = get_settings().secret_key
    if not secret:
        raise RuntimeError("SECRET_KEY must be set to use field encryption")
    # SHA-256 даёт ровно 32 байта — именно столько нужно Fernet
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key_bytes))


def encrypt_field(value: str) -> str:
    """Шифрует строку, возвращает base64-url строку для хранения в БД."""
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt_field(encrypted: str) -> str:
    """
    Дешифрует строку из БД.
    Raises ValueError если токен повреждён или ключ сменился.
    """
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt field: invalid token or wrong key") from exc
