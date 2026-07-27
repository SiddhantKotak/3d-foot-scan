"""Build the demo case-study dataset from our actual left + right results.

Runs the geometry pipeline on the reconstructed meshes into proper scan dirs
(so the backend serves the renders) and captures a live Claude biomechanics read,
then writes frontend/src/data/caseStudy.json for the UI case-study view.

  PYTHONPATH=backend python -m scripts.make_case_study
"""
from __future__ import annotations

import json
import os
import shutil

from app.adapters.claude import ClaudeVision
from app.config import get_settings
from app.geometry.pipeline import measure_foot
from app.quality_gate.foot_detect import crop_to_foot
from app.storage import renders_dir

FEET = [
    ("left", "backend/artifacts/smoke-left/renders/3DModel.obj", "case-left",
     "data/Left Foot/00021.034725167.HEIC"),
    ("right", "backend/artifacts/smoke-right/renders/3DModel.obj", "case-right",
     "data/Right Foot/00007.000479000.HEIC"),
]
VISION_VIEWS = ("plantar_top", "medial_side", "posterior_heel")


def main() -> None:
    settings = get_settings()
    vision = ClaudeVision(settings)
    feet = []
    for side, mesh, scan_id, photo in FEET:
        if not os.path.exists(mesh):
            print(f"skip {side}: {mesh} missing")
            continue
        res = measure_foot(mesh, foot_side=side, posture="non_weight_bearing",
                           out_dir=renders_dir(scan_id), do_render=True)
        d = res.to_dict()
        # clean, real input photo (vision-cropped to the foot) as the hero image
        renders = {}
        try:
            cropped = crop_to_foot(photo, renders_dir(scan_id), settings)
            shutil.move(cropped, os.path.join(renders_dir(scan_id), "capture.jpg"))
            renders["capture"] = "capture.jpg"
        except Exception as e:
            print(f"  capture crop failed ({side}): {e}")
        renders.update({k: os.path.basename(v) for k, v in d["renders"].items()})
        paths = [d["renders"][v] for v in VISION_VIEWS if v in d["renders"]]
        read = vision.read_biomechanics(paths, d["measurements"])
        feet.append({
            "side": side,
            "scan_id": scan_id,
            "measurements": {k: d["measurements"].get(k) for k in
                             ("length_mm", "width_mm", "width_reliable", "arch_height_mm",
                              "arch_reliable", "arch_engine")},
            "scale": {k: d["scale"].get(k) for k in ("method", "reliable")},
            "validation": {k: d["validation"].get(k) for k in
                           ("gt_length_mm", "gt_width_mm", "length_dev_mm", "width_dev_mm",
                            "within_tolerance", "scale_reliable")},
            "repair": {"method_used": d["repair"].get("method_used"),
                       "output_watertight": d["repair"].get("output_watertight")},
            "vision": read,
            "warnings": d["warnings"],
            "renders": renders,
        })
        print(f"{side}: L={d['measurements']['length_mm']} W={d['measurements']['width_mm']} "
              f"arch={d['measurements']['arch_height_mm']} vision={read.get('arch_type')}")

    out = {
        "patient": "MS LEUNG",
        "capture": "20 handheld non-weight-bearing HEIC photos per foot",
        "ground_truth_source": "A4 hand tracings (weight-bearing)",
        "data_issues": [
            "Reconstruction captured the whole scene (floor/chair) — background can fuse into the foot mesh",
            "Non-weight-bearing capture: no floor reference, arch height not clinically reliable",
            "Foot + leg in frame complicates orientation",
            "Marginal reconstruction from ~20 handheld photos of low-texture skin",
            "No in-frame scale reference: measurements are shape-only (anchored to the tracing)",
        ],
        "solved": [
            "Image quality gate on the real batches (accept/reject with reasons)",
            "Live KIRI reconstruction end-to-end",
            "Watertight repair of the real photogrammetry hole (pymeshfix)",
            "Scale-calibration method proven (A4 detector) + validation vs ground truth",
            "Foot length anchored to ground truth",
            "Live Claude biomechanics read",
            "LangGraph flow with checkpointing + clinician review interrupt",
            "Reliability flags: bad width/arch/scale are flagged, never shipped",
        ],
        "feet": feet,
    }
    dest = "frontend/src/data/caseStudy.json"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w") as f:
        json.dump(out, f, indent=2)
    print("wrote", dest)


if __name__ == "__main__":
    main()
