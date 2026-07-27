"""Dev entrypoint:  python -m app.geometry.cli <mesh> --side left [--posture ...]"""
from __future__ import annotations

import argparse
import json

from .pipeline import measure_foot


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure a foot mesh and validate vs ground truth.")
    ap.add_argument("mesh")
    ap.add_argument("--side", choices=["left", "right"], required=True)
    ap.add_argument("--posture", choices=["weight_bearing", "non_weight_bearing"],
                    default="non_weight_bearing")
    ap.add_argument("--out", default="./out")
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    result = measure_foot(
        args.mesh, foot_side=args.side, posture=args.posture,
        out_dir=args.out, do_render=not args.no_render,
    )
    d = result.to_dict()
    d["measurements"].pop("arch_profile", None)          # keep console output readable
    if d["measurements"].get("midfoot"):
        d["measurements"]["midfoot"].pop("outline_xy", None)
    print(json.dumps(d, indent=2))


if __name__ == "__main__":
    main()
