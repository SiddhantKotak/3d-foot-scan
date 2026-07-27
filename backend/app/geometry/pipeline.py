"""measure_foot() — the geometry contract and the body of the LangGraph
`measure` node.

Deterministic, self-contained, and never throws for a "bad" mesh: it downgrades
(``ok=False`` + warnings) so the graph can route to human review instead of
crashing. Order is load -> scale -> align -> repair (BEFORE ray casting) ->
measure -> validate -> render.
"""
from __future__ import annotations

from typing import Any

from . import align, io_mesh, measure as measure_mod, render, repair, scale
from .types import FootSide, GeometryResult, Posture


def measure_foot(
    mesh_path: str,
    *,
    foot_side: FootSide,
    posture: Posture = "weight_bearing",
    scale_hint: dict[str, Any] | None = None,
    out_dir: str = "./out",
    do_render: bool = True,
    keep_all_components: bool = False,
) -> GeometryResult:
    warnings: list[str] = []

    # 1. load + clean (STL vertex-merge trap handled inside)
    mesh = io_mesh.load_and_clean(mesh_path, keep_all_components=keep_all_components)
    native = io_mesh.describe(mesh)

    # 2. scale calibration (the #1 failure mode) -> millimetres
    scale_res = scale.resolve_scale(mesh, scale_hint)
    if scale_res.reliable:
        mesh.apply_scale(scale_res.mm_per_unit)
    else:
        warnings.append("scale unresolved: measurements are shape-only, not metric")
        # Provisionally normalise into a millimetre range so every alignment /
        # measurement threshold (floor bands, medial contact test) behaves the
        # same as on a truly metric mesh. Final anchoring happens after align.
        prov = 250.0 / float(max(mesh.extents))
        mesh.apply_scale(prov)
        scale_res.source_detail["provisional_norm_factor"] = round(prov, 6)

    # 3. canonical frame (mesh now in mm range)
    aligned, frame_info = align.build_canonical_frame(mesh, posture, foot_side)
    warnings.extend(frame_info.get("warnings", []))

    # 4. repair BEFORE any ray casting (open sole -> impossible arch reading)
    repaired, repair_info = repair.repair_for_raycast(aligned)
    if not repair_info.get("output_watertight"):
        warnings.append("mesh not watertight after repair: arch uses section fallback")

    # If scale was unreliable, anchor shape to GT length so downstream numbers
    # are comparable (clearly flagged as best-fit, not recovered scale).
    if not scale_res.reliable:
        length0 = measure_mod.measure_length_mm(repaired)["length_mm"]
        if length0 > 0:
            factor = scale.best_fit_scale_to_ground_truth(length0, foot_side)
            # repair_for_raycast returns the SAME object when the mesh is already
            # watertight, so scale each distinct mesh exactly once.
            for m in {id(aligned): aligned, id(repaired): repaired}.values():
                m.apply_scale(factor)
            scale_res.source_detail["best_fit_factor_to_gt"] = round(factor, 4)
    frame_info["aligned_extents_mm"] = [round(float(v), 2) for v in aligned.extents]

    # 5. measurements
    length = measure_mod.measure_length_mm(repaired)
    width = measure_mod.measure_width_mm(repaired, length["length_mm"])
    arch_engine = "ray" if repair_info.get("output_watertight") else "section"
    arch = measure_mod.measure_arch_height_mm(repaired, length["length_mm"], engine=arch_engine)
    mid = measure_mod.midfoot_cross_section(repaired, length["length_mm"])

    measurements = {
        "length_mm": length["length_mm"],
        "width_mm": width["width_mm"],
        "ball_width_fraction": width["ball_width_fraction"],
        "arch_height_mm": arch["arch_height_mm"],
        "arch_peak_fraction": arch["arch_peak_fraction"],
        "arch_engine": arch["engine"],
        "arch_profile": arch["per_slice_profile"],
        "midfoot": mid,
        "native_snapshot": native,
    }

    # Honesty flags — the PoC's whole point is to catch bad numbers, not ship
    # them. Arch is trustworthy only from a weight-bearing, well-oriented foot in
    # the physiological range; flag it otherwise.
    arch_mm = arch["arch_height_mm"]
    arch_reliable = (posture == "weight_bearing") and (0.0 <= arch_mm <= 40.0)
    measurements["arch_reliable"] = arch_reliable
    if not arch_reliable:
        reason = ("non-weight-bearing capture" if posture != "weight_bearing"
                  else "value outside physiological range")
        warnings.append(
            f"arch height {arch_mm:.0f} mm is NOT clinically reliable ({reason}); "
            "causes: non-weight-bearing pose, leg-in-scan, or noisy reconstruction")

    # Width sanity: a human foot is ~70-135 mm wide. Far outside that means the
    # foot could not be isolated from the reconstruction (floor/clutter fused in)
    # or the pose is wrong -> flag it instead of shipping a wrong width.
    width_mm = width["width_mm"]
    width_reliable = 70.0 <= width_mm <= 135.0
    measurements["width_reliable"] = width_reliable
    if not width_reliable:
        warnings.append(
            f"width {width_mm:.0f} mm is implausible (foot ~70-135 mm); likely "
            "floor/clutter fused into the foot mesh or a mis-orientation")

    # 6. accuracy validation vs A4-tracing ground truth
    validation = scale.validate_against_tracing(
        length["length_mm"], width["width_mm"], foot_side, scale_res.reliable,
    ).to_dict()

    # 7. standardized renders
    renders: dict[str, str] = {}
    if do_render:
        try:
            # Render the real captured surface (aligned), never the repaired mesh:
            # hole-fill geometry (cap/pymeshfix) can add non-anatomical faces the
            # vision LLM should not see.
            renders = render.render_standard_views(aligned, out_dir)
            renders.update(render.render_measurement_overlays(aligned, measurements, out_dir))
        except Exception as e:  # pragma: no cover - rendering is non-fatal
            warnings.append(f"render failed: {e}")

    # low-confidence if the foot couldn't be measured plausibly (e.g. floor
    # fused in -> implausible width); the graph still routes to human review, but
    # flagged, so a bad measurement is never treated as clean.
    ok = length["length_mm"] > 0 and width_reliable
    return GeometryResult(
        ok=ok,
        measurements=measurements,
        scale=scale_res.to_dict(),
        alignment=frame_info,
        repair=repair_info,
        validation=validation,
        renders=renders,
        warnings=warnings,
    )
