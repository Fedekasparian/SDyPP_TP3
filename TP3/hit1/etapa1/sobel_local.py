"""Hit #1, etapa 1: Sobel centralizado.
    python sobel_local.py entrada.png salida.png
"""
import sys
import time
from pathlib import Path

from tp3common import imaging, ops

if __name__ == "__main__":
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    t0 = time.perf_counter()
    img = imaging.decode(src.read_bytes())
    t1 = time.perf_counter()
    out = ops.sobel(img)
    t2 = time.perf_counter()
    dst.write_bytes(imaging.encode_png(out))
    t3 = time.perf_counter()
    print(f"{src.name} {img.shape}: leer {t1 - t0:.3f}s, sobel {t2 - t1:.3f}s, escribir {t3 - t2:.3f}s")
