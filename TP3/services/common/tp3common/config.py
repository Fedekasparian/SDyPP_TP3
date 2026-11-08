"""Configuracion por variables de entorno (ver .env.example en la raiz)."""
import os


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@localhost:5672/")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
AUTH_SECRET = os.getenv("AUTH_SECRET", "")

# Las imagenes van a un bucket; Redis guarda solo el puntero (ver blobs.py).
BLOB_BACKEND = os.getenv("BLOB_BACKEND", "local")
BLOB_BUCKET = os.getenv("BLOB_BUCKET", "")
BLOB_DIR = os.getenv("BLOB_DIR", "/tmp/tp3-blobs")

# R2: lo que se acepta se configura, no se programa.
ALLOWED_OPS = _list("ALLOWED_OPS", "sobel,grayscale,blur,threshold")
ALLOWED_WORKER_IMAGES = _list("ALLOWED_WORKER_IMAGES", "tp3-worker")
ALLOWED_FORMATS = _list("ALLOWED_FORMATS", "PNG,JPEG,BMP")
MAX_FILE_MB = float(os.getenv("MAX_FILE_MB", "10"))
MAX_FILES = int(os.getenv("MAX_FILES", "50"))
MAX_OPS = int(os.getenv("MAX_OPS", "5"))
RATE_LIMIT_PER_MIN = int(os.getenv("RATE_LIMIT_PER_MIN", "600"))

FRAGMENTS_PER_IMAGE = int(os.getenv("FRAGMENTS_PER_IMAGE", "4"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))

# Nombre del pool de workers que atiende este proceso (= routing key / imagen de worker).
WORKER_POOL = os.getenv("WORKER_POOL", "tp3-worker")

LOG_DIR = os.getenv("LOG_DIR", "/var/log/tp3")
HEALTH_PORT = int(os.getenv("HEALTH_PORT", "8080"))
