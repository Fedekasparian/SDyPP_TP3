"""Genera imagenes PNG de ruido (incompresibles) de los tamaños de V1.
    python TP3/loadtest/gen_images.py            -> TP3/loadtest/images/{1KB,10KB,...}.png
"""
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image

SIZES = {"1KB": 1_000, "10KB": 10_000, "100KB": 100_000, "1MB": 1_000_000,
         "10MB": 10_000_000, "100MB": 100_000_000}

out_dir = Path(__file__).with_name("images")
out_dir.mkdir(exist_ok=True)
rng = np.random.default_rng(0)
for name, target in SIZES.items():
    side = max(8, int(math.sqrt(target / 3)))
    img = rng.integers(0, 256, size=(side, side, 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="PNG", compress_level=1)
    (out_dir / f"{name}.png").write_bytes(buf.getvalue())
    print(f"{name}: {side}x{side} -> {len(buf.getvalue()):,} bytes")
