"""Re-run a foot through KIRI Featureless Object Scan (for smooth/low-texture
subjects), on vision-cropped foot frames, then measure + render and compare.

  PYTHONPATH=backend python -m scripts.featureless_rerun left
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
    side = sys.argv[1] if len(sys.argv) > 1 else "left"
    folder = "Left Foot" if side == "left" else "Right Foot"
    images = sorted(glob.glob(f"data/{folder}/*.HEIC"))
    settings = get_settings()
    kiri = KiriClient(settings)
    scan_id = f"featureless-{side}"

    print(f"[1/4] vision-LLM foot crop on {len(images)} frames ...")
    t = time.time()
    cropped = crop_images_to_foot(images, uploads_dir(scan_id), settings)
    print(f"      done in {time.time()-t:.0f}s")

    print("[2/4] submitting to KIRI Featureless Object Scan ...")
    serialize = kiri.submit_featureless_scan(cropped, file_format="obj")
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
    mesh_path = kiri.download_mesh(serialize, url, renders_dir(scan_id))
    print(f"      mesh={mesh_path}")

    print("[4/4] measuring + rendering ...")
    res = measure_foot(mesh_path, foot_side=side, posture="non_weight_bearing",
                       out_dir=renders_dir(scan_id), do_render=True)
    m = res.measurements
    print("\n===== FEATURELESS RESULT =====")
    print(f"mesh: {mesh_path}")
    print(f"length={m['length_mm']}  width={m['width_mm']} (reliable={m['width_reliable']})  "
          f"arch={m['arch_height_mm']} (reliable={m['arch_reliable']})")
    print("compare (left, photo-scan): width 110.8 mm; renders were fragmented blobs")


if __name__ == "__main__":
    main()
