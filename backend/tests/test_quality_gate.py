"""Tests for Agent 1 — the image quality gate."""
from __future__ import annotations

import glob
import os

import cv2
import pytest

from app.quality_gate.checks import check_image, run_quality_gate
from app.quality_gate.imaging import load_bgr

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEFT = sorted(glob.glob(os.path.join(REPO, "data", "Left Foot", "*.HEIC")))


@pytest.mark.skipif(not LEFT, reason="sample HEICs not present")
def test_real_batch_passes():
    res = run_quality_gate(LEFT)
    assert res["ok"] is True
    assert res["n_accepted"] == res["n_input"]
    assert res["distinct_viewpoints"] >= 8


@pytest.mark.skipif(not LEFT, reason="sample HEICs not present")
def test_blurred_image_rejected(tmp_path):
    bgr = load_bgr(LEFT[0])
    blurred = cv2.GaussianBlur(bgr, (0, 0), 8)
    p = str(tmp_path / "blurred.png")
    cv2.imwrite(p, blurred)
    verdict, _ = check_image(p)
    assert verdict.passed is False
    assert any("blur" in r for r in verdict.reasons)


@pytest.mark.skipif(not LEFT, reason="sample HEICs not present")
def test_too_few_images_rejected():
    res = run_quality_gate(LEFT[:3])
    assert res["ok"] is False
    assert any("usable images" in r for r in res["batch_reasons"])
