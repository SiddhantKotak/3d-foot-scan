"""End-to-end graph smoke test (mock or live, depending on env).

Runs the LangGraph pipeline on a real image batch, drives the podiatrist-review
interrupt, and prints the resulting state. Also exercises checkpoint resume.

Usage:
  PYTHONPATH=backend python -m scripts.smoke_graph            # uses .env (live)
  KIRI_API_KEY= ANTHROPIC_API_KEY= PYTHONPATH=backend python -m scripts.smoke_graph  # mock
"""
from __future__ import annotations

import glob
import json
import sys

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.config import get_settings
from app.graph.build import build_graph


def main() -> None:
    side = sys.argv[1] if len(sys.argv) > 1 else "left"
    folder = "Left Foot" if side == "left" else "Right Foot"
    images = sorted(glob.glob(f"data/{folder}/*.HEIC"))

    s = get_settings()
    print(f"[mode] kiri_live={s.kiri_live} claude_live={s.claude_live} | {len(images)} images, side={side}\n")

    graph = build_graph(InMemorySaver())
    scan_id = f"smoke-{side}"
    config = {"configurable": {"thread_id": scan_id}}
    init = {
        "scan_id": scan_id, "image_paths": images,
        "foot_side": side, "posture": "non_weight_bearing", "scale_hint": None,
        "errors": [],
    }

    result = graph.invoke(init, config)

    snap = graph.get_state(config)
    if snap.next:  # paused at the review interrupt
        print(f"[interrupt] paused before: {snap.next}")
        itr = result.get("__interrupt__")
        if itr:
            payload = itr[0].value
            print("[interrupt] payload keys:", list(payload.keys()))
            print("[interrupt] measurements:", json.dumps(payload.get("measurements"), default=str)[:300])
        print("\n[resume] podiatrist approves ...")
        result = graph.invoke(Command(resume={"approved": True, "edits": {}}), config)

    print("\n===== FINAL STATE =====")
    for k in ("status", "quality", "serialize", "mesh_path", "geometry", "vision", "insole_spec"):
        v = result.get(k)
        if k == "quality" and v:
            print(f"quality: ok={v['ok']} accepted={v['n_accepted']}/{v['n_input']} distinct={v['distinct_viewpoints']}")
        elif k == "geometry" and v:
            m, val = v["measurements"], v["validation"]
            print(f"geometry: L={m['length_mm']} W={m['width_mm']} arch={m['arch_height_mm']}mm({m['arch_engine']}) "
                  f"| repair={v['repair'].get('method_used')} wt={v['repair'].get('output_watertight')}")
            print(f"validation: len_dev={val['length_dev_mm']} wid_dev={val['width_dev_mm']} scale_reliable={val['scale_reliable']}")
        elif k == "vision" and v:
            print(f"vision: arch_type={v.get('arch_type')} pronation={v.get('pronation')} "
                  f"weight_dist='{v.get('weight_distribution')}' src={v.get('source','live')}")
        elif k == "insole_spec" and v:
            print("insole_spec:", json.dumps(v, default=str))
        else:
            print(f"{k}: {str(v)[:120]}")


if __name__ == "__main__":
    main()
