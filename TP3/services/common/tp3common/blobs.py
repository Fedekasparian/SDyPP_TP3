"""Imagenes en un bucket; en Redis y en los mensajes viaja solo el puntero (URI).

Redis guarda estado chico (hashes, sets, contadores). Con las imagenes adentro, la
memoria crece con el tamaño de los archivos y termina en OOMKilled; un bucket no
tiene ese techo y Redis queda acotado por cantidad de jobs, no por bytes.

Backends (BLOB_BACKEND):
    gcs    Google Cloud Storage. En GKE y en las VMs workers autentica con la identidad
           del pod/VM (sin claves). Con STORAGE_EMULATOR_HOST usa el emulador
           fake-gcs-server (docker compose) y crea el bucket si no existe.
    local  Directorio BLOB_DIR (tests y corridas sin nube). URIs file://.

Objetos:
    jobs/{id}/in/{file}            archivo original
    jobs/{id}/frag/{file}/{n}/in   fragmento de entrada (PNG)
    jobs/{id}/frag/{file}/{n}/out  fragmento procesado (PNG)
    jobs/{id}/out/{file}           resultado final (PNG)
La regla de lifecycle del bucket (Terraform) borra los objetos al dia, igual que el
TTL de 24 h de las claves del job en Redis.
"""
import os
import pathlib
import threading
from urllib.parse import urlparse
from urllib.request import url2pathname

from . import config
from .retry import retry_with_backoff


class BlobNotFound(Exception):
    pass


class BlobUnavailable(Exception):
    """El bucket no respondio tras los reintentos (el backend lo traduce a 503)."""


def input_name(job_id: str, file_idx: int) -> str:
    return f"jobs/{job_id}/in/{file_idx}"


def frag_name(job_id: str, file_idx: int, frag_idx: int, kind: str) -> str:
    return f"jobs/{job_id}/frag/{file_idx}/{frag_idx}/{kind}"


def output_name(job_id: str, file_idx: int) -> str:
    return f"jobs/{job_id}/out/{file_idx}"


class LocalStore:
    scheme = "file"

    def __init__(self, root: str):
        self.root = pathlib.Path(root).resolve()

    def put(self, name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, path)  # atomico: un lector nunca ve un archivo a medio escribir
        return path.as_uri()

    def get(self, uri: str) -> bytes:
        path = pathlib.Path(url2pathname(urlparse(uri).path))
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise BlobNotFound(uri) from exc


class GCSStore:
    scheme = "gs"

    def __init__(self, bucket: str):
        from google.api_core import exceptions as gexc
        from google.cloud import storage

        self._gexc = gexc
        if os.getenv("STORAGE_EMULATOR_HOST"):
            from google.auth.credentials import AnonymousCredentials

            self.client = storage.Client(project="tp3-local", credentials=AnonymousCredentials())
            self.bucket = self.client.bucket(bucket)
            if not self.bucket.exists():
                try:
                    self.client.create_bucket(bucket)
                except gexc.Conflict:
                    pass  # otro servicio lo creo primero
        else:
            self.client = storage.Client()
            self.bucket = self.client.bucket(bucket)
        self.transient = (gexc.ServiceUnavailable, gexc.InternalServerError, gexc.TooManyRequests,
                          gexc.GatewayTimeout, ConnectionError, TimeoutError)

    def put(self, name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        blob = self.bucket.blob(name)
        # Escribir el mismo objeto dos veces deja el mismo contenido: reintentar es seguro.
        try:
            retry_with_backoff(lambda: blob.upload_from_string(data, content_type=content_type),
                               "gcs", max_attempts=5, exceptions=self.transient)
        except (self._gexc.GoogleAPIError, *self.transient) as exc:
            raise BlobUnavailable(name) from exc
        return f"gs://{self.bucket.name}/{name}"

    def get(self, uri: str) -> bytes:
        parsed = urlparse(uri)
        blob = self.client.bucket(parsed.netloc).blob(parsed.path.lstrip("/"))
        try:
            return retry_with_backoff(blob.download_as_bytes, "gcs", max_attempts=5,
                                      exceptions=self.transient)
        except self._gexc.NotFound as exc:
            raise BlobNotFound(uri) from exc
        except (self._gexc.GoogleAPIError, *self.transient) as exc:
            raise BlobUnavailable(uri) from exc


_store = None
_lock = threading.Lock()


def get_store():
    """Un cliente por proceso (el de GCS es thread-safe y reusa conexiones)."""
    global _store
    with _lock:
        if _store is None:
            if config.BLOB_BACKEND == "gcs":
                if not config.BLOB_BUCKET:
                    raise RuntimeError("BLOB_BACKEND=gcs requiere BLOB_BUCKET")
                _store = GCSStore(config.BLOB_BUCKET)
            elif config.BLOB_BACKEND == "local":
                _store = LocalStore(config.BLOB_DIR)
            else:
                raise RuntimeError(f"BLOB_BACKEND desconocido: {config.BLOB_BACKEND}")
        return _store


def reset_store(store=None) -> None:
    """Para tests: reemplazar el backend o forzar a que se relea la configuracion."""
    global _store
    with _lock:
        _store = store


def put(name: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    return get_store().put(name, data, content_type)


def get(uri: str) -> bytes:
    return get_store().get(uri)
