"""Detect a known-size rectangular reference (A4 sheet) in an image and derive
pixels-per-millimetre.

This proves the reference-marker scale-calibration method. In the client's data
the A4 sheet only appears in the *tracing* images (not the foot-capture frames),
so this runs on those to demonstrate px->mm extraction; the same detector would
scale a photogrammetry mesh if the sheet were placed in the capture frames.

Approach: threshold -> largest external contour -> reduce to a 4-corner quad
(minAreaRect fallback) -> cross-check the long/short edge ratio against A4's
1.414 aspect and require the two edges to agree on px/mm.
"""
from __future__ import annotations

import cv2
import numpy as np

from ..config import A4_MM

A4_ASPECT = A4_MM[1] / A4_MM[0]           # 297 / 210 = 1.414
ASPECT_TOLERANCE = 0.10                    # accept 1.27 .. 1.56
AGREEMENT_TOLERANCE = 0.05                 # long/short px-per-mm must agree within 5%


def _order_quad(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as TL, TR, BR, BL."""
    pts = pts.reshape(4, 2).astype(np.float32)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    return np.array([
        pts[np.argmin(s)],   # top-left  (min x+y)
        pts[np.argmin(d)],   # top-right (min x-y)
        pts[np.argmax(s)],   # bottom-right
        pts[np.argmax(d)],   # bottom-left
    ], dtype=np.float32)


def _largest_quad(image_bgr: np.ndarray) -> np.ndarray | None:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    # A4 paper is the bright region; Otsu separates it from the darker floor.
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    biggest = max(contours, key=cv2.contourArea)
    if cv2.contourArea(biggest) < 0.05 * image_bgr.shape[0] * image_bgr.shape[1]:
        return None
    # Try a clean 4-corner polygon; fall back to the min-area rectangle.
    peri = cv2.arcLength(biggest, True)
    approx = cv2.approxPolyDP(biggest, 0.02 * peri, True)
    if len(approx) == 4:
        return _order_quad(approx)
    rect = cv2.minAreaRect(biggest)
    return _order_quad(cv2.boxPoints(rect))


def detect_a4_px_per_mm(image_path: str) -> dict:
    """Return {ok, px_per_mm, aspect, long_px, short_px, notes}.

    ``ok`` is True only when a plausible A4-shaped quad is found and the two
    edge directions agree on scale.
    """
    img = cv2.imread(image_path)
    if img is None:
        return {"ok": False, "notes": ["could not read image"]}

    quad = _largest_quad(img)
    if quad is None:
        return {"ok": False, "notes": ["no A4-sized bright quad found"]}

    tl, tr, br, bl = quad
    w_top = np.linalg.norm(tr - tl)
    w_bot = np.linalg.norm(br - bl)
    h_left = np.linalg.norm(bl - tl)
    h_right = np.linalg.norm(br - tr)
    short_px = float((w_top + w_bot) / 2)
    long_px = float((h_left + h_right) / 2)
    if short_px > long_px:
        short_px, long_px = long_px, short_px

    aspect = long_px / short_px if short_px else 0.0
    px_per_mm_long = long_px / A4_MM[1]
    px_per_mm_short = short_px / A4_MM[0]
    agreement = abs(px_per_mm_long - px_per_mm_short) / max(px_per_mm_long, 1e-9)

    notes: list[str] = []
    aspect_ok = abs(aspect - A4_ASPECT) <= ASPECT_TOLERANCE * A4_ASPECT
    agree_ok = agreement <= AGREEMENT_TOLERANCE
    if not aspect_ok:
        notes.append(f"aspect {aspect:.3f} off A4 {A4_ASPECT:.3f} (foot may overhang the sheet)")
    if not agree_ok:
        notes.append(f"edge px/mm disagree by {agreement*100:.1f}% (perspective not corrected)")

    return {
        "ok": bool(aspect_ok and agree_ok),
        "px_per_mm": round((px_per_mm_long + px_per_mm_short) / 2, 4),
        "aspect": round(aspect, 4),
        "long_px": round(long_px, 1),
        "short_px": round(short_px, 1),
        "agreement_pct": round(agreement * 100, 2),
        "notes": notes,
    }
