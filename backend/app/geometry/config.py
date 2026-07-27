"""Canonical constants for the geometry/measurement core.

Every downstream stage assumes the canonical frame established by ``align``:
  +Y = up, floor plane at Y = 0 (sole rests on the floor)
  Z  = length axis, heel at Z=0 -> toe at Z=+max
  X  = width axis, medial (big-toe) side = +X
All measurements are computed in **millimetres** (ground truth and the
clinical tolerance are in mm).
"""
from __future__ import annotations

import numpy as np

# --- axis convention (indices into a 3-vector) ---
UP_AXIS = 1      # Y
WIDTH_AXIS = 0   # X
LENGTH_AXIS = 2  # Z
CANONICAL_UP = np.array([0.0, 1.0, 0.0])

# --- arch measurement ---
# The true arch peak is NOT reliably at 50% of foot length; scan a band and
# take the max clearance across slices.
ARCH_SCAN_FRACTION = (0.35, 0.65)  # fraction of foot length, heel = 0
ARCH_SLICE_COUNT = 21
MEDIAL_HALF_FRACTION = 0.5          # rays cast only over the medial half of width

# --- ball-of-foot width search band (fraction of length from heel) ---
BALL_WIDTH_BAND = (0.55, 0.82)

# --- clinical accuracy benchmark ---
# A 2025 scanner-choice study used +/-1 mm as the "in tolerance" bar for
# orthotic design; we validate against the same benchmark.
CLINICAL_TOLERANCE_MM = 1.0

# --- floor detection (weight-bearing) ---
FLOOR_BAND_FRACTION = 0.15   # lowest 15% of Y-extent used to fit the floor plane
FLOOR_RANSAC_RESIDUAL_MM = 3.0

# --- rendering ---
RENDER_PX = (2200, 2200)

# --- reference object real-world dimensions (mm) ---
A4_MM = (210.0, 297.0)                 # short x long
CREDIT_CARD_MM = (53.98, 85.60)        # ISO/IEC 7810 ID-1
