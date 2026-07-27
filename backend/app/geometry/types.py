"""Structured result types for the geometry core.

Everything here is JSON-serialisable (via ``asdict``) so a LangGraph node can
drop the results straight into shared state.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

FootSide = Literal["left", "right"]
Posture = Literal["weight_bearing", "non_weight_bearing"]


@dataclass
class ScaleResult:
    mm_per_unit: float          # multiply mesh coords by this -> millimetres
    method: str                 # "lidar_metric" | "reference_marker" | "manual" | "unresolved"
    confidence: float           # 0..1
    reliable: bool              # False => downstream numbers are shape-only, not metric
    source_detail: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ValidationReport:
    foot_side: str
    gt_length_mm: float
    gt_width_mm: float
    meas_length_mm: float
    meas_width_mm: float
    length_dev_mm: float        # signed: measured - ground truth
    width_dev_mm: float
    tolerance_mm: float
    within_tolerance: bool      # both |dev| <= tolerance
    scale_reliable: bool
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeometryResult:
    ok: bool                                    # gate for the podiatrist-review node
    measurements: dict[str, Any] = field(default_factory=dict)
    scale: dict[str, Any] = field(default_factory=dict)
    alignment: dict[str, Any] = field(default_factory=dict)
    repair: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] | None = None
    renders: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
