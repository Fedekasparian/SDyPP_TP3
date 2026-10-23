"""Genera imagenes PNG de ruido (incompresibles) de los tamaños de V1.

    py TP3/loadtest/gen_images.py                -> todas, en images/{1KB,...,100MB}.png
    py TP3/loadtest/gen_images.py 100MB          -> solo esa, sin tocar las demas

POR QUE ACEPTA UN FILTRO
    Regenerar una imagen cambia los bytes exactos que se subieron en las celdas
    ya medidas. R5 se midio con 10KB.png y 1MB.png, asi que esas no se tocan: el
    filtro permite rehacer solo la que hace falta.

POR QUE EL TAMAÑO SE AJUSTA EN UN BUCLE Y NO DE UNA
    El lado del cuadrado sale de `sqrt(objetivo/3)`, que cuenta 3 bytes por pixel
    (RGB) y supone que el PNG no agrega nada. Pero el PNG de ruido con
    compress_level=1 queda ~5,5% POR ENCIMA de los bytes crudos: cabecera, chunks
    y el filtro por fila que sobre ruido no comprime nada y encima suma un byte
    por scanline. Resultado: cada imagen pesaba un 5% mas que su nombre.

    En los tamaños chicos eso no molesta. En 100MB si: el backend rechaza con 413
    todo archivo que supere MAX_FILE_MB (100 * 1024 * 1024 = 104.857.600 bytes),
    y 100.000.000 "objetivo" terminaban en 105.482.919 bytes reales. Toda la fila
    V1=100MB de la tabla del Hit #3 habria dado 413 en vez de una medicion, y el
    numero no habria dicho nada del sistema: solo que el generador se paso.

    Asi que se encoda, se mide y, si quedo por encima del objetivo, se reduce el
    lado y se vuelve a probar. Son 2 o 3 vueltas.
"""
import io
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SIZES = {"1KB": 1_000, "10KB": 10_000, "100KB": 100_000, "1MB": 1_000_000,
         "10MB": 10_000_000, "100MB": 100_000_000}

pedidas = sys.argv[1:] or list(SIZES)
desconocidas = [n for n in pedidas if n not in SIZES]
if desconocidas:
    sys.exit(f"tamaños desconocidos: {desconocidas}. Validos: {list(SIZES)}")

out_dir = Path(__file__).with_name("images")
out_dir.mkdir(exist_ok=True)
rng = np.random.default_rng(0)

for name in pedidas:
    target = SIZES[name]
    side = max(8, int(math.sqrt(target / 3)))
    for intento in range(1, 9):
        img = rng.integers(0, 256, size=(side, side, 3), dtype=np.uint8)
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG", compress_level=1)
        datos = buf.getvalue()
        if len(datos) <= target or side <= 8:
            break
        # Reducir el lado en la proporcion que sobra, con un 1% de margen para
        # no quedar pegado al limite y tener que iterar de nuevo.
        side = max(8, int(side * math.sqrt(target / len(datos)) * 0.99))
    (out_dir / f"{name}.png").write_bytes(datos)
    print(f"{name}: {side}x{side} -> {len(datos):,} bytes "
          f"({len(datos) / target * 100:.1f}% del objetivo, {intento} intento/s)")
