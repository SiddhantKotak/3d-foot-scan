"""Foot measurements from a canonically-aligned, mm-scaled mesh.

Length/width come from the plantar footprint / silhouette (never the raw bbox,
which can include the leg). Arch height uses multi-slice ray casting across the
35-65% band (the true peak is not at 50%), with a dependency-free section-based
fallback so the node never hard-crashes when ray casting is unavailable.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from .config import (
    ARCH_SCAN_FRACTION, ARCH_SLICE_COUNT, BALL_WIDTH_BAND,
    LENGTH_AXIS, UP_AXIS, WIDTH_AXIS,
)


def _footprint_mask(mesh: trimesh.Trimesh) -> np.ndarray:
    # Relative band only (no absolute mm term) so the selection is scale-
    # invariant: the same vertices are chosen whether the mesh is in metres or
    # millimetres. The sole spans the full heel->toe length at low Y, so the
    # lowest ~30% of height captures the footprint while excluding any leg.
    y = mesh.vertices[:, UP_AXIS]
    thresh = y.min() + 0.30 * (y.max() - y.min())
    return y <= thresh


def measure_length_mm(mesh: trimesh.Trimesh) -> dict[str, Any]:
    """Foot length = Z-extent of the plantar footprint (excludes the leg)."""
    fp = mesh.vertices[_footprint_mask(mesh)]
    z = fp[:, LENGTH_AXIS]
    return {"length_mm": round(float(z.max() - z.min()), 2),
            "heel_z": round(float(z.min()), 2), "toe_z": round(float(z.max()), 2)}


def measure_width_mm(mesh: trimesh.Trimesh, length_mm: float) -> dict[str, Any]:
    """Max width across the ball-of-foot band, from the full silhouette."""
    z = mesh.vertices[:, LENGTH_AXIS]
    z0 = z.min()
    lo, hi = z0 + BALL_WIDTH_BAND[0] * length_mm, z0 + BALL_WIDTH_BAND[1] * length_mm
    best_w, best_frac = 0.0, None
    for zc in np.linspace(lo, hi, 20):
        strip = mesh.vertices[np.abs(z - zc) <= 0.02 * length_mm]
        if len(strip) < 3:
            continue
        w = float(strip[:, WIDTH_AXIS].ptp())
        if w > best_w:
            best_w, best_frac = w, float((zc - z0) / length_mm)
    return {"width_mm": round(best_w, 2), "ball_width_fraction": round(best_frac, 3) if best_frac else None}


def measure_arch_height_mm(
    mesh: trimesh.Trimesh, length_mm: float, engine: str = "ray",
) -> dict[str, Any]:
    """Arch clearance above the floor over the medial midfoot.

    engine='ray'    : cast rays up from below the floor, take the highest sole
                      underside across the 35-65% band (requires rtree/embreex).
    engine='section': vertex lower-envelope fallback (no extra deps).
    """
    z = mesh.vertices[:, LENGTH_AXIS]
    x = mesh.vertices[:, WIDTH_AXIS]
    y = mesh.vertices[:, UP_AXIS]
    z0 = z.min()
    x_mid = float(np.median(x))
    zs = np.linspace(z0 + ARCH_SCAN_FRACTION[0] * length_mm,
                     z0 + ARCH_SCAN_FRACTION[1] * length_mm, ARCH_SLICE_COUNT)

    profile: list[dict[str, float]] = []
    used = engine

    if engine == "ray":
        try:
            xs = np.linspace(x_mid, x.max() * 0.98, 12)  # medial half (+X)
            y_floor = float(y.min()) - 1.0
            for zc in zs:
                origins, dirs = [], []
                for xc in xs:
                    origins.append([xc, y_floor, zc])
                    dirs.append([0.0, 1.0, 0.0])
                locs, ray_idx, _ = mesh.ray.intersects_location(
                    np.asarray(origins), np.asarray(dirs), multiple_hits=True)
                clearance = 0.0
                if len(locs):
                    # per ray: first (lowest positive-Y) hit = sole underside
                    for r in np.unique(ray_idx):
                        yy = locs[ray_idx == r][:, UP_AXIS]
                        yy = yy[yy > 1e-6]
                        if len(yy):
                            clearance = max(clearance, float(yy.min()))
                profile.append({"fraction": round(float((zc - z0) / length_mm), 3),
                                "clearance_mm": round(clearance, 2)})
        except Exception:
            used = "section"
            profile = []

    if used == "section" or not profile:
        used = "section"
        for zc in zs:
            band = mesh.vertices[(np.abs(z - zc) <= 0.02 * length_mm) & (x >= x_mid)]
            clearance = float(band[:, UP_AXIS].min()) if len(band) else 0.0
            profile.append({"fraction": round(float((zc - z0) / length_mm), 3),
                            "clearance_mm": round(max(clearance, 0.0), 2)})

    peak = max(profile, key=lambda p: p["clearance_mm"]) if profile else {"clearance_mm": 0.0, "fraction": None}
    return {
        "arch_height_mm": peak["clearance_mm"],
        "arch_peak_fraction": peak["fraction"],
        "engine": used,
        "per_slice_profile": profile,
    }


def midfoot_cross_section(mesh: trimesh.Trimesh, length_mm: float, at_fraction: float = 0.5) -> dict[str, Any]:
    """The 2D outline where a plane slices the midfoot ('cut the shoe in half')."""
    z0 = mesh.vertices[:, LENGTH_AXIS].min()
    origin = [0.0, 0.0, z0 + at_fraction * length_mm]
    section = mesh.section(plane_origin=origin, plane_normal=[0, 0, 1])
    if section is None:
        return {"available": False}
    v = np.asarray(section.vertices)
    xy = v[:, [WIDTH_AXIS, UP_AXIS]]
    perimeter = float(sum(np.linalg.norm(np.diff(e.discrete(section.vertices), axis=0), axis=1).sum()
                          for e in section.entities))
    return {
        "available": True,
        "at_fraction": at_fraction,
        "width_mm": round(float(xy[:, 0].ptp()), 2),
        "height_mm": round(float(xy[:, 1].ptp()), 2),
        "perimeter_mm": round(perimeter, 2),
        "outline_xy": [[round(float(a), 2), round(float(b), 2)] for a, b in xy],
    }
