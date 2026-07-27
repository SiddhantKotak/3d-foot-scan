"""Image decoding helpers shared by the quality gate.

HEIC (iPhone default) needs pillow-heif to decode; we register it once and load
everything through PIL so the gate accepts HEIC/JPEG/PNG uniformly.
"""
from __future__ import annotations

import numpy as np

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    _HEIC = True
except Exception:  # pragma: no cover
    _HEIC = False

from PIL import Image


def load_bgr(path: str, max_dim: int = 1024) -> np.ndarray:
    """Load any supported image as an OpenCV BGR ndarray, downscaled so quality
    metrics are resolution-independent (a 4032px photo and a 1024px one get
    comparable Laplacian-variance / histogram readings)."""
    img = Image.open(path).convert("RGB")
    if max(img.size) > max_dim:
        scale = max_dim / max(img.size)
        img = img.resize((int(img.size[0] * scale), int(img.size[1] * scale)))
    rgb = np.asarray(img)
    return rgb[:, :, ::-1].copy()  # RGB -> BGR


def heic_supported() -> bool:
    return _HEIC
