"""Tests for the geometry core — the accuracy-critical hard parts.

Uses the sample STLs as fixtures (throwaway meshes, but they exercise the real
code paths: the open sole hole, the leg-included mesh, the STL vertex-merge trap).
"""
from __future__ import annotations

import os

import pytest
import trimesh

from app.geometry import io_mesh, repair
from app.geometry.pipeline import measure_foot
from app.geometry.reference.a4_scale import detect_a4_px_per_mm
from app.geometry.reference.ground_truth import GROUND_TRUTH_MM

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL1 = os.path.join(REPO, "data", "model-mobile 1.stl")   # open sole (48 edges)
MODEL2 = os.path.join(REPO, "data", "model-mobile 2.stl")   # watertight + leg
TRACING1 = os.path.join(REPO, "data", "Foot Tracing 1.jpeg")


def test_stl_merge_yields_real_topology():
    """Without merge, STL looks like thousands of open bodies; after, one body."""
    m = io_mesh.load_and_clean(MODEL1)
    assert m.body_count == 1
    # model 1 has the classic single sole hole
    topo = repair.assess_topology(m)
    assert not topo["watertight"]
    assert topo["open_edges"] == 48
    assert len(topo["boundary_loops"]) == 1


def test_repair_closes_the_sole_hole():
    """fill_holes alone fails on this loop; the layered repair must still close it."""
    m = io_mesh.load_and_clean(MODEL1)
    repaired, info = repair.repair_for_raycast(m)
    assert info["output_watertight"] is True
    assert repaired.is_watertight
    assert info["method_used"] in ("cap_loops", "pymeshfix")


def test_watertight_mesh_needs_no_repair():
    m = io_mesh.load_and_clean(MODEL2)
    repaired, info = repair.repair_for_raycast(m)
    assert info["method_used"] == "none"
    assert repaired is m


@pytest.mark.parametrize("mesh_path,side", [(MODEL1, "left"), (MODEL2, "right")])
def test_pipeline_anchors_length_and_validates(mesh_path, side):
    """Unresolved-scale path best-fit-anchors length to GT; validation reports it."""
    res = measure_foot(mesh_path, foot_side=side, posture="non_weight_bearing",
                       out_dir="/tmp/geomtest", do_render=False)
    m = res.measurements
    assert m["length_mm"] > 0 and m["width_mm"] > 0
    # best-fit anchoring => measured length == GT length (deviation ~0)
    assert res.validation["length_dev_mm"] == pytest.approx(0.0, abs=0.5)
    assert res.validation["scale_reliable"] is False
    # arch measured on a repaired (watertight) mesh via the ray engine
    assert res.measurements["arch_engine"] in ("ray", "section")
    # honesty flags always present so the graph can never treat a bad number as clean
    assert "width_reliable" in m and "arch_reliable" in m


def test_a4_detector_runs_on_tracing():
    """The A4 marker detector returns a px/mm estimate on the tracing image."""
    out = detect_a4_px_per_mm(TRACING1)
    assert "px_per_mm" in out or out.get("ok") is False  # runs without raising
    if out.get("ok"):
        assert out["px_per_mm"] > 0


def test_ground_truth_present():
    assert GROUND_TRUTH_MM["left"]["length"] == 245.0
    assert GROUND_TRUTH_MM["right"]["length"] == 240.0
