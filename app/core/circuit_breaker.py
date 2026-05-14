"""
Circuit Breaker pattern для внешних API (CDEK, YooKassa).

Три состояния:
  CLOSED    — нормальная работа; считает ошибки
  OPEN      — fast-fail; не пропускает вызовы recovery_timeout секунд
  HALF_OPEN — один пробный вызов; успех → CLOSED, ошибка → OPEN снова

asyncio.Lock гарантирует корректное изменение состояния
в многозадачном event-loop FastAPI.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Awaitable, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CBState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Выбрасывается при fast-fail (circuit OPEN)."""

    def __init__(self, name: str) -> None:
        super().__init__(f"Circuit '{name}' is OPEN — request rejected (fail-fast)")
        self.cb_name = name


@dataclass
class CircuitBreaker:
    """
    In-process circuit breaker.
    Один экземпляр на интеграцию создаётся при старте процесса.
    """

    name: str
    failure_threshold: int = 5       # кол-во ошибок подряд до размыкания
    success_threshold: int = 2       # успехов из HALF_OPEN для закрытия
    recovery_timeout:  float = 60.0  # секунд в OPEN до следующей пробы

    _state:           CBState = field(default=CBState.CLOSED, init=False, repr=False)
    _failures:        int     = field(default=0,              init=False, repr=False)
    _half_successes:  int     = field(default=0,              init=False, repr=False)
    _opened_at:       float   = field(default=0.0,            init=False, repr=False)
    _lock:       asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _maybe_half_open(self) -> None:
        """Переход OPEN → HALF_OPEN по истечению timeout. Вызывать внутри lock."""
        if (
            self._state == CBState.OPEN
            and time.monotonic() - self._opened_at >= self.recovery_timeout
        ):
            self._state = CBState.HALF_OPEN
            self._half_successes = 0
            logger.info("CircuitBreaker '%s': OPEN → HALF_OPEN (probe window)", self.name)

    def _on_failure(self, exc: Exception) -> None:
        """Регистрирует ошибку и, при необходимости, размыкает цепь. Внутри lock."""
        self._failures += 1
        self._opened_at = time.monotonic()
        if self._state == CBState.HALF_OPEN:
            self._state = CBState.OPEN
            logger.warning(
                "CircuitBreaker '%s': HALF_OPEN → OPEN (probe failed: %s)",
                self.name, exc,
            )
        elif self._failures >= self.failure_threshold:
            self._state = CBState.OPEN
            logger.warning(
                "CircuitBreaker '%s': CLOSED → OPEN (%d consecutive failures)",
                self.name, self._failures,
            )

    def _on_success(self) -> None:
        """Регистрирует успех и при необходимости закрывает цепь. Внутри lock."""
        if self._state == CBState.HALF_OPEN:
            self._half_successes += 1
            if self._half_successes >= self.success_threshold:
                self._state = CBState.CLOSED
                self._failures = 0
                logger.info("CircuitBreaker '%s': HALF_OPEN → CLOSED (recovered)", self.name)
        elif self._state == CBState.CLOSED:
            self._failures = 0  # сбросить счётчик при успехе

    # ── Public API ────────────────────────────────────────────────────────────

    async def call(self, fn: Callable[[], Awaitable[T]]) -> T:
        """
        Выполняет корутину fn() через circuit breaker.
        Бросает CircuitOpenError если цепь разомкнута (fast-fail).
        """
        async with self._lock:
            self._maybe_half_open()
            if self._state == CBState.OPEN:
                raise CircuitOpenError(self.name)

        try:
            result = await fn()
        except CircuitOpenError:
            raise  # не считаем как failure
        except Exception as exc:
            async with self._lock:
                self._on_failure(exc)
            raise

        async with self._lock:
            self._on_success()

        return result

    def status(self) -> dict:
        """Текущее состояние для мониторинга и /health/detailed."""
        return {
            "name":     self.name,
            "state":    self._state.value,
            "failures": self._failures,
        }

    @property
    def is_closed(self) -> bool:
        return self._state == CBState.CLOSED


# ── Глобальные экземпляры (singleton per process) ─────────────────────────────

cdek_cb = CircuitBreaker(
    name="cdek",
    failure_threshold=5,
    recovery_timeout=60.0,
)

yookassa_cb = CircuitBreaker(
    name="yookassa",
    failure_threshold=5,
    recovery_timeout=60.0,
)
