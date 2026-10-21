"""Codificacion y particion de imagenes en franjas horizontales con solapamiento."""
import io
from dataclasses import dataclass

import numpy as np
from PIL import Image


def decode(data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(data))
    img = img.convert("L") if img.mode in ("L", "1", "P", "I;16") else img.convert("RGB")
    return np.asarray(img)


def encode_png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="PNG")
    return buf.getvalue()


def image_format(data: bytes) -> str | None:
    """Devuelve el formato (PNG, JPEG...) o None si el archivo no es una imagen valida."""
    try:
        with Image.open(io.BytesIO(data)) as img:
            img.verify()
            return img.format
    except Exception:  # noqa: BLE001
        return None


@dataclass
class Strip:
    index: int
    data: np.ndarray  # franja extendida (incluye el solapamiento)
    pad_top: int  # filas de solapamiento arriba del nucleo
    core_h: int  # filas del nucleo (lo que queda al unir)


def split_strips(img: np.ndarray, n: int, overlap: int) -> list[Strip]:
    h = img.shape[0]
    n = max(1, min(n, h))
    bounds = np.linspace(0, h, n + 1, dtype=int)
    strips = []
    for i in range(n):
        a, b = int(bounds[i]), int(bounds[i + 1])
        ea, eb = max(0, a - overlap), min(h, b + overlap)
        strips.append(Strip(i, img[ea:eb], pad_top=a - ea, core_h=b - a))
    return strips


def crop_core(processed: np.ndarray, pad_top: int, core_h: int) -> np.ndarray:
    return processed[pad_top : pad_top + core_h]


def join_strips(cores: list[np.ndarray]) -> np.ndarray:
    return np.concatenate(cores, axis=0)
