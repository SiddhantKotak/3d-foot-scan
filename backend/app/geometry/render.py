"""Standardized 2D renders of the aligned mesh for the Vision LLM.

Only matplotlib's Agg backend renders reliably headless (no display, no GL), so
we use it deliberately instead of pyvista/open3d. The camera poses are fixed in
the canonical frame so the LLM sees the same orientation every time.
"""
from __future__ import annotations

import os
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402
import numpy as np                        # noqa: E402
import trimesh                            # noqa: E402

from .config import LENGTH_AXIS, RENDER_PX, UP_AXIS, WIDTH_AXIS  # noqa: E402

# (elev, azim) per standardized view, in the canonical frame.
_VIEWS = {
    "plantar_top": (90, -90),
    "medial_side": (0, 0),
    "posterior_heel": (0, -90),
}


def _shaded_facecolors(mesh: trimesh.Trimesh) -> np.ndarray:
    light = np.array([0.3, 0.8, 0.5]); light /= np.linalg.norm(light)
    inten = np.clip(mesh.face_normals @ light, 0.2, 1.0)
    base = np.array([0.86, 0.72, 0.64])   # skin-ish
    return np.clip(inten[:, None] * base, 0, 1)


def _autocrop(path: str, pad: int = 18, thresh: int = 244) -> None:
    """Trim the white matplotlib margins so the foot fills the frame.

    3D axes leave a large white border and the object floats small inside it;
    cropping to the non-white bounding box (plus a small pad) makes the render
    read large and crisp in the UI without changing the geometry.
    """
    from PIL import Image
    im = Image.open(path).convert("RGB")
    arr = np.asarray(im)
    mask = (arr < thresh).any(axis=2)
    if not mask.any():
        return
    ys, xs = np.where(mask)
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    h, w = arr.shape[:2]
    box = (max(0, x0 - pad), max(0, y0 - pad),
           min(w, x1 + 1 + pad), min(h, y1 + 1 + pad))
    im.crop(box).save(path)


def render_standard_views(mesh: trimesh.Trimesh, out_dir: str, px=RENDER_PX) -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    tris = mesh.vertices[mesh.faces]
    colors = _shaded_facecolors(mesh)
    b_min, b_max = mesh.bounds
    center = (b_min + b_max) / 2
    radius = 0.55 * float(np.max(b_max - b_min))  # frame to the longest extent, not the diagonal
    paths: dict[str, str] = {}
    for name, (elev, azim) in _VIEWS.items():
        fig = plt.figure(figsize=(px[0] / 100, px[1] / 100), dpi=100)
        ax = fig.add_subplot(111, projection="3d")
        coll = Poly3DCollection(tris, facecolors=colors, edgecolors="none")
        ax.add_collection3d(coll)
        for setlim, c in ((ax.set_xlim, 0), (ax.set_ylim, 1), (ax.set_zlim, 2)):
            setlim(center[c] - radius, center[c] + radius)
        ax.set_box_aspect((1, 1, 1))
        ax.view_init(elev=elev, azim=azim)
        ax.set_axis_off()
        path = os.path.join(out_dir, f"{name}.png")
        fig.savefig(path, bbox_inches="tight", pad_inches=0, facecolor="white")
        plt.close(fig)
        _autocrop(path)
        paths[name] = path
    return paths


def render_measurement_overlays(mesh: trimesh.Trimesh, measurements: dict[str, Any], out_dir: str) -> dict[str, str]:
    """2D dimensioned figures (often clearer to an LLM than a shaded 3D render)."""
    os.makedirs(out_dir, exist_ok=True)
    paths: dict[str, str] = {}

    # Plantar silhouette (top-down X-Z) with length + ball-width dimension lines.
    v = mesh.vertices
    fig, ax = plt.subplots(figsize=(4, 8), dpi=120)
    ax.scatter(v[:, WIDTH_AXIS], v[:, LENGTH_AXIS], s=0.4, c="#b58", alpha=0.35, linewidths=0)
    L = measurements.get("length_mm")
    W = measurements.get("width_mm")
    if L:
        z0 = v[:, LENGTH_AXIS].min()
        ax.annotate("", xy=(v[:, WIDTH_AXIS].min(), z0), xytext=(v[:, WIDTH_AXIS].min(), z0 + L),
                    arrowprops=dict(arrowstyle="<->", color="k"))
        ax.text(v[:, WIDTH_AXIS].min(), z0 + L / 2, f" length {L:.1f} mm", rotation=90, va="center")
    ax.set_aspect("equal"); ax.set_title(f"Plantar outline  (width {W:.1f} mm)" if W else "Plantar outline")
    ax.set_xlabel("X width (mm)"); ax.set_ylabel("Z length (mm)")
    p = os.path.join(out_dir, "overlay_plantar.png")
    fig.savefig(p, bbox_inches="tight"); plt.close(fig); paths["overlay_plantar"] = p

    # Midfoot cross-section.
    mid = measurements.get("midfoot") or {}
    if mid.get("outline_xy"):
        xy = np.asarray(mid["outline_xy"])
        fig, ax = plt.subplots(figsize=(5, 3), dpi=120)
        ax.scatter(xy[:, 0], xy[:, 1], s=3, c="#357")
        ax.set_aspect("equal")
        ax.set_title(f"Midfoot section  w={mid.get('width_mm')} h={mid.get('height_mm')} mm")
        ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
        p = os.path.join(out_dir, "overlay_section.png")
        fig.savefig(p, bbox_inches="tight"); plt.close(fig); paths["overlay_section"] = p

    return paths
