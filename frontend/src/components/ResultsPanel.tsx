import { renderUrl } from "../api";
import type { ScanState } from "../types";
import { DimLine } from "./Worksheet";

interface Props {
  scanId: string;
  state: ScanState;
  onNewScan: () => void;
}

export default function ResultsPanel({ scanId, state, onNewScan }: Props) {
  const spec = state.insole_spec;
  const geom = state.geometry;
  const vision = state.vision;
  const renders = state.render_paths ?? {};
  const scaleUnreliable = geom?.scale?.reliable === false;

  // No spec means the run stopped early (quality block or reconstruction failure).
  if (!spec) {
    const reasons = state.quality?.batch_reasons ?? state.errors ?? [];
    return (
      <section className="panel results results--halted">
        <span className="sheet-eyebrow">Run ended early</span>
        <h2 className="panel-title">No insole spec produced</h2>
        <p className="results__halt">
          Status: <span className="mono">{state.status ?? "unknown"}</span>
        </p>
        {reasons.length > 0 && (
          <ul className="notes">
            {reasons.map((r, i) => (
              <li key={i} className="notes__warn">
                {r}
              </li>
            ))}
          </ul>
        )}
        <button type="button" className="btn btn--primary" onClick={onNewScan}>
          Start a new scan
        </button>
      </section>
    );
  }

  return (
    <section className="panel results">
      <header className="results__head">
        <div>
          <span className="sheet-eyebrow">Final output</span>
          <h2 className="panel-title">Insole spec</h2>
        </div>
        <span
          className={`stamp ${spec.approved ? "stamp--approved" : "stamp--recorded"}`}
        >
          {spec.approved ? "Approved" : "Recorded"}
        </span>
      </header>

      {scaleUnreliable && (
        <div className="banner banner--warn" role="note">
          <span className="banner__tag">Shape-only</span>
          <div className="banner__body">
            <strong>Absolute sizes below are uncalibrated.</strong> No in-frame
            reference was in the capture — add an A4 sheet or bank card in frame,
            or use LiDAR, before manufacturing.
          </div>
        </div>
      )}

      <div className="dims dims--readout">
        <DimLine label="Length" value={spec.length_mm} size="lg" />
        <DimLine label="Width" value={spec.width_mm} size="lg" />
        <DimLine label="Arch height" value={spec.arch_height_mm} size="lg" />
      </div>

      <dl className="spec">
        <SpecRow label="Foot side" value={spec.foot_side} />
        <SpecRow label="Arch type" value={spec.arch_type} />
        <SpecRow label="Arch support" value={spec.arch_support} />
        {vision?.pronation && (
          <SpecRow label="Pronation" value={vision.pronation} />
        )}
        {geom?.scale?.method && (
          <SpecRow label="Scale method" value={geom.scale.method} />
        )}
      </dl>

      {Object.keys(renders).length > 0 && (
        <div className="results__strip">
          {["plantar_top", "medial_side", "posterior_heel"]
            .filter((k) => renders[k])
            .map((k) => (
              <img
                key={k}
                src={renderUrl(scanId, renders[k])}
                alt={k}
                loading="lazy"
              />
            ))}
        </div>
      )}

      {spec.note && <p className="results__note">{spec.note}</p>}

      <button type="button" className="btn btn--ghost" onClick={onNewScan}>
        Start a new scan
      </button>
    </section>
  );
}

function SpecRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="spec__row">
      <dt>{label}</dt>
      <dd>{value ?? "—"}</dd>
    </div>
  );
}
