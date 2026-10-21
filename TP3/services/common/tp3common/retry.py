"""Retry con backoff exponencial 1s, 2s, 4s, 8s... con tope de 30s (Hit #3).

Nunca reintentar en loop sin espera: genera tormentas de reconexion.
"""
import logging
import time
from typing import Callable, TypeVar

T = TypeVar("T")
log = logging.getLogger("retry")


def backoff_delays(max_delay: float = 30.0):
    delay = 1.0
    while True:
        yield min(delay, max_delay)
        delay *= 2


def retry_with_backoff(
    fn: Callable[[], T], what: str, max_attempts: int = 10, max_delay: float = 30.0
) -> T:
    delays = backoff_delays(max_delay)
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if attempt == max_attempts:
                log.error("%s: fallo definitivo tras %d intentos: %s", what, attempt, exc)
                raise
            wait = next(delays)
            log.warning("%s: intento %d fallo (%s), reintento en %.0fs", what, attempt, exc, wait)
            time.sleep(wait)
    raise RuntimeError("unreachable")
