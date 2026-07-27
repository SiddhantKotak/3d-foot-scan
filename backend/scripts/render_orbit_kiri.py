"""Render a clean foot mesh into a multi-view orbit photo set, then reconstruct
it live with KIRI — a synthetic-but-genuine end-to-end KIRI reconstruction.

A procedural high-frequency surface texture is baked in so photogrammetry has
features to match (bare-skin renders have none). Run:

  PYOPENGL_PLATFORM=egl PYTHONPATH=backend python -m scripts.render_orbit_kiri
"""
from __future__ import annotations

import os
import time

import numpy as np
import trimesh
import pyrender
from PIL import Image

from app.adapters.kiri import KiriClient, STATUS_SUCCESS, STATUS_FAILED, STATUS_EXPIRED
from app.config import get_settings
from app.geometry import io_mesh
from app.geometry.pipeline import measure_foot
from app.storage import renders_dir, uploads_dir

GLTF = "backend/artifacts/footmodel/model/scene.gltf"
SCAN_ID = "kiri-render"
N_AZ, ELEVS = 20, (18, 42, 66)   # 20 azimuths x 3 elevations = 60 views


def look_at(eye, target=(0, 0, 0), up=(0, 0, 1)):
    eye = np.asarray(eye, float); target = np.asarray(target, float); up = np.asarray(up, float)
    z = eye - target; z /= np.linalg.norm(z)
    x = np.cross(up, z)
    if np.linalg.norm(x) < 1e-6:
        x = np.cross((0, 1, 0), z)
    x /= np.linalg.norm(x); y = np.cross(z, x)
    M = np.eye(4); M[:3, 0] = x; M[:3, 1] = y; M[:3, 2] = z; M[:3, 3] = eye
    return M


_PALETTE = np.array([
    [ 20,  20,  20], [240, 240, 240], [214,  40,  40], [ 40, 110, 214],
    [ 45, 170,  70], [240, 196,  25], [176,  55, 196], [ 30, 196, 196],
    [240, 120,  30], [120,  82,  46], [200,  60, 120], [ 60,  66, 150],
], dtype=np.uint8)


def textured_mesh():
    m = io_mesh.load_and_clean(GLTF, keep_all_components=True)
    m.apply_translation(-m.centroid)
    # SPATIALLY-COHERENT high-contrast patches (~7 mm), coloured by a hash of the
    # face-centroid's 3D grid cell. This is the correct photogrammetry texture:
    # per-face white noise ALIASES under camera motion (each view resamples it
    # differently) and breaks Structure-from-Motion matching; coherent patches
    # that are static in 3D are photo-consistent across views, so KIRI can match
    # the SAME point in overlapping photos. Rendered matte/flat.
    cent = m.triangles_center
    cell = 0.03 * float(max(m.extents))            # ~7 mm patches on a ~245 mm foot
    idx = np.floor(cent / cell).astype(np.int64)
    h = (idx[:, 0] * 73856093) ^ (idx[:, 1] * 19349663) ^ (idx[:, 2] * 83492791)
    rgb = _PALETTE[np.abs(h) % len(_PALETTE)]
    fc = np.hstack([rgb, np.full((len(rgb), 1), 255, np.uint8)])
    m.visual = trimesh.visual.ColorVisuals(m, face_colors=fc)
    return m


def _matte():
    return pyrender.MetallicRoughnessMaterial(
        metallicFactor=0.0, roughnessFactor=1.0, baseColorFactor=[1, 1, 1, 1])


def render_orbit(out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    m = textured_mesh()
    R = float(np.linalg.norm(m.extents)) / 2
    dist = R * 2.6
    # flat shading (smooth=False) keeps each face's random speckle colour crisp;
    # a camera-mounted headlight + strong ambient keeps every point well-lit and
    # view-consistent, so the speckle (unique, non-repeating) matches across views.
    pm = pyrender.Mesh.from_trimesh(m, smooth=False)
    cam = pyrender.PerspectiveCamera(yfov=np.pi / 4)
    rr = pyrender.OffscreenRenderer(1200, 1400)
    paths = []
    i = 0
    for el in ELEVS:
        for k in range(N_AZ):
            az = 2 * np.pi * k / N_AZ
            e = np.radians(el)
            eye = dist * np.array([np.cos(e) * np.cos(az), np.cos(e) * np.sin(az), np.sin(e)])
            pose = look_at(eye)
            # Mid-grey background: far from both the dark (20) and light (240)
            # patches, so every silhouette edge stays crisp for segmentation.
            sc = pyrender.Scene(bg_color=[128, 128, 128], ambient_light=[.6, .6, .6])
            sc.add(pm); sc.add(cam, pose=pose)
            sc.add(pyrender.DirectionalLight(intensity=2.5), pose=pose)
            col, _ = rr.render(sc)
            p = os.path.join(out_dir, f"view_{i:03d}.jpg")
            Image.fromarray(col).save(p, quality=92)
            paths.append(p); i += 1
    rr.delete()
    return paths


def main() -> None:
    settings = get_settings()
    kiri = KiriClient(settings)
    print(f"[1/4] rendering {N_AZ * len(ELEVS)} orbit views ...")
    t = time.time()
    frames = render_orbit(uploads_dir(SCAN_ID))
    print(f"      {len(frames)} frames in {time.time()-t:.0f}s")

    print("[2/4] submitting to KIRI photo scan ...")
    serialize = kiri.submit_photo_scan(frames, file_format="obj", model_quality=0)
    print(f"      serialize={serialize}")

    print("[3/4] polling ...")
    deadline = time.time() + 1200
    while True:
        st = kiri.get_status(serialize)
        if st == STATUS_SUCCESS:
            break
        if st in (STATUS_FAILED, STATUS_EXPIRED) or time.time() > deadline:
            print(f"      FAILED/timeout status={st}"); return
        time.sleep(6)
    url = kiri.get_download_url(serialize)
    mesh_path = kiri.download_mesh(serialize, url, renders_dir(SCAN_ID))
    print(f"      mesh={mesh_path}")

    print("[4/4] measuring + rendering ...")
    res = measure_foot(mesh_path, foot_side="left", posture="weight_bearing",
                       out_dir=renders_dir(SCAN_ID), do_render=True)
    m = res.measurements
    print("\n===== KIRI-FROM-RENDER RESULT =====")
    print(f"mesh: {mesh_path}")
    print(f"length={m['length_mm']} width={m['width_mm']} (rel {m['width_reliable']}) "
          f"arch={m['arch_height_mm']} (rel {m['arch_reliable']})")
    print(f"repair={res.repair.get('method_used')} wt={res.repair.get('output_watertight')}")


if __name__ == "__main__":
    main()
