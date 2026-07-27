"""Rotate/translate a foot mesh into the canonical frame.

Canonical frame (see config): +Y up, floor at Y=0, Z=length (heel=0 -> toe),
X=width (medial=+X). Pitfalls handled here:
  * Use the oriented bounding box for coarse pose, NOT principal inertia axes
    (leg mass skews inertia -> wrong axes on the verified samples).
  * Never trust the raw bbox long-axis as foot length when a leg is included;
    length is derived later from the plantar footprint (measure.py). Alignment
    only needs the axes and floor.
  * Heel/toe disambiguation from the ball-of-foot position (~0.62-0.73 from
    heel), not from raw geometry ends.
  * Medial/lateral from arch-clearance asymmetry, cross-checked against
    foot_side; disagreement is surfaced as a warning, never silently trusted.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import trimesh

from .config import FLOOR_BAND_FRACTION, UP_AXIS, WIDTH_AXIS, LENGTH_AXIS


def _rotation_between(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """4x4 rotation mapping unit vector a onto unit vector b."""
    a = a / (np.linalg.norm(a) + 1e-12)
    b = b / (np.linalg.norm(b) + 1e-12)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    if np.linalg.norm(v) < 1e-9:
        if c > 0:
            return np.eye(4)
        # anti-parallel: 180 deg about any perpendicular axis
        perp = np.array([1.0, 0, 0]) if abs(a[0]) < 0.9 else np.array([0, 1.0, 0])
        axis = np.cross(a, perp)
        return trimesh.transformations.rotation_matrix(np.pi, axis)
    vx = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    R = np.eye(3) + vx + vx @ vx * (1.0 / (1.0 + c))
    M = np.eye(4)
    M[:3, :3] = R
    return M


def _permute_axes(extents: np.ndarray) -> np.ndarray:
    """Map source axes -> canonical (X=width, Y=up, Z=length) by extent size.
    length = largest extent, up = smallest, width = middle."""
    order = np.argsort(extents)          # [smallest, middle, largest]
    src_up, src_width, src_length = order[0], order[1], order[2]
    P = np.zeros((4, 4)); P[3, 3] = 1.0
    P[WIDTH_AXIS, src_width] = 1.0
    P[UP_AXIS, src_up] = 1.0
    P[LENGTH_AXIS, src_length] = 1.0
    # guarantee a right-handed (proper) rotation
    if np.linalg.det(P[:3, :3]) < 0:
        P[LENGTH_AXIS, src_length] = -1.0
    return P


def _obb_align(m: trimesh.Trimesh) -> None:
    """Coarse OBB pose + canonical axis assignment, in place."""
    to_origin, extents = trimesh.bounds.oriented_bounds(m)
    m.apply_transform(to_origin)
    m.apply_transform(_permute_axes(np.asarray(extents)))


def _orient_sole_down(m: trimesh.Trimesh) -> bool:
    """Rest the foot on a floor plane using physics stable-pose analysis, then
    remap to +Y up. More robust than OBB for a curved/leg-cropped foot: it finds
    how the shape actually settles on a table and picks the flattest such pose
    (sole- or dorsum-down), which puts the plantar surface roughly horizontal so
    arch ray casting has a real floor. Returns False if it can't (caller keeps
    the OBB pose)."""
    # stable poses need a closed volume for a correct centre of mass; repair a
    # throwaway proxy if the (leg-cropped) mesh is open, then apply the pose it
    # finds to the real mesh.
    proxy = m
    if not m.is_watertight:
        from .repair import repair_for_raycast
        proxy, _ = repair_for_raycast(m.copy())
    try:
        transforms, probs = proxy.compute_stable_poses(n_samples=1)
    except Exception:
        return False
    if transforms is None or len(transforms) == 0:
        return False
    best_T = transforms[0]                                      # most probable natural rest
    m.apply_transform(best_T)                                   # rests on z=0, +Z up
    m.apply_transform(trimesh.transformations.rotation_matrix(-np.pi / 2, [1, 0, 0]))  # +Z -> +Y up
    # make Z the longer horizontal axis (length), X the shorter (width)
    ext = m.extents
    if ext[WIDTH_AXIS] > ext[LENGTH_AXIS]:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    return True


def _crop_leg(m: trimesh.Trimesh) -> tuple[trimesh.Trimesh, bool]:
    """Remove the leg above the ankle for a foot+leg scan.

    A foot+leg scan shows two lobes (foot, calf) joined by a narrow ankle 'neck'.
    We find the neck as the min-width slice in the central length band, then keep
    the lobe on the *flatter* (higher width/height) end — the forefoot — since the
    calf cross-section is rounder. No pronounced neck -> return unchanged (so a
    foot-only mesh is untouched)."""
    z = m.vertices[:, LENGTH_AXIS]
    z0, z1 = z.min(), z.max()
    L = z1 - z0
    fr = np.linspace(0.1, 0.9, 33)
    widths, heights = [], []
    for f in fr:
        strip = m.vertices[np.abs(z - (z0 + f * L)) <= 0.03 * L]
        widths.append(float(strip[:, WIDTH_AXIS].ptp()) if len(strip) > 3 else 0.0)
        heights.append(float(strip[:, UP_AXIS].ptp()) if len(strip) > 3 else 0.0)
    widths, heights = np.asarray(widths), np.asarray(heights)

    central = (fr >= 0.3) & (fr <= 0.7)
    if not central.any():
        return m, False
    idxs = np.where(central)[0]
    neck_i = idxs[int(np.argmin(widths[idxs]))]
    # a real ankle neck is a pinch relative to the WIDEST slab (foot ball/heel),
    # not the median (which the leg's own width inflates).
    if widths[neck_i] > 0.72 * float(widths.max()):
        return m, False

    neck_f = fr[neck_i]
    flat_lo = widths[:3].mean() / (heights[:3].mean() + 1e-6)
    flat_hi = widths[-3:].mean() / (heights[-3:].mean() + 1e-6)
    keep_high = flat_hi >= flat_lo   # flatter end = forefoot
    thr = z0 + neck_f * L
    mask = z >= thr if keep_high else z <= thr

    m2 = m.copy()
    face_mask = mask[m2.faces].all(axis=1)
    if face_mask.sum() < 0.25 * len(m2.faces):     # keep-region too small; abort
        return m, False
    m2.update_faces(face_mask)
    m2.remove_unreferenced_vertices()
    if m2.body_count > 1:
        m2 = max(m2.split(only_watertight=False), key=lambda c: len(c.faces))
    return m2, True


def _pose_plausibility(m: trimesh.Trimesh) -> float:
    """Foot-likeness of the CURRENT pose: plantar-footprint length/width ratio
    (a real foot is ~2.2-2.8). Low means the foot is mis-oriented (e.g. on its
    side, or a noisy stable-pose landed on the wrong face)."""
    y = m.vertices[:, UP_AXIS]
    fp = m.vertices[y <= y.min() + 0.30 * (y.max() - y.min())]
    if len(fp) < 5:
        return 0.0
    w = float(fp[:, WIDTH_AXIS].ptp())
    length = float(fp[:, LENGTH_AXIS].ptp())
    return length / max(w, 1e-6)


def _fit_floor_normal(pts: np.ndarray) -> np.ndarray:
    """Least-squares plane normal of a point band (RANSAC-lite via SVD)."""
    centroid = pts.mean(axis=0)
    _, _, vh = np.linalg.svd(pts - centroid)
    return vh[2]  # smallest-variance direction = plane normal


def build_canonical_frame(
    mesh: trimesh.Trimesh,
    posture: str,
    foot_side: str,
) -> tuple[trimesh.Trimesh, dict[str, Any]]:
    """Return (aligned_copy, frame_info). Mesh is expected already scaled to mm."""
    m = mesh.copy()
    info: dict[str, Any] = {"posture": posture, "foot_side": foot_side, "warnings": []}

    # 1. Coarse pose via OBB + canonical axis assignment.
    _obb_align(m)

    # 2. Foot+leg scans: try cropping the leg at the ankle neck + physics
    #    stable-pose orientation, but ADOPT it only if the resulting pose is more
    #    foot-plausible than plain OBB. A noisy/partial reconstruction can defeat
    #    stable-pose, so we never let it degrade the pose. Clean foot-only meshes
    #    have no ankle neck and stay on the OBB path.
    info["leg_cropped"] = False
    info["orientation"] = "obb_floor"
    cand, cropped = _crop_leg(m.copy())
    if cropped and _orient_sole_down(cand) and _pose_plausibility(cand) > _pose_plausibility(m):
        m = cand
        info["leg_cropped"] = True
        info["orientation"] = "stable_pose"

    # 3. Up-sign: the flatter extreme band is the floor -> put it at the bottom.
    ys = m.vertices[:, UP_AXIS]
    span = ys.max() - ys.min()
    band = max(span * FLOOR_BAND_FRACTION, 1e-6)
    low_flat = np.std(m.vertices[ys <= ys.min() + band][:, UP_AXIS])
    high_flat = np.std(m.vertices[ys >= ys.max() - band][:, UP_AXIS])
    if high_flat < low_flat:  # flatter region is on top -> flip so floor is down
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 0, 1]))
        ys = m.vertices[:, UP_AXIS]

    # 4. Weight-bearing: level the floor plane to +Y, then drop it to Y=0.
    floor_pts = m.vertices[ys <= ys.min() + band]
    floor_residual = None
    if posture == "weight_bearing" and len(floor_pts) >= 10:
        n = _fit_floor_normal(floor_pts)
        if n[UP_AXIS] < 0:
            n = -n
        m.apply_transform(_rotation_between(n, np.array([0.0, 1.0, 0.0])))
        floor_residual = float(np.std((floor_pts - floor_pts.mean(0)) @ n))
    m.apply_translation([0, -m.vertices[:, UP_AXIS].min(), 0])

    # 5. Heel/toe: ball-of-foot (max width) sits ~0.62-0.73 from heel.
    z = m.vertices[:, LENGTH_AXIS]
    z0, z1 = z.min(), z.max()
    length = z1 - z0
    fr = np.linspace(0.05, 0.95, 19)
    widths = []
    for f in fr:
        zc = z0 + f * length
        strip = m.vertices[np.abs(z - zc) <= 0.03 * length]
        widths.append(strip[:, WIDTH_AXIS].ptp() if len(strip) else 0.0)
    ball_frac = float(fr[int(np.argmax(widths))])
    if ball_frac < 0.5:  # ball is near z0 => toe is at z0 => flip so heel -> Z=0
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))
        m.apply_translation([0, 0, -m.vertices[:, LENGTH_AXIS].min()])
        ball_frac = 1.0 - ball_frac
    else:
        m.apply_translation([0, 0, -m.vertices[:, LENGTH_AXIS].min()])
    info["ball_of_foot_fraction"] = round(ball_frac, 3)

    # 6. Medial/lateral: at midfoot the medial arch lifts, so the medial half
    #    has fewer near-floor (contact) vertices. Put medial on +X.
    z = m.vertices[:, LENGTH_AXIS]
    zc = z.max() * 0.5
    mid = m.vertices[np.abs(z - zc) <= 0.08 * z.max()]
    detected_medial_sign = None
    if len(mid) >= 20:
        near = mid[mid[:, UP_AXIS] <= 10.0]  # within 10 mm of floor
        if len(near) >= 5:
            xmid = mid[:, WIDTH_AXIS].mean()
            pos = np.count_nonzero(near[:, WIDTH_AXIS] > xmid)
            neg = np.count_nonzero(near[:, WIDTH_AXIS] <= xmid)
            # medial = fewer contact points; sign points toward that half
            detected_medial_sign = +1 if pos < neg else -1
    if detected_medial_sign == -1:
        m.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 0, 1]))
        m.apply_translation([0, -m.vertices[:, UP_AXIS].min(), 0])
    if detected_medial_sign is None:
        info["warnings"].append("medial/lateral not detected geometrically; used foot_side default")

    ext = m.extents
    info.update({
        "floor_residual_mm": round(floor_residual, 3) if floor_residual is not None else None,
        "aligned_extents_mm": [round(float(v), 2) for v in ext],
        "detected_medial_sign": detected_medial_sign,
    })
    return m, info
