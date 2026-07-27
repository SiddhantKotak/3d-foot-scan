# Foot Scan → Custom Insole — Production System Plan

A system that turns a patient foot capture into a validated, manufacturable
custom-insole specification, with clinician sign-off and full auditability.

## 1. Pipeline

```
Capture (guided app)
  → Ingest & Quality Gate
  → Foot Segmentation (remove background/clutter)
  → 3D Reconstruction (KIRI Engine)
  → Mesh Cleanup + Scale Calibration + Measurement
  → Standardized Renders
  → Vision-LLM Biomechanics
  → Clinician Review (human-in-the-loop)
  → Automated Podiatry Report
  → Parametric Insole (.stl) for manufacturing
```

Orchestrated by **LangGraph**: nodes are pure functions over a shared, typed
state; every step is checkpointed and resumable, giving a complete audit trail
from raw capture to the manufactured spec.

## 2. Components

**Capture app (guided).** Enforces the capture protocol: weight-bearing posture,
foot framed to the ankle, a scale reference (A4/card) or LiDAR depth, adequate
coverage (orbit video or 30–60 frames), even lighting. Real-time on-device hints
(too dark / too few angles / no marker detected) prevent bad captures at source.

**Ingest & Quality Gate.** Accepts image batches or video (keyframe extraction).
Rejects unusable input before any paid reconstruction: blur (Laplacian variance),
exposure (histogram), foot presence, angle coverage/diversity, resolution, and
marker presence. Returns actionable reasons for re-capture.

**Foot Localisation (vision-LLM crop).** The vision model locates the target
foot in each frame (a bounding box), and we **crop** to it with a margin. Cropping
— not masking — is the key insight: it drops the leg, the other foot, and distant
clutter (so background can't fuse into the foot mesh and width stays real) while
**keeping local texture** so photogrammetry can still align cameras. Full masking
was found to strip the features reconstruction needs, collapsing the mesh; a crop
does not. (Learned segmentation — rembg/SAM — remains available as a secondary
mask for `is_mask=1` when the reconstruction service supports server-side
alignment.)

**3D Reconstruction (KIRI Engine).** Submit → webhook (with signature
verification) or poll → fetch mesh within the 60-minute link window. Modes:
Photo Scan, Featureless Object Scan, and 3D Gaussian Splatting → mesh. Credit
metering, retries, and a poll fallback for missed webhooks.

**Mesh Cleanup + Scale + Measurement.**
- *Cleanup:* vertex merge, largest-component isolation, watertight repair
  (pymeshfix) before any ray casting.
- *Scale calibration:* reference-marker detection (A4/card → mm/px → scale) or
  LiDAR metric units. This is the one error nothing downstream can catch, so it
  is explicit and validated.
- *Orientation:* leg crop at the ankle + physics stable-pose to rest the sole on
  a floor plane; adaptive fallback that never degrades the pose.
- *Measurement:* length and width from the plantar footprint; arch height by
  multi-slice ray casting (35–65% of length, take the peak) on a weight-bearing,
  repaired mesh; midfoot cross-section.
- *Validation & reliability flags:* every measurement carries a reliability flag
  and is checked against clinical plausibility and (where available) ground
  truth at the ±1 mm benchmark.

**Standardized Renders.** Deterministic camera poses (plantar, medial, posterior)
+ dimensioned 2D overlays, headless. Consistent framing so the vision model sees
the same views every time.

**Vision-LLM Biomechanics (Claude).** From the renders + measurements: arch type,
pronation/supination, and an estimated weight-distribution pattern (grounded in
arch type and foot shape; labelled an estimate, not a measured pressure map).
Returns structured JSON.

**Clinician Review (HITL).** A dynamic interrupt pauses the run and surfaces the
measurements, validation, renders, biomechanics, and all reliability flags. The
clinician approves or edits; the graph resumes on the same thread. Time-travel to
correct an earlier decision without losing later work.

**Automated Podiatry Report (Agent 3).** Generates a professional PDF: patient
data, measurements with confidence, biomechanical assessment, imagery, and
recommendations — from the reviewed state.

**Parametric Insole (Agent 4 / CAD-CAM).** Drives parametric modelling
(OpenSCAD / KittyCAD-style) from the measurements + prescription to emit a
manufacturable, 3D-printable `.stl` — arch support height, heel cup, width,
posting — with a manufacturing manifest.

## 3. Platform & operations

- **API:** FastAPI; async job orchestration; SSE/websocket progress.
- **State & audit:** LangGraph checkpointer on Postgres (thread-per-scan);
  full replay/history.
- **Storage:** object store for captures, meshes, renders, reports, STLs;
  signed URLs; retention policy.
- **Queue/workers:** background workers for reconstruction polling, geometry,
  rendering, report/STL generation.
- **Frontend:** clinician web app (capture intake, live progress, review, report,
  spec) + patient capture guidance.
- **Security/compliance:** patient data handling, access control, encryption at
  rest/in transit, audit logs (health-data-grade).
- **Observability:** per-node metrics, error tracking, cost (KIRI credits, LLM),
  accuracy dashboards.

## 4. Accuracy targets

With the upgraded capture protocol:
- Foot length & width: **±1–2 mm** (validated vs ground truth at the ±1 mm bar).
- Arch height: reliable from weight-bearing capture.
- Scale: metric via marker/LiDAR.
- Biomechanics: reliable arch-type/pronation classification.

Reliability flags guarantee that any measurement failing plausibility or scale
checks is surfaced to the clinician, never passed silently to manufacturing.

## 5. Prerequisite: capture protocol

Full accuracy depends on capture quality. The system mandates: weight-bearing,
foot framed to the ankle, a scale reference (or LiDAR), plain/handled background,
and adequate coverage. The quality gate enforces these before reconstruction; the
capture app guides the patient to meet them.
