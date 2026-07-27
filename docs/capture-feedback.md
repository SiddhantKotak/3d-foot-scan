# Foot Scan — Capture Quality Feedback

**Bottom line:** The current photo sets can't produce a reliable 3D reconstruction. Our pipeline runs end‑to‑end and correctly *flags* the problems, but the **input is the limiter** — no software step can recover what the capture didn't record. Below is exactly what's wrong, by the numbers, and what a usable capture needs.

---

## What we received
- **20 photos per foot** (left + right), handheld.
- **Posture: non‑weight‑bearing** — patient seated, foot lifted, sole to camera.
- **Scale reference in frame: none.**
- A4 foot tracings (weight‑bearing) — usable only as a rough ground‑truth number, not as scan input.

---

## The faults — specific

**1. Too few images — 20 per foot (need 40–80+).**
Photogrammetry builds 3D by matching the *same points across overlapping photos*. 20 frames is roughly a quarter to a half of the minimum for a dense, coherent mesh → sparse, holey reconstructions.

**2. Non‑weight‑bearing (foot held in the air).**
- There is **no floor/ground plane** in the scan → **arch height can't be measured** (it came out **38–74 mm**; a real arch is **~15–30 mm**).
- A lifted foot **shifts between shots** → inconsistent geometry → the mesh **fragmented into up to 71 disconnected pieces.**

**3. No scale reference in frame — the single most damaging fault.**
Photogrammetry recovers **shape, not size.** With no A4 sheet, bank card, or ruler beside the foot, the mesh has **no real‑world units** → every measurement is "shape‑only," and **nothing downstream can fix it.**

**4. Cluttered scene — the whole room is captured.**
Floor tiles, the red chair, a bag, trousers, and the **second foot** are all in frame. The reconstructor rebuilds the **floor and fuses it into the foot**, so measured **width came out 189–210 mm — a foot is ~95 mm** (a ~100 mm error).

**5. Foot + lower leg in the same frame.**
A large leg section is included, so automatic orientation can't reliably separate **foot length from leg length.**

**6. Smooth, low‑texture skin.**
Feature‑matching needs surface detail; bare sole skin has almost none → very few points match → the isolated foot came out as low as **~800–4,500 vertices** (a clean foot scan is **~84,000–168,000**).

**7. Limited, uneven angular coverage.**
Only **~19 of 20 frames were distinct viewpoints** (the rest near‑duplicates), and all from the narrow arc reachable on a lifted foot — **no consistent 360° orbit**, with gaps (top of foot, between toes).

**8. Some frames borderline (blur / low sharpness).**
Smooth‑skin frames sit at the low end of the sharpness range, and **up to ~2 of 20 per foot are too soft to use** — thinning already‑sparse coverage further.

**9. Posture mismatch for validation.**
Tracings are **weight‑bearing**, scans are **non‑weight‑bearing** — so arch height and heel width aren't directly comparable between them.

---

## What the reconstruction actually produced (evidence)
| Measure | From this data | Reality | Cause |
|---|---|---|---|
| **Foot width** | 189–210 mm | ~95 mm | floor fused into the mesh |
| **Arch height** | 38–74 mm | ~15–30 mm | no floor + fragmentation |
| **Foot mesh density** | ~800–4,500 verts | ~100,000+ | too few photos + low texture |
| **Real‑world scale** | unresolved (shape‑only) | metric | no in‑frame reference |
| **Mesh integrity** | up to 71 fragments | one solid piece | foot moved between shots |

---

## What a usable capture needs — checklist
- ✅ **Weight‑bearing** — patient standing, foot **loaded** (e.g. on a glass plate, camera underneath), so the arch is real.
- ✅ **40–80 frames** or a slow, steady **orbit video** — heavy overlap, full **360°** coverage.
- ✅ **A scale reference in every shot** — an **A4 sheet or a bank card** flat beside the foot, **or** a **LiDAR‑equipped phone.**
- ✅ **Frame to the ankle** — minimise leg; **one foot per capture.**
- ✅ **Plain background, ideally a textured mat** under the foot (gives the software features to lock onto).
- ✅ **Even, diffuse lighting; sharp focus** — no motion blur, no harsh shadows.

> With those, the *same* pipeline produces clean, **metric, weight‑bearing** measurements at the **±1–2 mm** clinical bar.
