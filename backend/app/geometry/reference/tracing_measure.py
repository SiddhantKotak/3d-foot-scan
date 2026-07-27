"""Measure foot length & width directly from an A4 foot-tracing image.

The tracing is a weight-bearing 2D outline on a known-size sheet, so it is the
right METRIC source for length/width — more trustworthy than a marginal 3D
reconstruction. Steps: detect the A4 → perspective-rectify to real millimetres →
isolate the traced foot outline (adaptive threshold, since the pen line is faint
and the paper is unevenly lit) → measure its bounding box.

ACCURACY: on the sample phone-photo tracings this lands within ~10-25 mm (right
foot length was exact). Reaching the ±1-2 mm clinical bar needs a proper
document-scan pipeline (deskew, robust binarisation of faint ink, stroke
tracing). The clinician's *written* dimensions on the sheet are also available as
an authoritative value (OCR / manual entry). Treated as approximate + flagged.
"""
from __future__ import annotations

import cv2
import numpy as np

from .a4_scale import _largest_quad
from ..config import A4_MM

PX_PER_MM = 4.0  # rectified resolution


def measure_tracing(image_path: str) -> dict:
    """Return {ok, length_mm, width_mm, approximate, notes} from an A4 tracing."""
    img = cv2.imread(image_path)
    if img is None:
        return {"ok": False, "notes": ["could not read image"]}
    quad = _largest_quad(img)
    if quad is None:
        return {"ok": False, "notes": ["no A4 sheet detected"]}

    # rectify the A4 to a canonical portrait sheet at PX_PER_MM
    w_px, h_px = int(A4_MM[0] * PX_PER_MM), int(A4_MM[1] * PX_PER_MM)
    dst = np.array([[0, 0], [w_px - 1, 0], [w_px - 1, h_px - 1], [0, h_px - 1]], np.float32)
    warp = cv2.warpPerspective(img, cv2.getPerspectiveTransform(quad.astype(np.float32), dst),
                               (w_px, h_px))

    gray = cv2.cvtColor(warp, cv2.COLOR_BGR2GRAY)
    # adaptive threshold catches the faint pen line despite uneven paper shading
    ink = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                cv2.THRESH_BINARY_INV, 51, 10)
    m = int(10 * PX_PER_MM)
    ink[:m, :] = 0; ink[-m:, :] = 0; ink[:, :m] = 0; ink[:, -m:] = 0
    conn = cv2.dilate(ink, np.ones((int(4 * PX_PER_MM),) * 2, np.uint8))  # bridge broken strokes

    n, labels, stats, _ = cv2.connectedComponentsWithStats(conn, 8)
    best = None  # foot-shaped (aspect 1.8-3.6) largest component
    for i in range(1, n):
        w, h, area = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
        aspect = max(w, h) / max(min(w, h), 1)
        if 1.8 <= aspect <= 3.6 and area > int(30 * PX_PER_MM) ** 2:
            if best is None or area > best[0]:
                best = (area, i)
    if best is None:
        return {"ok": False, "notes": ["no foot-shaped outline found inside the sheet"]}

    tight = (labels == best[1]) & (ink > 0)   # tight bbox from ORIGINAL ink
    ys, xs = np.where(tight)
    length_mm = (ys.max() - ys.min()) / PX_PER_MM
    width_mm = (xs.max() - xs.min()) / PX_PER_MM
    ok = 200 <= length_mm <= 320 and 60 <= width_mm <= 135
    return {
        "ok": ok,
        "length_mm": round(length_mm, 1),
        "width_mm": round(width_mm, 1),
        "approximate": True,
        "source": "a4_tracing (weight-bearing, metric)",
        "notes": ["approximate (~±10-25 mm); clinical accuracy needs a document-scan pipeline "
                  "or the clinician's written dimensions"],
    }
