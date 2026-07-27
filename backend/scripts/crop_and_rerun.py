"""Vision-LLM foot-crop each frame, then reconstruct live and measure.

  PYTHONPATH=backend python -m scripts.crop_and_rerun right
"""
from __future__ import annotations

import glob
import sys
import time

from app.adapters.kiri import KiriClient, STATUS_SUCCESS, STATUS_FAILED, STATUS_EXPIRED
from app.config import get_settings
from app.geometry.pipeline import measure_foot
from app.quality_gate.foot_detect import crop_images_to_foot
from app.storage import renders_dir, uploads_dir


def main() -> None:
    side = sys.argv[1] if len(sys.argv) > 1 else "right"
    folder = "Right Foot" if side == "right" else "Left Foot"
    images = sorted(glob.glob(f"data/{folder}/*.HEIC"))
    settings = get_settings()
    kiri = KiriClient(settings)
    scan_id = f"cropped-{side}"

    print(f"[1/4] vision-LLM foot crop on {len(images)} frames ...")
    t = time.time()
    cropped = crop_images_to_foot(images, uploads_dir(scan_id), settings)
    print(f"      done in {time.time()-t:.0f}s")

    print("[2/4] submitting cropped frames to KIRI ...")
    serialize = kiri.submit_photo_scan(cropped, file_format="obj")
    print(f"      serialize={serialize}")

    print("[3/4] polling ...")
    deadline = time.time() + 900
    while True:
        st = kiri.get_status(serialize)
        if st == STATUS_SUCCESS:
            break
        if st in (STATUS_FAILED, STATUS_EXPIRED) or time.time() > deadline:
            print(f"      FAILED/timeout status={st}"); return
        time.sleep(5)
    url = kiri.get_download_url(serialize)
    mesh_path = kiri.download_mesh(serialize, url, renders_dir(scan_id))
    print(f"      mesh={mesh_path}")

    print("[4/4] measuring ...")
    res = measure_foot(mesh_path, foot_side=side, posture="non_weight_bearing",
                       out_dir=renders_dir(scan_id), do_render=True)
    m = res.measurements
    print("\n===== VISION-CROP RESULT =====")
    print(f"length={m['length_mm']}  width={m['width_mm']} (reliable={m['width_reliable']})  "
          f"arch={m['arch_height_mm']} (reliable={m['arch_reliable']})")
    print(f"width_dev vs GT: {res.validation['width_dev_mm']} mm")
    print("compare: unmasked width 199.94 mm | rembg-masked width 210.33 mm")
    for w in res.warnings:
        print("  warn:", w)


if __name__ == "__main__":
    main()
