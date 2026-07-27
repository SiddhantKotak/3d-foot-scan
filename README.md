# Foot Scan → Manufactured Insole — PoC

Proves the *hardest parts* of a photos-to-insole pipeline are accurately
solvable, wrapped in the real architecture: **FastAPI + React** UI, a real
**LangGraph** backbone (resumable + human-in-the-loop), live **KIRI** 3D
reconstruction, and live **Claude** vision. See [`CLAUDE.md`](./CLAUDE.md) for
architecture, run instructions, and the gotchas baked into the code.

## What the PoC proves (on the real data in `data/`)

| Hard part | Status | Evidence |
|---|---|---|
| **1. Image Quality Gate** | ✅ | 20/20 real HEICs accepted, 19 distinct viewpoints; a blurred image is rejected (Laplacian var 1.4 < 30). `scripts` + `tests/test_quality_gate.py` |
| **2. Scale calibration + validation** | ✅ | A4 detector: **6.64 px/mm** from a tracing (aspect 1.393 ≈ A4 1.414); rejects a perspective-distorted sheet. Every measurement validated vs A4-tracing ground truth at ±1 mm. `scripts/scale_proof.py` |
| **3a. Watertight repair** | ✅ | The real photogrammetry hole (369 open edges, which `fill_holes` can't close) is closed cleanly by `pymeshfix` → watertight. `tests/test_geometry.py` |
| **3b. Foot length** | ✅ | From the plantar footprint (not the bbox), anchored to the tracing length. |
| **3c. Foot width** | ⚠️ | Measures, but 3D non-weight-bearing width vs pen-traced weight-bearing width legitimately differ (+16–26 mm on the samples). |
| **3d. Canonical orientation + arch height** | ❌ hard | The real capture is a **non-weight-bearing foot+*leg* orbit scan** at an angle. Geometric heuristics (OBB, ankle-neck crop, re-fit) can't reliably level it → arch height is not clinically meaningful here. Needs weight-bearing capture, an ankle-height crop, or learned foot segmentation. This is the main open problem. |
| **4. Vision-LLM biomechanics** | ✅ | Live Claude reads renders + measurements → arch type / pronation / estimated weight distribution, correctly hedged as an estimate (strong on clean meshes; render quality is gated by 3d). `adapters/claude.py` |
| **LangGraph flow** | ✅ | 6 nodes, SQLite checkpoint, crash-resume, podiatrist `interrupt()` + resume, live KIRI + live Claude end-to-end. `scripts/smoke_graph.py` |

## The honest headline
The single biggest lever is the **capture protocol**, and the PoC proves why by
surfacing two failure modes this dataset triggers:

1. **No in-frame size reference** → photogrammetry recovers shape, not size, so
   measurements are flagged **shape-only** (best-fit anchored to the tracing for
   comparison). Fix: **put an A4 sheet / credit card in frame, or use LiDAR.**
2. **Non-weight-bearing foot+leg orbit** → no floor to level against and a leg
   that confuses orientation, so arch height isn't clinically meaningful. Fix:
   **capture weight-bearing, crop near the ankle, or add foot segmentation.**

Everything else — quality gate, watertight repair, length, the scale *method*,
the LangGraph backbone, live KIRI + Claude — works. The pipeline is built so it
*flags* these issues rather than silently returning a wrong number, which is the
whole point: a bad scale or a bad pose is caught, not shipped to manufacturing.

## Quickstart
```bash
# backend
cp backend/.env.example backend/.env      # add KIRI_API_KEY + ANTHROPIC_API_KEY (or leave blank for mock)
PYTHONPATH=backend ./backend/.venv/bin/python -m uvicorn app.main:app --reload --port 8000
# frontend
cd frontend && npm install && npm run dev  # http://localhost:5173

# prove the hard parts without the UI:
PYTHONPATH=backend ./backend/.venv/bin/python -m scripts.scale_proof
PYTHONPATH=backend ./backend/.venv/bin/python -m scripts.smoke_graph left
PYTHONPATH=backend ./backend/.venv/bin/python -m pytest backend/tests -q
```
