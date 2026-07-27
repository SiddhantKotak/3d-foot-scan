"""Scale calibration + accuracy validation.

This is the pipeline's #1 failure mode: photogrammetry recovers *shape*, not
*size*. Nothing downstream can catch a scale error, so we make it explicit and
auditable here.

Two supply paths, both returning a single ``mm_per_unit`` factor:
  * LiDAR / metric      -> trust device units (mesh already in real units)
  * reference marker    -> known-size object in frame -> real/measured ratio

If neither is available (the client's foot photos have no in-frame reference),
we return an *unresolved* scale flagged ``reliable=False`` so every downstream
number is labelled shape-only, and we still validate the mesh *shape* against
the tracing ground truth to quantify how close a best-fit scale would land.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from .config import CLINICAL_TOLERANCE_MM
from .reference.ground_truth import GROUND_TRUTH_MM
from .types import ScaleResult, ValidationReport


def _mm_per_unit_for_units(units: str | None) -> float | None:
    return {"m": 1000.0, "meter": 1000.0, "meters": 1000.0,
            "cm": 10.0, "mm": 1.0, "millimeter": 1.0}.get((units or "").lower())


def resolve_scale(mesh: trimesh.Trimesh, scale_hint: dict[str, Any] | None) -> ScaleResult:
    """Decide a ``mm_per_unit`` factor from the caller's hint.

    scale_hint examples:
      {"method": "lidar",  "declared_units": "m"}
      {"method": "marker", "px_per_mm": 6.5, "measured_units": ..., ...}
      {"method": "manual", "mm_per_unit": 1000.0}
      None  -> unresolved (shape-only)
    """
    hint = scale_hint or {}
    method = hint.get("method")

    if method == "manual" and hint.get("mm_per_unit"):
        return ScaleResult(float(hint["mm_per_unit"]), "manual", 1.0, True,
                           {"source": "operator override"})

    if method == "lidar":
        mm = _mm_per_unit_for_units(hint.get("declared_units"))
        if mm is not None:
            return ScaleResult(mm, "lidar_metric", 0.9, True,
                               {"declared_units": hint.get("declared_units")})

    if method == "marker" and hint.get("mm_per_unit"):
        # Caller measured the marker in mesh units and computed real/measured.
        return ScaleResult(float(hint["mm_per_unit"]), "reference_marker",
                           float(hint.get("confidence", 0.75)), True,
                           {k: hint[k] for k in ("px_per_mm", "marker_type") if k in hint})

    # No usable scale source: shape-only. mm_per_unit=1 keeps coordinates finite;
    # `reliable=False` tells everyone the metric is untrustworthy.
    return ScaleResult(
        1.0, "unresolved", 0.0, False,
        {"reason": "no in-frame size reference and no LiDAR units"},
        notes=[
            "No scale reference in the capture frames -> mesh is unitless.",
            "Fix: place an A4 sheet or credit card beside the foot, or capture "
            "with LiDAR depth.",
        ],
    )


def best_fit_scale_to_ground_truth(length_units: float, foot_side: str) -> float:
    """The scale factor that would make measured length match the GT length.

    Only for the *unresolved* demo path: lets us report how faithful the mesh
    *shape* is once anchored, without pretending we recovered true scale.
    """
    gt = GROUND_TRUTH_MM[foot_side]["length"]
    return gt / length_units if length_units else 1.0


def validate_against_tracing(
    meas_length_mm: float,
    meas_width_mm: float,
    foot_side: str,
    scale_reliable: bool,
    tolerance_mm: float = CLINICAL_TOLERANCE_MM,
) -> ValidationReport:
    """Signed mm deviation of measured length/width vs the A4-tracing GT."""
    gt = GROUND_TRUTH_MM[foot_side]
    len_dev = meas_length_mm - gt["length"]
    wid_dev = meas_width_mm - gt["width"]
    notes: list[str] = []
    if not scale_reliable:
        notes.append(
            "Scale unresolved: deviations reflect best-fit shape anchoring, "
            "not recovered metric scale."
        )
    notes.append(
        "Tracing is weight-bearing; a non-weight-bearing scan will differ most "
        "in arch height and heel width."
    )
    return ValidationReport(
        foot_side=foot_side,
        gt_length_mm=gt["length"], gt_width_mm=gt["width"],
        meas_length_mm=round(meas_length_mm, 2), meas_width_mm=round(meas_width_mm, 2),
        length_dev_mm=round(len_dev, 2), width_dev_mm=round(wid_dev, 2),
        tolerance_mm=tolerance_mm,
        within_tolerance=bool(abs(len_dev) <= tolerance_mm and abs(wid_dev) <= tolerance_mm),
        scale_reliable=scale_reliable,
        notes=notes,
    )
