"""Validacion previa a encolar (R2). Funciones puras: faciles de testear y
garantizan que un request invalido nunca llega a RabbitMQ."""
import json
from dataclasses import dataclass

from tp3common import config, imaging


@dataclass
class ValidationError(Exception):
    status: int  # 400 o 413
    code: str
    detail: str


def parse_ops(raw: str) -> list[str]:
    chain = [o.strip().lower() for o in raw.split(",") if o.strip()]
    if not chain:
        raise ValidationError(400, "missing_ops", "Debe indicar al menos una operacion")
    if len(chain) > config.MAX_OPS:
        raise ValidationError(400, "too_many_ops", f"Maximo {config.MAX_OPS} operaciones encadenadas")
    unknown = [o for o in chain if o not in config.ALLOWED_OPS]
    if unknown:
        raise ValidationError(
            400, "unsupported_op",
            f"Operacion(es) no soportada(s): {unknown}. Permitidas: {config.ALLOWED_OPS}",
        )
    return chain


def parse_worker_image(raw: str | None) -> str:
    image = (raw or config.ALLOWED_WORKER_IMAGES[0]).strip()
    if image not in config.ALLOWED_WORKER_IMAGES:
        raise ValidationError(
            400, "worker_image_not_allowed",
            f"Imagen de worker '{image}' no permitida. Permitidas: {config.ALLOWED_WORKER_IMAGES}",
        )
    return image


def parse_params(raw: str | None) -> dict:
    if not raw:
        return {}
    try:
        params = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(400, "invalid_params", f"params no es JSON valido: {exc}") from exc
    if not isinstance(params, dict) or not all(isinstance(v, dict) for v in params.values()):
        raise ValidationError(400, "invalid_params", 'params debe ser {"<op>": {...}}')
    return params


def validate_files(files: list[tuple[str, bytes]]) -> None:
    if not files:
        raise ValidationError(400, "missing_files", "Debe adjuntar al menos un archivo")
    if len(files) > config.MAX_FILES:
        raise ValidationError(400, "too_many_files", f"Maximo {config.MAX_FILES} archivos por request")
    max_bytes = config.MAX_FILE_MB * 1024 * 1024
    for name, data in files:
        if len(data) > max_bytes:
            raise ValidationError(413, "file_too_large", f"'{name}' supera {config.MAX_FILE_MB} MB")
        fmt = imaging.image_format(data)
        if fmt is None:
            raise ValidationError(400, "invalid_image", f"'{name}' no es una imagen valida o esta corrupta")
        if fmt not in config.ALLOWED_FORMATS:
            raise ValidationError(
                400, "unsupported_format", f"'{name}' es {fmt}; permitidos: {config.ALLOWED_FORMATS}"
            )
