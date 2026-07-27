"""Vision-LLM foot localisation + crop (Agent 1, pre-reconstruction).

Instead of masking (which strips the background texture photogrammetry needs for
camera alignment), we CROP each frame to the target foot. A crop keeps local
features for alignment while removing the leg, the other foot, and distant
clutter — so the background can't fuse into the foot mesh and width stays real.

The foot is located by the vision LLM (Claude), which is exactly what it is good
at: "find the foot in this photo." Falls back to the full frame if detection
fails, so reconstruction never loses a frame.
"""
from __future__ import annotations

import base64
import json
import os
import re

import cv2

from ..config import Settings
from .imaging import load_bgr

_PROMPT = (
    "This is a podiatry capture; there may be more than one foot. Return ONLY JSON "
    '{"x0":,"y0":,"x1":,"y1":} — the tight bounding box (each value normalized 0-1) '
    "of the SINGLE most prominent foot being scanned (held toward the camera, sole "
    "visible). If no foot is clearly visible return {\"x0\":0,\"y0\":0,\"x1\":1,\"y1\":1}. No prose."
)


def detect_foot_bbox(image_bgr, settings: Settings) -> tuple[float, float, float, float]:
    """Return a normalized (x0,y0,x1,y1) foot box, or the full frame on failure."""
    full = (0.0, 0.0, 1.0, 1.0)
    if not settings.claude_live:
        return full
    from anthropic import Anthropic

    ok, buf = cv2.imencode(".jpg", image_bgr)
    b64 = base64.b64encode(buf).decode()
    try:
        client = Anthropic(api_key=settings.anthropic_api_key)
        resp = client.messages.create(
            model=settings.claude_model, max_tokens=300,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": _PROMPT},
                {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
            ]}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        box = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0))
        x0, y0, x1, y1 = (float(box[k]) for k in ("x0", "y0", "x1", "y1"))
        if 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1 and (x1 - x0) > 0.05 and (y1 - y0) > 0.05:
            return x0, y0, x1, y1
    except Exception:
        pass
    return full


def crop_to_foot(image_path: str, out_dir: str, settings: Settings,
                 margin: float = 0.12, max_dim: int = 1600) -> str:
    """Detect the foot, crop with a margin (keeps alignment context), save JPEG."""
    os.makedirs(out_dir, exist_ok=True)
    bgr = load_bgr(image_path, max_dim=max_dim)
    h, w = bgr.shape[:2]
    x0, y0, x1, y1 = detect_foot_bbox(bgr, settings)
    mx, my = margin * (x1 - x0), margin * (y1 - y0)
    X0 = int(max(0.0, x0 - mx) * w); Y0 = int(max(0.0, y0 - my) * h)
    X1 = int(min(1.0, x1 + mx) * w); Y1 = int(min(1.0, y1 + my) * h)
    crop = bgr[Y0:Y1, X0:X1] if (X1 > X0 and Y1 > Y0) else bgr
    name = os.path.splitext(os.path.basename(image_path))[0] + ".jpg"
    out_path = os.path.join(out_dir, name)
    cv2.imwrite(out_path, crop)
    return out_path


def crop_images_to_foot(paths: list[str], out_dir: str, settings: Settings) -> list[str]:
    return [crop_to_foot(p, out_dir, settings) for p in paths]
