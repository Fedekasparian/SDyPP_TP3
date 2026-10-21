"""Operaciones de imagen (R2). Para agregar una operacion: escribirla, registrarla
en OPS y en NEIGHBORHOOD, y sumarla a ALLOWED_OPS en la config.

Todas reciben y devuelven np.ndarray uint8 (HxW o HxWx3). Ninguna normaliza por
el maximo de la imagen: eso haria que cada fragmento quede distinto al unirlos.
"""
from typing import Callable

import numpy as np

SOBEL_X = np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype=np.float32)
SOBEL_Y = SOBEL_X.T
BOX = np.full((3, 3), 1 / 9, dtype=np.float32)


def _conv3(g: np.ndarray, k: np.ndarray) -> np.ndarray:
    """Convolucion 3x3 sobre una imagen 2D float, con borde replicado."""
    h, w = g.shape
    p = np.pad(g, 1, mode="edge")
    out = np.zeros((h, w), dtype=np.float32)
    for i in range(3):
        for j in range(3):
            if k[i, j]:
                out += k[i, j] * p[i : i + h, j : j + w]
    return out


def grayscale(img: np.ndarray, **_) -> np.ndarray:
    if img.ndim == 2:
        return img
    rgb = img[..., :3].astype(np.float32)
    return np.clip(rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32), 0, 255).astype(np.uint8)


def sobel(img: np.ndarray, **_) -> np.ndarray:
    g = grayscale(img).astype(np.float32)
    mag = np.hypot(_conv3(g, SOBEL_X), _conv3(g, SOBEL_Y))
    return np.clip(mag, 0, 255).astype(np.uint8)


def blur(img: np.ndarray, **_) -> np.ndarray:
    if img.ndim == 2:
        return np.clip(_conv3(img.astype(np.float32), BOX), 0, 255).astype(np.uint8)
    chans = [_conv3(img[..., c].astype(np.float32), BOX) for c in range(img.shape[2])]
    return np.clip(np.stack(chans, axis=-1), 0, 255).astype(np.uint8)


def threshold(img: np.ndarray, threshold: int = 128, **_) -> np.ndarray:
    return np.where(grayscale(img) >= int(threshold), 255, 0).astype(np.uint8)


OPS: dict[str, Callable[..., np.ndarray]] = {
    "sobel": sobel,
    "grayscale": grayscale,
    "blur": blur,
    "threshold": threshold,
}

# Pixeles de vecindad que necesita cada operacion (define el solapamiento al partir).
NEIGHBORHOOD = {"sobel": 1, "grayscale": 0, "blur": 1, "threshold": 0}


def required_overlap(ops: list[str]) -> int:
    return sum(NEIGHBORHOOD[o] for o in ops)


def apply_chain(img: np.ndarray, ops: list[str], params: dict | None = None) -> np.ndarray:
    params = params or {}
    for name in ops:
        img = OPS[name](img, **params.get(name, {}))
    return img
