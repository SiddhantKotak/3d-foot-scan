"""Node 4 — Vision-LLM biomechanics read (Claude).

Feeds the standardized renders + measured geometry to Claude and gets a
structured biomechanical estimate (arch type, pronation/supination, estimated
weight distribution). Falls back to a deterministic mock if no key is set.
"""
from __future__ import annotations

from ...adapters.claude import ClaudeVision
from ...config import get_settings
from ..state import ScanState

# The 3D renders (skip the 2D overlays) go to the vision model.
_VISION_VIEWS = ("plantar_top", "medial_side", "posterior_heel")


def vision_read(state: ScanState) -> dict:
    settings = get_settings()
    vision = ClaudeVision(settings)
    render_paths = state.get("render_paths", {})
    paths = [render_paths[v] for v in _VISION_VIEWS if v in render_paths]
    measurements = (state.get("geometry") or {}).get("measurements", {})
    read = vision.read_biomechanics(paths, measurements)
    return {"vision": read, "status": "vision_done"}
