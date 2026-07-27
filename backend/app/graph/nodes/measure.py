"""Node 3 — geometry measurement + standardized renders (Agent 2 core).

Calls the geometry package's measure_foot(), which cleans -> scales -> aligns ->
repairs (before ray casting) -> measures -> validates -> renders. Rendering is
folded in here because it needs the same aligned+repaired mesh; the render PNG
paths are surfaced separately in state for the vision node.
"""
from __future__ import annotations

from ...geometry.pipeline import measure_foot
from ...storage import renders_dir
from ..state import ScanState


def measure(state: ScanState) -> dict:
    result = measure_foot(
        state["mesh_path"],
        foot_side=state["foot_side"],
        posture=state.get("posture", "weight_bearing"),
        scale_hint=state.get("scale_hint"),
        out_dir=renders_dir(state["scan_id"]),
        do_render=True,
    )
    d = result.to_dict()
    return {
        "geometry": {k: d[k] for k in ("measurements", "scale", "alignment", "repair", "validation", "warnings", "ok")},
        "render_paths": d["renders"],
        "status": "measured" if d["ok"] else "measurement_low_confidence",
    }
