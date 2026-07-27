"""Agent 1 — Image Quality Gate.

Rejects input that geometrically cannot produce a good 3D scan, before any paid
reconstruction runs. Per-image checks are pure OpenCV; the batch-level coverage
check is a cheap heuristic (foot-skin presence + view diversity) standing in for
the pose/keypoint + object-detection models described in the brief — the bar is
intentionally low: catch scans that cannot work, not grade good ones.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import cv2
import numpy as np

from .imaging import load_bgr

# --- thresholds (empirical, tunable) ---
# Calibrated on the real batches at load_bgr's 1024px downscale: 40 usable foot
# photos span variance 40-103 (smooth plantar skin is inherently low-texture),
# so the doc's "<100" example rejects everything. Genuine motion blur drops
# well below 30; that is the floor that catches unusable scans.
BLUR_MIN_VAR = 30.0           # variance of Laplacian; below => too blurry
EXPOSURE_EXTREME_FRAC = 0.25  # reject if >25% of pixels are crushed-black/blown-out
SKIN_MIN_FRAC = 0.02          # need at least ~2% skin pixels => a foot is present
MIN_IMAGES = 8                # need enough angles for photogrammetry
DUP_CORRELATION = 0.985       # histogram corr above this => effectively the same view


@dataclass
class ImageVerdict:
    path: str
    passed: bool
    blur_var: float
    dark_frac: float
    bright_frac: float
    skin_frac: float
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _blur_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _exposure_fracs(gray: np.ndarray) -> tuple[float, float]:
    hist = cv2.calcHist([gray], [0], None, [256], [0, 256]).ravel()
    total = gray.size
    dark = float(hist[:13].sum() / total)     # lowest ~5%
    bright = float(hist[243:].sum() / total)  # highest ~5%
    return dark, bright


def _skin_frac(bgr: np.ndarray) -> float:
    ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
    mask = cv2.inRange(ycrcb, (0, 133, 77), (255, 173, 127))
    return float(np.count_nonzero(mask) / mask.size)


def _hue_hist(bgr: np.ndarray) -> np.ndarray:
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 2], None, [16, 16], [0, 180, 0, 256])
    return cv2.normalize(h, h).flatten()


def check_image(path: str) -> tuple[ImageVerdict, np.ndarray]:
    bgr = load_bgr(path)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    blur = _blur_variance(gray)
    dark, bright = _exposure_fracs(gray)
    skin = _skin_frac(bgr)

    reasons: list[str] = []
    if blur < BLUR_MIN_VAR:
        reasons.append(f"blurry (Laplacian var {blur:.0f} < {BLUR_MIN_VAR:.0f})")
    if dark > EXPOSURE_EXTREME_FRAC:
        reasons.append(f"underexposed ({dark*100:.0f}% crushed-black)")
    if bright > EXPOSURE_EXTREME_FRAC:
        reasons.append(f"overexposed ({bright*100:.0f}% blown-out)")
    if skin < SKIN_MIN_FRAC:
        reasons.append(f"no foot detected (skin {skin*100:.1f}% < {SKIN_MIN_FRAC*100:.0f}%)")

    verdict = ImageVerdict(path, not reasons, round(blur, 1), round(dark, 4),
                           round(bright, 4), round(skin, 4), reasons)
    return verdict, _hue_hist(bgr)


def _distinct_views(hists: list[np.ndarray]) -> int:
    """Greedy count of distinct views: an image starts a new cluster unless it
    correlates strongly with an existing cluster representative."""
    reps: list[np.ndarray] = []
    for h in hists:
        if not any(cv2.compareHist(h, r, cv2.HISTCMP_CORREL) > DUP_CORRELATION for r in reps):
            reps.append(h)
    return len(reps)


def run_quality_gate(image_paths: list[str]) -> dict[str, Any]:
    """Return a batch verdict: per-image results + coverage + overall pass/fail."""
    verdicts: list[ImageVerdict] = []
    hists: list[np.ndarray] = []
    for p in image_paths:
        try:
            v, h = check_image(p)
        except Exception as e:
            v = ImageVerdict(p, False, 0.0, 0.0, 0.0, 0.0, [f"decode failed: {e}"])
            h = None
        verdicts.append(v)
        if h is not None:
            hists.append(h)

    accepted = [v for v in verdicts if v.passed]
    distinct = _distinct_views(hists) if hists else 0

    batch_reasons: list[str] = []
    if len(accepted) < MIN_IMAGES:
        batch_reasons.append(f"only {len(accepted)} usable images (need >= {MIN_IMAGES})")
    if distinct < MIN_IMAGES:
        batch_reasons.append(
            f"only ~{distinct} distinct viewpoints (need >= {MIN_IMAGES}); "
            "looks like repeated shots of the same angle")

    return {
        "ok": not batch_reasons,
        "n_input": len(image_paths),
        "n_accepted": len(accepted),
        "n_rejected": len(verdicts) - len(accepted),
        "distinct_viewpoints": distinct,
        "batch_reasons": batch_reasons,
        "images": [v.to_dict() for v in verdicts],
    }
