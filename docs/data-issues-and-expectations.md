# Data Issues & Expectations

_Findings from the current dataset (patient "MS LEUNG", left + right foot), and what accuracy to expect from this input vs an upgraded capture._

## The dataset we received

| Item | Detail |
|---|---|
| Foot photos | 20 HEIC per foot (3024×4032), handheld |
| Posture | **Non-weight-bearing** — patient seated, foot lifted, sole to camera |
| Scene | Busy clinic: floor tiles, red chair, bag, second foot, trousers all in frame |
| Scale reference | **None in the foot photos** |
| A4 tracings | 2D pen outlines on A4 — LEFT 245×95 mm, RIGHT 240×95 mm (weight-bearing) |

The A4 tracings are the **ground truth** and are used to validate/anchor measurements. They are a *separate* capture, so they cannot scale the 3D mesh — only the foot photos can.

## Issues found (with evidence)

1. **The reconstruction captures the whole scene, not just the foot.** KIRI reconstructs the floor, chair, and clutter. On the right foot the ground plane **fused into the foot**, so the measured width came out **200 mm** (a foot is ~95 mm). *Evidence: right-foot largest component measured 189 mm wide × 65 mm tall — a wide flat sheet, not a foot.*

2. **Non-weight-bearing capture → no floor reference.** With the foot held in the air there is no ground plane to measure the arch against, and the relaxed/curled foot is not in a standing pose. Arch height is not clinically recoverable this way. *Evidence: arch read 74 mm (left) / 38 mm (right) vs a real ~15–30 mm.*

3. **Foot + leg in frame.** The scan includes a large leg section, which confuses automatic orientation (the bounding box follows the foot→leg axis, not the foot). *Handled by our leg-crop + stable-pose, but only when the reconstruction is clean enough.*

4. **Marginal reconstruction quality.** ~20 handheld photos of a smooth, low-texture foot against a busy background yields a sparse, noisy, partial mesh (right foot: ~4.4k vertices; cropped foot ≈214 cm³ vs ~800 cm³ real). Smooth skin gives photogrammetry few features to match.

5. **No in-frame scale reference.** Photogrammetry recovers shape, not size. Without a card/A4 in the foot photos (or LiDAR), the mesh has no real-world units — measurements are **shape-only** and must be anchored to the tracing.

6. **Posture mismatch for validation.** The tracing is weight-bearing; the scan is non-weight-bearing. Length/width compare reasonably; arch and heel width legitimately differ between the two.

## What the pipeline does about it (built)

- **Isolates the foot** before reconstruction: the **vision LLM locates the foot** in each frame and we **crop** to it. Cropping (not masking) drops the leg/other-foot/clutter yet keeps local texture so photogrammetry can still align cameras — full masking strips those features and collapses the mesh. (Naive colour/skin masking also fails: the light floor reads as skin.)
- **Repairs** the photogrammetry hole (pymeshfix) before any ray casting.
- **Adaptive orientation** (leg-crop + physics stable-pose) that self-checks and falls back rather than degrading.
- **Flags bad numbers instead of shipping them:** `scale_reliable`, `width_reliable`, `arch_reliable` + human-readable warnings, surfaced to the reviewer.

## What to expect — current data vs upgraded capture

| Measurement | Current data (non-WB, no marker, cluttered) | Upgraded capture (WB, foot-framed, plain bg, marker/LiDAR) |
|---|---|---|
| Foot length | Reliable **shape**, anchored to tracing | **±1–2 mm** metric |
| Foot width | Best-effort, flagged when floor fuses | **±1–2 mm** metric |
| Arch height | **Not clinically reliable** (flagged) | Reliable (weight-bearing) |
| Real-world scale | Shape-only (flagged) | **Metric** (marker/LiDAR) |
| Biomechanics (arch type / pronation) | Indicative | Reliable |

## The capture protocol that unlocks full accuracy

1. **Weight-bearing** — patient standing on a glass plate, camera underneath (or standing normally for dorsal/side views). Unlocks arch height.
2. **Frame to the ankle** — minimise leg in shot. Unlocks clean orientation.
3. **Plain, uncluttered background** — or our segmentation step handles it. Removes floor fusion.
4. **A scale reference in frame** — an A4 sheet or a credit card beside the foot, **or** a LiDAR-equipped phone. Unlocks metric scale — the one thing nothing downstream can fix.
5. **Good coverage** — ~30–60 frames or a slow orbit video; even lighting. Improves reconstruction density.

> The single highest-leverage change is the **capture protocol**. Software (segmentation, repair, orientation, flagging) mitigates a lot, but scale and weight-bearing arch require the capture to provide them.
