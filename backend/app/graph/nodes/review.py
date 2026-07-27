"""Node 5 — Human-in-the-loop podiatrist review (dynamic interrupt).

Pauses the run and surfaces the measurements, validation, renders and vision
read to the app. The podiatrist approves or edits; the graph resumes via
Command(resume=decision) on the same thread_id, and this node then assembles the
insole spec (a placeholder for the future Agent 3 report / Agent 4 CAD steps).

Interrupt discipline: the node is side-effect-free before interrupt(), and the
single interrupt() call is unconditional, so a resume replays the node top
cleanly and returns the decision.
"""
from __future__ import annotations

from langgraph.types import interrupt

from ..state import ScanState


def _build_insole_spec(state: ScanState, decision: dict) -> dict:
    geom = state.get("geometry") or {}
    m = geom.get("measurements", {})
    vision = state.get("vision") or {}
    edits = (decision or {}).get("edits") or {}
    length = edits.get("length_mm", m.get("length_mm"))
    width = edits.get("width_mm", m.get("width_mm"))
    arch = edits.get("arch_height_mm", m.get("arch_height_mm"))
    return {
        "foot_side": state.get("foot_side"),
        "approved": bool((decision or {}).get("approved")),
        "length_mm": length,
        "width_mm": width,
        "arch_height_mm": arch,
        "arch_type": vision.get("arch_type"),
        "arch_support": vision.get("weight_distribution"),
        "note": "Placeholder spec; Agent 3 (report) and Agent 4 (CAD/.stl) are future phases.",
    }


def review(state: ScanState) -> dict:
    decision = interrupt({
        "kind": "podiatrist_review",
        "measurements": (state.get("geometry") or {}).get("measurements"),
        "validation": (state.get("geometry") or {}).get("validation"),
        "warnings": (state.get("geometry") or {}).get("warnings"),
        "vision": state.get("vision"),
        "render_paths": state.get("render_paths"),
    })
    return {
        "review": decision,
        "insole_spec": _build_insole_spec(state, decision),
        "status": "approved" if (decision or {}).get("approved") else "reviewed",
    }
