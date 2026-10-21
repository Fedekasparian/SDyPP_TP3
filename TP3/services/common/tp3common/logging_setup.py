"""Logging en memoria (ring buffer) + stdout + archivo rotativo en disco."""
import logging
import os
from collections import deque
from logging.handlers import RotatingFileHandler

from . import config

_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_memory: deque[str] = deque(maxlen=500)


class _MemoryHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _memory.append(self.format(record))


def recent_logs(n: int = 100) -> list[str]:
    return list(_memory)[-n:]


def setup_logging(service: str, level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger()
    if getattr(root, "_tp3_configured", False):
        return logging.getLogger(service)
    root.setLevel(level)
    fmt = logging.Formatter(_FORMAT)
    handlers: list[logging.Handler] = [logging.StreamHandler(), _MemoryHandler()]
    try:
        os.makedirs(config.LOG_DIR, exist_ok=True)
        handlers.append(
            RotatingFileHandler(
                os.path.join(config.LOG_DIR, f"{service}.log"), maxBytes=5_000_000, backupCount=3
            )
        )
    except OSError:
        pass  # sin disco escribible (p.ej. tests): seguimos con stdout + memoria
    for h in handlers:
        h.setFormatter(fmt)
        root.addHandler(h)
    for noisy in ("pika", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    root._tp3_configured = True  # type: ignore[attr-defined]
    return logging.getLogger(service)
