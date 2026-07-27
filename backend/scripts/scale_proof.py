"""Prove the scale-calibration method on the A4 tracing images.

Photogrammetry recovers shape, not size. This demonstrates the reference-marker
path: detect a known-size A4 sheet, derive pixels-per-millimetre, and (given the
sheet were in the reconstruction frames) scale the mesh by real/measured. It also
shows the detector refusing a perspective-distorted sheet instead of trusting it.

  PYTHONPATH=backend python -m scripts.scale_proof
"""
from __future__ import annotations

from app.geometry.config import A4_MM
from app.geometry.reference.a4_scale import detect_a4_px_per_mm

TRACINGS = ["data/Foot Tracing 1.jpeg", "data/Foot Tracing 2.jpeg"]


def main() -> None:
    print(f"A4 real size: {A4_MM[0]} x {A4_MM[1]} mm (aspect {A4_MM[1]/A4_MM[0]:.3f})\n")
    for path in TRACINGS:
        r = detect_a4_px_per_mm(path)
        status = "USABLE" if r.get("ok") else "REJECTED"
        print(f"{path}: {status}")
        if "px_per_mm" in r:
            print(f"  px/mm={r['px_per_mm']}  aspect={r['aspect']}  edge-agreement={r.get('agreement_pct')}%")
        for n in r.get("notes", []):
            print(f"  note: {n}")
        print()
    print("Takeaway: with an A4/card in the reconstruction frames we can recover true")
    print("metric scale (real_mm / measured_units). The client's foot photos lack one,")
    print("so those measurements are flagged shape-only until the capture protocol adds a marker.")


if __name__ == "__main__":
    main()
