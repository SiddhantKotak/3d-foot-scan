"""Foreground foot isolation (Agent 1 pre-reconstruction step).

Removes floor / chair / clutter from each capture frame before reconstruction so
the background can't fuse into the foot mesh (the cause of the blown-up width).
Uses rembg (U^2-Net) for the segmentation and keeps the largest foreground
component; output is a transparent-background PNG suitable for KIRI with
is_mask=1. Naive colour/skin masking fails here because the light clinic floor
reads as skin — a learned model is required.
"""
from __future__ import annotations

import os

import cv2
import numpy as np
from PIL import Image

from .imaging import load_bgr

_SESSION = None


def _session():
    global _SESSION
    if _SESSION is None:
        from rembg import new_session
        _SESSION = new_session("u2net")
    return _SESSION


def mask_foot_image(path: str, out_dir: str, max_dim: int = 1600) -> str:
    """Isolate the foreground foot/leg; write a transparent-bg PNG, return path."""
    from rembg import remove

    os.makedirs(out_dir, exist_ok=True)
    bgr = load_bgr(path, max_dim=max_dim)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    rgba = np.array(remove(Image.fromarray(rgb), session=_session()))
    alpha = rgba[:, :, 3]

    # keep only the largest foreground blob (drops the far foot / stray patches)
    binary = (alpha > 10).astype("uint8")
    n, labels, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    if n > 1:
        largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        keep = labels == largest
        rgba[~keep] = 0

    name = os.path.splitext(os.path.basename(path))[0] + ".png"
    out_path = os.path.join(out_dir, name)
    Image.fromarray(rgba).save(out_path)
    return out_path


def mask_foot_images(paths: list[str], out_dir: str) -> list[str]:
    return [mask_foot_image(p, out_dir) for p in paths]
