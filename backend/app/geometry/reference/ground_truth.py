"""Hand-traced ground truth from the client's A4 foot tracings.

These are the physical measurements the podiatrist annotated on A4 paper while
the patient stood (weight-bearing). They are our accuracy oracle: the geometry
pipeline's length/width are validated against these at the +/-1 mm clinical bar.

Source: data/Foot Tracing 1.jpeg (LEFT) and data/Foot Tracing 2.jpeg (RIGHT),
patient "MS LEUNG", ref 21 T02/46/012.
"""
from __future__ import annotations

# length x width in millimetres, plus capture posture of the tracing.
GROUND_TRUTH_MM = {
    "left":  {"length": 245.0, "width": 95.0},
    "right": {"length": 240.0, "width": 95.0},
}

# The tracings were made standing on paper -> weight-bearing. Arch height is
# posture-dependent, so arch is NOT directly comparable to a non-weight-bearing
# scan; length/width are.
GROUND_TRUTH_POSTURE = "weight_bearing"
