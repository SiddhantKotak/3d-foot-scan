"""Node 1 — Image Quality Gate (Agent 1).

Rejects bad input before any paid reconstruction. On failure it records the
verdict and sets status='rejected'; a conditional edge then routes straight to
END so nothing downstream runs.
"""
from __future__ import annotations

from ...quality_gate.checks import run_quality_gate
from ..state import ScanState


def quality_gate(state: ScanState) -> dict:
    result = run_quality_gate(state["image_paths"])
    return {
        "quality": result,
        "status": "quality_passed" if result["ok"] else "rejected",
    }


def route_after_quality(state: ScanState) -> str:
    """Conditional edge target."""
    return "submit_reconstruction" if state.get("status") == "quality_passed" else "__end__"
