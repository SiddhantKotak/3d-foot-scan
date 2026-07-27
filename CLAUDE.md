# CLAUDE.md — Foot Scan → Manufactured Insole (PoC)

## What this is
A proof-of-concept multi-agent pipeline that turns a batch of foot photos into
validated insole measurements. It is **not** the full product — its job is to
prove the *hardest parts* are accurately solvable, wrapped in the real
architecture (FastAPI + React UI, a real LangGraph orchestration backbone, live
KIRI reconstruction, live Claude vision).

Pipeline (each stage is a LangGraph node):
```
upload → quality_gate → submit_reconstruction → await_reconstruction
       → measure(+render) → vision_read → review(HITL interrupt) → insole_spec
```

## The four hard parts (what the PoC proves)
1. **Image Quality Gate** (`backend/app/quality_gate/`) — blur (Laplacian
   variance), exposure (histogram), foot presence (skin), angle coverage
   (view-diversity). Rejects bad input before any paid reconstruction.
2. **Scale calibration + validation** (`backend/app/geometry/scale.py`,
   `reference/`) — the #1 failure mode. Photogrammetry recovers shape, not size.
   We prove the reference-marker method (A4 detector) and validate every
   measurement against the hand-traced ground truth at the ±1 mm clinical bar.
3. **Watertight repair + arch** (`geometry/repair.py`, `measure.py`) — the real
   sole hole can't be closed by `trimesh.fill_holes`; we cap-the-loop /
   pymeshfix **before** ray casting, then multi-slice ray-cast (35–65% of
   length) for arch height.
4. **Vision-LLM biomechanics** (`adapters/claude.py`) — Claude reads the
   standardized renders + measurements → arch type, pronation/supination,
   estimated weight distribution.

## Repo layout
```
data/                      # sample HEIC foot photos + A4 tracings (ground truth)
backend/
  .venv/                   # python venv (system-site-packages; has trimesh/cv2/…)
  app/
    config.py  storage.py  main.py
    quality_gate/          # Agent 1: checks.py, imaging.py (HEIC), keyframes.py (video stub)
    geometry/              # Agent 2 core: io_mesh, scale, align, repair, measure, render, pipeline, cli
      reference/           # ground_truth.py (A4 tracings), a4_scale.py (marker detector)
    adapters/              # kiri.py (real+mock), claude.py (real+mock)
    graph/                 # state.py, build.py, runner.py, nodes/*.py  ← the LangGraph flow
    api/                   # routes_scan / routes_review / routes_webhook
  scripts/smoke_graph.py   # end-to-end runner (mock or live)
frontend/                  # Vite + React + TS UI
```

## Run it
```bash
# backend (from repo root)
PYTHONPATH=backend ./backend/.venv/bin/python -m uvicorn app.main:app --reload --port 8000
# geometry CLI on a mesh
PYTHONPATH=backend ./backend/.venv/bin/python -m app.geometry.cli "<mesh>" --side left
# full pipeline end-to-end (uses backend/.env; blank the keys to force mock)
PYTHONPATH=backend ./backend/.venv/bin/python -m scripts.smoke_graph left
# frontend
cd frontend && npm install && npm run dev     # proxies /api -> :8000
```

## Keys / modes
`backend/.env`: `KIRI_API_KEY`, `ANTHROPIC_API_KEY`, optional `KIRI_WEBHOOK_SECRET`
+ `PUBLIC_URL`. **Any key absent → that adapter runs in mock mode**, so the whole
graph runs with no credentials. Without `PUBLIC_URL`+secret, reconstruction
completion is detected by **polling** (webhook path is the alternative).

## Gotchas baked into the code (don't undo these)
- **STL vertex-merge first** (`io_mesh.load_and_clean`): STL duplicates vertices;
  topology/watertightness is meaningless until merged.
- **Repair before ray casting**: an open sole lets an up-ray pass through and hit
  the top of the foot → impossible arch. `fill_holes` alone fails on the big sole
  loop → cap-the-loop → pymeshfix.
- **Never use the raw bbox as foot length** — it can include the leg; length comes
  from the plantar footprint (`measure._footprint_mask`, a *relative* band so it's
  scale-invariant).
- **Submit/await are separate nodes**: never submit-KIRI-then-`interrupt()` in one
  node — a resume re-runs the node top and re-submits (double billing).
- **`interrupt()` discipline**: nodes are side-effect-free before the interrupt and
  the interrupt is unconditional (resume replays the node top).
- **Renders use matplotlib Agg** (headless); do not add open3d/pyvista/GL stacks.

## Data reality (important context)
- The provided `data/*.stl` are ImageToStl.com throwaways — **dev fixtures only**;
  the pipeline uses live KIRI output.
- The foot photos are **non-weight-bearing** and have **no in-frame size
  reference**, so photogrammetry can't recover true scale from them → measurements
  are flagged **shape-only** and best-fit-anchored to the tracing length. Capture
  fix: put an A4 sheet / credit card in frame, or use LiDAR.
- Ground truth (A4 tracings): LEFT 245×95 mm, RIGHT 240×95 mm (weight-bearing).
  Arch height is posture-dependent, so it is not apples-to-apples vs a
  non-weight-bearing scan.
