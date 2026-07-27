import { useState } from "react";
import { renderUrl } from "../api";
import { DimLine } from "./Worksheet";
import type {
  Measurements,
  ReviewEdits,
  ReviewInterrupt,
  Validation,
  Vision,
} from "../types";

interface Props {
  scanId: string;
  interrupt: ReviewInterrupt;
  onDecision: (approved: boolean, edits: ReviewEdits) => void;
}

const VIEWS: { key: string; label: string; kind: "render" | "overlay" }[] = [
  { key: "plantar_top", label: "Plantar · top", kind: "render" },
  { key: "medial_side", label: "Medial · side", kind: "render" },
  { key: "posterior_heel", label: "Posterior · heel", kind: "render" },
  { key: "overlay_plantar", label: "Overlay · plantar", kind: "overlay" },
  { key: "overlay_section", label: "Overlay · section", kind: "overlay" },
];

const num = (n: number | null | undefined, d = 1): string =>
  n == null ? "—" : Number(n).toFixed(d);

export default function ReviewPanel({ scanId, interrupt, onDecision }: Props) {
  const m = interrupt.measurements ?? ({} as Measurements);
  const v = interrupt.validation ?? ({} as Validation);
  const vision = interrupt.vision ?? ({} as Vision);
  const warnings = interrupt.warnings ?? [];
  const renders = interrupt.render_paths ?? {};

  const scaleUnreliable = v.scale_reliable === false;
  const [zoom, setZoom] = useState<string | null>(null);

  const [edits, setEdits] = useState({
    length_mm: str(m.length_mm),
    width_mm: str(m.width_mm),
    arch_height_mm: str(m.arch_height_mm),
  });

  function submit(approved: boolean) {
    const out: ReviewEdits = {};
    (["length_mm", "width_mm", "arch_height_mm"] as const).forEach((k) => {
      const raw = edits[k].trim();
      if (raw === "") return;
      const val = Number(raw);
      if (!Number.isNaN(val) && val !== (m[k] ?? null)) out[k] = val;
    });
    onDecision(approved, out);
  }

  return (
    <section className="panel review">
      <header className="review__head">
        <div>
          <span className="sheet-eyebrow">Human in the loop</span>
          <h2 className="panel-title">Podiatrist review</h2>
        </div>
        <p className="review__lead">
          The pipeline is paused. Confirm the measurements, adjust anything that
          looks off, then approve to write the insole spec.
        </p>
      </header>

      {scaleUnreliable ? (
        <div className="banner banner--warn" role="alert">
          <span className="banner__tag">Scale not calibrated</span>
          <div className="banner__body">
            <strong>Measurements are shape-only.</strong> No in-frame size
            reference was detected, so absolute millimetre values are not
            trustworthy — the foot’s <em>proportions</em> are reliable, its
            absolute <em>size</em> is not.
            <span className="banner__fix">
              Fix: include an A4 sheet or a bank card flat in frame, or capture
              with a LiDAR-equipped device.
            </span>
          </div>
        </div>
      ) : (
        v.scale_reliable === true && (
          <div className="banner banner--ok">
            <span className="banner__tag">Scale calibrated</span>
            <div className="banner__body">
              An in-frame reference was detected — absolute millimetre values are
              trustworthy within tolerance.
            </div>
          </div>
        )
      )}

      {/* Renders */}
      <div className="review__block">
        <h3 className="sheet-h3">3D renders</h3>
        <div className="renders">
          {VIEWS.filter((view) => renders[view.key]).map((view) => (
            <figure key={view.key} className={`render render--${view.kind}`}>
              <button
                type="button"
                className="render__btn"
                onClick={() => setZoom(renderUrl(scanId, renders[view.key]))}
              >
                <img
                  src={renderUrl(scanId, renders[view.key])}
                  alt={view.label}
                  loading="lazy"
                />
              </button>
              <figcaption>{view.label}</figcaption>
            </figure>
          ))}
        </div>
      </div>

      <div className="review__cols">
        {/* Measurements */}
        <div className="review__block">
          <h3 className="sheet-h3">Measurements</h3>
          <div className="dims">
            <DimLine label="Length" value={m.length_mm} />
            <DimLine label="Width" value={m.width_mm} />
            <DimLine label="Arch height" value={m.arch_height_mm} />
          </div>
          <table className="dtable">
            <tbody>
              {m.arch_peak_fraction != null && (
                <tr>
                  <th>Arch peak</th>
                  <td className="mono">
                    {num(m.arch_peak_fraction * 100, 0)}% of length
                  </td>
                </tr>
              )}
              {m.midfoot && (
                <tr>
                  <th>Midfoot</th>
                  <td className="mono">
                    {num(m.midfoot.width_mm)} × {num(m.midfoot.height_mm)} mm
                  </td>
                </tr>
              )}
              {m.arch_engine && (
                <tr>
                  <th>Arch engine</th>
                  <td className="mono">{m.arch_engine}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Validation */}
        <div className="review__block">
          <h3 className="sheet-h3">Validation vs ground truth</h3>
          <table className="dtable">
            <tbody>
              <Row
                label="Length dev."
                value={`${num(v.length_dev_mm)} mm`}
                sub={`meas ${num(v.meas_length_mm)} · gt ${num(v.gt_length_mm)}`}
              />
              <Row
                label="Width dev."
                value={`${num(v.width_dev_mm)} mm`}
                sub={`meas ${num(v.meas_width_mm)} · gt ${num(v.gt_width_mm)}`}
              />
              <Row label="Tolerance" value={`± ${num(v.tolerance_mm)} mm`} />
              <tr>
                <th>Within tolerance</th>
                <td>
                  <Flag
                    on={v.within_tolerance === true}
                    off={v.within_tolerance === false}
                    onText="within ±tol"
                    offText="out of tolerance"
                  />
                </td>
              </tr>
              <tr>
                <th>Scale reliable</th>
                <td>
                  <Flag
                    on={v.scale_reliable === true}
                    off={v.scale_reliable === false}
                    onText="calibrated"
                    offText="shape-only"
                    warnOff
                  />
                </td>
              </tr>
            </tbody>
          </table>
          {(v.notes?.length || warnings.length) && (
            <ul className="notes">
              {v.notes?.map((n, i) => (
                <li key={`vn${i}`}>{n}</li>
              ))}
              {warnings.map((n, i) => (
                <li key={`w${i}`} className="notes__warn">
                  {n}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Vision read */}
      <div className="review__block">
        <h3 className="sheet-h3">
          AI biomechanics read
          {vision.source && (
            <span
              className={`chip ${
                String(vision.source).toLowerCase().includes("mock")
                  ? "chip--mock"
                  : "chip--live"
              }`}
            >
              {vision.source}
            </span>
          )}
        </h3>
        <div className="bio">
          <BioCell label="Arch type" value={vision.arch_type} />
          <BioCell label="Pronation" value={vision.pronation} />
          <BioCell label="Weight" value={vision.weight_distribution} />
          <BioCell
            label="Confidence"
            value={
              vision.confidence == null
                ? undefined
                : typeof vision.confidence === "number"
                  ? `${Math.round(vision.confidence * 100)}%`
                  : String(vision.confidence)
            }
          />
        </div>
        {vision.pressure_zones && vision.pressure_zones.length > 0 && (
          <div className="zones">
            {vision.pressure_zones.map((z) => (
              <span key={z} className="zone">
                {z}
              </span>
            ))}
          </div>
        )}
        {vision.notes && <p className="bio__notes">{vision.notes}</p>}
      </div>

      {/* Edit + approve */}
      <div className="review__block review__decide">
        <h3 className="sheet-h3">Adjust &amp; approve</h3>
        <p className="review__editnote">
          Values default to the measured geometry. Change any field to override
          it in the insole spec.
        </p>
        <div className="edits">
          <EditField
            label="Length (mm)"
            value={edits.length_mm}
            onChange={(x) => setEdits((e) => ({ ...e, length_mm: x }))}
          />
          <EditField
            label="Width (mm)"
            value={edits.width_mm}
            onChange={(x) => setEdits((e) => ({ ...e, width_mm: x }))}
          />
          <EditField
            label="Arch height (mm)"
            value={edits.arch_height_mm}
            onChange={(x) => setEdits((e) => ({ ...e, arch_height_mm: x }))}
          />
        </div>
        <div className="review__actions">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => submit(true)}
          >
            Approve &amp; generate spec
          </button>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={() => submit(false)}
          >
            Record without approval
          </button>
        </div>
      </div>

      {zoom && (
        <div
          className="lightbox"
          role="dialog"
          aria-modal="true"
          onClick={() => setZoom(null)}
        >
          <img src={zoom} alt="Render, enlarged" />
          <button type="button" className="lightbox__close" aria-label="Close">
            ×
          </button>
        </div>
      )}
    </section>
  );
}

function str(n: number | null | undefined): string {
  return n == null ? "" : String(Number(n).toFixed(1));
}

function Row({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <tr>
      <th>{label}</th>
      <td>
        <span className="mono">{value}</span>
        {sub && <span className="tbl__sub mono">{sub}</span>}
      </td>
    </tr>
  );
}

function Flag({
  on,
  off,
  onText,
  offText,
  warnOff,
}: {
  on: boolean;
  off: boolean;
  onText: string;
  offText: string;
  warnOff?: boolean;
}) {
  if (on) return <span className="flag flag--ok">{onText}</span>;
  if (off)
    return (
      <span className={`flag ${warnOff ? "flag--warn" : "flag--bad"}`}>
        {offText}
      </span>
    );
  return <span className="flag flag--unknown">n/a</span>;
}

function BioCell({ label, value }: { label: string; value?: string }) {
  return (
    <div className="bio__cell">
      <span className="bio__label">{label}</span>
      <span className="bio__value">{value ?? "—"}</span>
    </div>
  );
}

function EditField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <label className="editfield">
      <span>{label}</span>
      <input
        type="number"
        inputMode="decimal"
        step="0.1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
