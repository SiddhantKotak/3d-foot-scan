"""Video -> keyframe extraction (interface-only stub for this PoC).

The real implementation samples at a fixed interval and keeps the sharpest frame
per interval (blur score), then the same per-image checks run on the keyframes.
Wired as an interface so the quality-gate node can accept video later without
changing its contract. Images are the supported input path for the PoC.
"""
from __future__ import annotations

import os

import cv2

from .imaging import load_bgr  # noqa: F401  (kept for symmetry / future use)


def extract_keyframes(video_path: str, out_dir: str, interval_s: float = 0.5) -> list[str]:
    """Sample frames every ``interval_s`` seconds, keeping the sharpest per
    interval. Returns saved frame paths. Present but not exercised in the PoC."""
    os.makedirs(out_dir, exist_ok=True)
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(int(fps * interval_s), 1)
    saved: list[str] = []
    idx, best = 0, None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % step == 0 and best is not None:
            path = os.path.join(out_dir, f"frame_{len(saved):04d}.jpg")
            cv2.imwrite(path, best[1])
            saved.append(path)
            best = None
        sharp = cv2.Laplacian(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
        if best is None or sharp > best[0]:
            best = (sharp, frame)
        idx += 1
    cap.release()
    return saved
