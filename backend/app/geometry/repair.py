"""Watertight detection + layered hole repair.

Must run BEFORE any ray casting: an open sole lets an upward ray pass straight
through the hole and hit the *top* of the foot, producing an impossible arch
reading. On the verified sample, ``trimesh.fill_holes`` alone does NOT close the
large sole loop, so we layer three strategies and stop at the first that yields a
watertight mesh:

  1. trimesh.repair.fill_holes        (cheap; closes small tri/quad gaps)
  2. cap-the-loop                     (triangulate each boundary loop to its centroid)
  3. pymeshfix.MeshFix                (robust; handles non-planar / self-intersecting)
"""
from __future__ import annotations

from typing import Any

import numpy as np
import trimesh


def _boundary_loops(mesh: trimesh.Trimesh) -> list[list[int]]:
    """Ordered vertex-index loops around each open boundary."""
    sorted_edges = mesh.edges_sorted
    single = trimesh.grouping.group_rows(sorted_edges, require_count=1)
    if len(single) == 0:
        return []
    edges = mesh.edges[single]
    adj: dict[int, list[int]] = {}
    for a, b in edges:
        adj.setdefault(int(a), []).append(int(b))
        adj.setdefault(int(b), []).append(int(a))
    loops: list[list[int]] = []
    unused = {tuple(sorted((int(a), int(b)))) for a, b in edges}
    while unused:
        a, b = next(iter(unused))
        unused.discard((a, b))
        loop = [a, b]
        while True:
            nxt = None
            for cand in adj.get(loop[-1], []):
                key = tuple(sorted((loop[-1], cand)))
                if key in unused:
                    nxt = cand
                    unused.discard(key)
                    break
            if nxt is None or nxt == loop[0]:
                break
            loop.append(nxt)
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def assess_topology(mesh: trimesh.Trimesh) -> dict[str, Any]:
    loops = _boundary_loops(mesh)
    single = trimesh.grouping.group_rows(mesh.edges_sorted, require_count=1)
    return {
        "watertight": bool(mesh.is_watertight),
        "open_edges": int(len(single)),
        "boundary_loops": [
            {
                "n_verts": len(lp),
                "centroid": [round(float(v), 2) for v in mesh.vertices[lp].mean(0)],
                "bbox_mm": [round(float(v), 2) for v in mesh.vertices[lp].ptp(0)],
            }
            for lp in loops
        ],
        "winding_consistent": bool(mesh.is_winding_consistent),
        "euler_number": int(mesh.euler_number),
    }


def _cap_loops(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Fan-triangulate each boundary loop to its centroid (near-planar loops)."""
    loops = _boundary_loops(mesh)
    if not loops:
        return mesh
    verts = mesh.vertices.copy()
    faces = mesh.faces.copy().tolist()
    for lp in loops:
        centroid = verts[lp].mean(axis=0)
        ci = len(verts)
        verts = np.vstack([verts, centroid])
        for i in range(len(lp)):
            a, b = lp[i], lp[(i + 1) % len(lp)]
            faces.append([a, b, ci])
    capped = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces), process=True)
    capped.merge_vertices()
    capped.fix_normals()
    return capped


def _pymeshfix(mesh: trimesh.Trimesh) -> trimesh.Trimesh | None:
    try:
        from pymeshfix import MeshFix
    except Exception:
        return None
    try:
        mf = MeshFix(mesh.vertices, mesh.faces)
        mf.repair()                      # this pymeshfix build takes no kwargs
        verts, faces = mf.points, mf.faces  # 0.18 API (.mesh needs pyvista)
    except Exception:
        return None
    if faces is None or len(faces) == 0:
        return None
    out = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    out.fix_normals()
    return out


def repair_for_raycast(mesh: trimesh.Trimesh) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Return (repaired_mesh, repair_info). Never raises; degrades gracefully."""
    before = assess_topology(mesh)
    info: dict[str, Any] = {"input": before, "steps": []}

    if before["watertight"]:
        info["method_used"] = "none"
        info["output_watertight"] = True
        return mesh, info

    # 1. trimesh fill_holes
    m1 = mesh.copy()
    try:
        trimesh.repair.fill_holes(m1)
    except Exception as e:  # pragma: no cover - defensive
        info["steps"].append(f"fill_holes error: {e}")
    info["steps"].append({"fill_holes_watertight": bool(m1.is_watertight)})
    if m1.is_watertight:
        info["method_used"] = "fill_holes"
        info["output_watertight"] = True
        return m1, info

    # 2. pymeshfix — proper remeshing that closes large, non-planar loops
    #    cleanly (unlike a centroid fan, which sprays long triangles across the
    #    interior and corrupts ray casting).
    m2 = _pymeshfix(m1)
    if m2 is not None:
        info["steps"].append({"pymeshfix_watertight": bool(m2.is_watertight)})
        if m2.is_watertight:
            info["method_used"] = "pymeshfix"
            info["output_watertight"] = True
            return m2, info

    # 3. cap-the-loop — last resort for small, near-planar leftover loops only.
    try:
        m3 = _cap_loops(m2 if m2 is not None else m1)
        info["steps"].append({"cap_loops_watertight": bool(m3.is_watertight)})
        if m3.is_watertight:
            info["method_used"] = "cap_loops"
            info["output_watertight"] = True
            return m3, info
    except Exception as e:  # pragma: no cover
        info["steps"].append(f"cap_loops error: {e}")
        m3 = m2 if m2 is not None else m1

    # Give back the best effort; caller falls back to the section-based arch.
    best = m3 if m3 is not None else m1
    info["method_used"] = "best_effort"
    info["output_watertight"] = bool(best.is_watertight)
    info["output"] = assess_topology(best)
    return best, info
