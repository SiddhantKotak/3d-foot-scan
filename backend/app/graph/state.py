"""Shared LangGraph state.

One TypedDict threaded through every node; each node reads what it needs and
returns a partial update. This object IS the audit trail — the SQLite
checkpointer persists it after every node, keyed by thread_id (== scan_id).
"""
from __future__ import annotations

from typing import Any, Literal

from typing_extensions import TypedDict


class ScanState(TypedDict, total=False):
    # inputs
    scan_id: str
    image_paths: list[str]
    foot_side: Literal["left", "right"]
    posture: Literal["weight_bearing", "non_weight_bearing"]
    scale_hint: dict[str, Any] | None

    # node outputs
    quality: dict[str, Any]          # quality-gate verdict
    serialize: str                   # KIRI task id (committed before await)
    model_url: str                   # KIRI download link (from webhook/poller)
    mesh_path: str                   # local reconstructed mesh
    geometry: dict[str, Any]         # measurements + scale + validation + repair
    render_paths: dict[str, str]     # standardized render PNG paths
    vision: dict[str, Any]           # Claude biomechanics read
    review: dict[str, Any]           # podiatrist decision (from interrupt resume)
    insole_spec: dict[str, Any]      # final spec (placeholder for Agent 3/4)

    # control / audit
    status: str
    errors: list[str]
