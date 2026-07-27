"""Claude vision adapter — real Anthropic Messages API + mock mode.

Sends the standardized renders plus the measured numbers and asks for a
structured biomechanical read: arch type, pronation/supination, and an estimated
weight-distribution pattern. Pressure points can't be measured from a mesh
without a pressure mat, so we frame this as an *estimate grounded in arch type
and foot shape* (the client's explicit ask), clearly labelled as such.

Mock mode (no ANTHROPIC_API_KEY) returns a deterministic read derived from the
measured arch height, so the pipeline runs end-to-end without a key.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any

from ..config import Settings

_SCHEMA_HINT = {
    "arch_type": "one of: low (pes planus) | neutral | high (pes cavus)",
    "pronation": "one of: pronation | neutral | supination",
    "weight_distribution": "short phrase estimating load pattern (e.g. 'increased medial/forefoot loading')",
    "pressure_zones": "list of likely elevated-pressure regions (e.g. ['heel','1st metatarsal head'])",
    "confidence": "0.0-1.0",
    "notes": "one or two sentences of clinical reasoning",
}

_SYSTEM = (
    "You are a podiatry assistant. From standardized 3D foot renders and measured "
    "geometry, infer biomechanical traits. Pressure/weight distribution is an "
    "ESTIMATE grounded in arch type and foot shape, not a measured pressure map — "
    "say so in notes. Respond with ONLY a JSON object, no prose."
)


def _b64(path: str) -> tuple[str, str]:
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    media = f"image/{'jpeg' if ext in ('jpg','jpeg') else ext}"
    return media, base64.standard_b64encode(open(path, "rb").read()).decode()


def _mock_read(measurements: dict[str, Any]) -> dict[str, Any]:
    arch = measurements.get("arch_height_mm") or 0.0
    length = measurements.get("length_mm") or 1.0
    ratio = arch / length
    if ratio < 0.06:
        arch_type, pron, wd, zones = "low (pes planus)", "pronation", \
            "increased medial arch and forefoot loading", ["medial arch", "1st metatarsal head", "heel"]
    elif ratio > 0.12:
        arch_type, pron, wd, zones = "high (pes cavus)", "supination", \
            "increased lateral and heel/forefoot loading", ["lateral column", "heel", "5th metatarsal head"]
    else:
        arch_type, pron, wd, zones = "neutral", "neutral", \
            "balanced heel-to-forefoot loading", ["heel", "metatarsal heads"]
    return {
        "arch_type": arch_type, "pronation": pron, "weight_distribution": wd,
        "pressure_zones": zones, "confidence": 0.4,
        "notes": ("MOCK read (no ANTHROPIC_API_KEY). Estimated from arch/length "
                  f"ratio {ratio:.3f}; not a measured pressure map."),
        "source": "mock",
    }


def _extract_json(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


class ClaudeVision:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def live(self) -> bool:
        return self.settings.claude_live

    def read_biomechanics(self, render_paths: list[str], measurements: dict[str, Any]) -> dict[str, Any]:
        if not self.live:
            return _mock_read(measurements)

        from anthropic import Anthropic

        prompt = (
            "Analyze this foot. Measured geometry (mm): "
            f"length={measurements.get('length_mm')}, width={measurements.get('width_mm')}, "
            f"arch_height={measurements.get('arch_height_mm')} "
            f"(peak at {measurements.get('arch_peak_fraction')} of length). "
            "Renders follow (plantar, medial, posterior). "
            f"Return JSON with keys: {json.dumps(_SCHEMA_HINT)}"
        )
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for p in render_paths:
            media, data = _b64(p)
            content.append({"type": "image",
                            "source": {"type": "base64", "media_type": media, "data": data}})

        client = Anthropic(api_key=self.settings.anthropic_api_key)
        resp = client.messages.create(
            model=self.settings.claude_model, max_tokens=1024,
            system=_SYSTEM, messages=[{"role": "user", "content": content}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")
        out = _extract_json(text)
        out["source"] = self.settings.claude_model
        return out
