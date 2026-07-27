"""Load an arbitrary reconstruction mesh into a single clean Trimesh.

The critical trap (verified on the sample data): STL stores every triangle's
vertices independently, so a freshly loaded STL reports thousands of
disconnected "bodies" and *every* edge looks open. Topology is meaningless
until vertices are merged. We fix that here, before anyone checks
watertightness or casts a ray.
"""
from __future__ import annotations

import numpy as np
import trimesh


def load_and_clean(mesh_path: str, keep_all_components: bool = False) -> trimesh.Trimesh:
    """Return a single, de-duplicated, cleaned mesh.

    Steps (order matters):
      1. force a single Trimesh
      2. merge duplicated vertices  -> real topology
      3. drop duplicate / degenerate faces
      4. drop unreferenced vertices
      5. component handling (see below)
      6. fix winding so normals are consistent

    Component handling: by default keep the largest connected component (isolates
    the foot from floor/clutter in a scene reconstruction). For a multi-piece
    scan — e.g. a mesh split into texture chunks where no single component is the
    whole foot — pass ``keep_all_components=True`` to keep every piece and only
    drop tiny speckle. Scaling to mm is scale.resolve_scale's job.
    """
    mesh = trimesh.load(mesh_path, force="mesh", process=True)
    if not isinstance(mesh, trimesh.Trimesh):
        raise ValueError(f"{mesh_path}: could not load a triangle mesh")

    mesh.merge_vertices()
    mesh.update_faces(mesh.unique_faces())
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()

    if mesh.body_count > 1:
        components = mesh.split(only_watertight=False)
        if len(components) > 1:
            if keep_all_components:
                # drop only tiny speckle (<1% of the largest piece's faces)
                floor = 0.01 * max(len(c.faces) for c in components)
                kept = [c for c in components if len(c.faces) >= floor]
                mesh = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]
            else:
                mesh = max(components, key=lambda c: len(c.faces))

    mesh.fix_normals()
    return mesh


def describe(mesh: trimesh.Trimesh) -> dict:
    """A compact, JSON-friendly snapshot for logs / audit trail."""
    ext = np.asarray(mesh.extents, dtype=float)
    return {
        "vertices": int(len(mesh.vertices)),
        "faces": int(len(mesh.faces)),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "euler_number": int(mesh.euler_number),
        "extents_native": [round(float(v), 6) for v in ext],
        "body_count": int(mesh.body_count),
    }
