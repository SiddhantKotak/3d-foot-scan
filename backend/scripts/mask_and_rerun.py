"""Mask the foot images (remove floor/clutter) and re-run reconstruction live,
then compare width vs the unmasked run.

  PYTHONPATH=backend python -m scripts.mask_and_rerun right
"""
from __future__ import annotations

import glob
import sys
import time

from app.adapters.kiri import KiriClient, STATUS_SUCCESS, STATUS_FAILED, STATUS_EXPIRED
from app.config import get_settings
from app.geometry.pipeline import measure_foot
from app.quality_gate.segmentation import mask_foot_images
from app.storage import renders_dir, uploads_dir


def main() -> None:
    side = sys.argv[1] if len(sys.argv) > 1 else "right"
    folder = "Right Foot" if side == "right" else "Left Foot"
    images = sorted(glob.glob(f"data/{folder}/*.HEIC"))
    settings = get_settings()
    kiri = KiriClient(settings)
    scan_id = f"masked-{side}"

    print(f"[1/4] masking {len(images)} images (rembg, foreground only) ...")
    t = time.time()
    masked = mask_foot_images(images, uploads_dir(scan_id))
    print(f"      done in {time.time()-t:.0f}s -> {len(masked)} PNGs")

    print("[2/4] submitting masked images to KIRI (is_mask=1) ...")
    serialize = kiri.submit_photo_scan(masked, file_format="obj", is_mask=1)
    print(f"      serialize={serialize}")

    print("[3/4] polling for reconstruction ...")
    deadline = time.time() + 900
    while True:
        st = kiri.get_status(serialize)
        if st == STATUS_SUCCESS:
            break
        if st in (STATUS_FAILED, STATUS_EXPIRED) or time.time() > deadline:
            print(f"      FAILED/timeout status={st}")
            return
        time.sleep(5)
    url = kiri.get_download_url(serialize)
    mesh_path = kiri.download_mesh(serialize, url, renders_dir(scan_id))
    print(f"      mesh={mesh_path}")

    print("[4/4] measuring ...")
    res = measure_foot(mesh_path, foot_side=side, posture="non_weight_bearing",
                       out_dir=renders_dir(scan_id), do_render=True)
    m = res.measurements
    print("\n===== MASKED RESULT =====")
    print(f"length={m['length_mm']}  width={m['width_mm']} (reliable={m['width_reliable']})  "
          f"arch={m['arch_height_mm']} (reliable={m['arch_reliable']})")
    print(f"width_dev vs GT: {res.validation['width_dev_mm']} mm")
    print("compare: UNMASKED right width was 199.94 mm (implausible, floor fused)")
    for w in res.warnings:
        print("  warn:", w)


if __name__ == "__main__":
    main()
