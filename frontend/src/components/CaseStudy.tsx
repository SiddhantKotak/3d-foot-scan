import { useEffect, useRef, useState } from "react";
import { renderUrl } from "../api";
import type { CaseFoot, CaseStudyData } from "../types";
import { DimLine, CalloutTag } from "./Worksheet";
import FootViewer from "./FootViewer";
import caseData from "../data/caseStudy.json";

const data = caseData as unknown as CaseStudyData;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const ref: any = (caseData as any).reference;

// The real pipeline is a sequence, so numbered stages carry true order.
const PIPELINE: { label: string }[] = [
  { label: "Upload" },
  { label: "Quality gate" },
  { label: "Reconstruct" },
  { label: "Measure" },
  { label: "Vision read" },
  { label: "Review" },
];

const HERO_VIEW = "capture";
const REF_STRIP: { key: string; label: string }[] = [
  { key: "plantar_top", label: "plantar" },
  { key: "overlay_plantar", label: "outline" },
  { key: "overlay_section", label: "midfoot" },
];
const STRIP_VIEWS: { key: string; label: string; kind: "render" | "overlay" }[] =
  [
    { key: "plantar_top", label: "3D scan · plantar", kind: "render" },
    { key: "medial_side", label: "3D scan · medial", kind: "render" },
    { key: "posterior_heel", label: "3D scan · heel", kind: "render" },
    { key: "overlay_plantar", label: "Overlay · plantar", kind: "overlay" },
    { key: "overlay_section", label: "Overlay · section", kind: "overlay" },
  ];

const num = (n: number | null | undefined, d = 1): string =>
  n == null ? "-" : Number(n).toFixed(d);

const pct = (c: number | string | undefined): string => {
  if (c == null) return "-";
  const n = Number(c);
  return Number.isNaN(n) ? String(c) : `${Math.round(n * 100)}%`;
};

// --- motion helpers -------------------------------------------------------
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const on = () => setReduced(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return reduced;
}

// Adds a class once the element scrolls into view (one-shot).
function useInView<T extends HTMLElement>(threshold = 0.25) {
  const nodeRef = useRef<T | null>(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = nodeRef.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          setInView(true);
          io.disconnect();
        }
      },
      { threshold },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [threshold]);
  return { nodeRef, inView };
}

function useCountUp(target: number, run: boolean, reduced: boolean, ms = 950) {
  const [val, setVal] = useState(0);
  useEffect(() => {
    if (!run) return;
    if (reduced) {
      setVal(target);
      return;
    }
    let raf = 0;
    let start = 0;
    const step = (t: number) => {
      if (!start) start = t;
      const p = Math.min(1, (t - start) / ms);
      const eased = 1 - Math.pow(1 - p, 3);
      setVal(target * eased);
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, run, reduced, ms]);
  return val;
}

export default function CaseStudy() {
  const [zoom, setZoom] = useState<string | null>(null);
  const SHOW_PAST = false; // client (past) data hidden; reference scan is the focus
  const reduced = usePrefersReducedMotion();
  const refBlock = useInView<HTMLElement>(0.12);
  const measBlock = useInView<HTMLOListElement>(0.4);
  const delivers = useInView<HTMLElement>(0.2);

  const m = ref?.measurements ?? {};
  const rows = [
    { label: "Length", value: m.length_mm, reliable: true, sub: "anchored to GT" },
    { label: "Width", value: m.width_mm, reliable: !!m.width_reliable, sub: "pose-limited" },
    { label: "Arch height", value: m.arch_height_mm, reliable: !!m.arch_reliable, sub: "pose-limited" },
  ];

  return (
    <div className="case">
      <header className="mast">
        <span className="sheet-eyebrow mast__eyebrow">
          Case study · foot-scan pipeline
        </span>
        <h1 className="mast__title">
          Foot scan <span className="mast__arrow" aria-hidden="true">→</span>{" "}
          insole
        </h1>
        <p className="mast__deck">
          A batch of foot photos becomes a validated set of insole measurements.
          Reconstruction runs on KIRI photogrammetry, geometry is measured in a
          canonical millimetre frame, and Claude reads the biomechanics, with
          every number checked against ground truth and flagged the moment it
          can't be trusted.
        </p>
        <dl className="mast__meta">
          <MetaField label="Subject" value="Reference foot scan" />
          <MetaField label="Method" value="Photogrammetry → KIRI" />
          <MetaField label="Ground truth" value="A4 tracing · 245 mm" />
          <MetaField label="Orchestration" value="LangGraph · Claude" />
        </dl>
        <ol className="flow" aria-label="Pipeline stages">
          {PIPELINE.map((s, i) => (
            <li
              key={s.label}
              className="flow__step"
              style={{ ["--d"]: `${i * 90}ms` } as React.CSSProperties}
            >
              <span className="flow__n mono">{String(i + 1).padStart(2, "0")}</span>
              <span className="flow__t">{s.label}</span>
            </li>
          ))}
        </ol>
        {SHOW_PAST && (
          <dl className="formfields">
            <FormField label="Capture" value={data.capture} />
            <FormField label="Ground truth" value={data.ground_truth_source} />
          </dl>
        )}
      </header>

      {ref && (
        <section
          ref={refBlock.nodeRef}
          className={`refscan reveal ${refBlock.inView ? "is-in" : ""}`}
        >
          <div className="refscan__stage">
            <div className="io">
              {ref.renders?.capture && (
                <figure className="capture">
                  <button
                    type="button"
                    className="capture__btn"
                    onClick={() => setZoom(renderUrl(ref.scan_id, ref.renders.capture))}
                  >
                    <img
                      src={renderUrl(ref.scan_id, ref.renders.capture)}
                      alt="Captured foot"
                    />
                  </button>
                  <figcaption className="capture__cap mono">
                    <span className="capture__dot" /> capture · input
                  </figcaption>
                </figure>
              )}

              <div className="refscan__frame">
                <FootViewer
                  src={renderUrl(ref.scan_id, "foot.glb")}
                  poster={renderUrl(ref.scan_id, ref.renders.medial_side)}
                />
                <span className="refscan__corner refscan__corner--tl" aria-hidden="true" />
                <span className="refscan__corner refscan__corner--br" aria-hidden="true" />
                <span className="refscan__tag mono">3D · live mesh</span>
              </div>
            </div>

            <div className="refscan__strip">
              {REF_STRIP.filter((v) => ref.renders?.[v.key]).map((v) => (
                <button
                  key={v.key}
                  type="button"
                  className="refscan__thumb"
                  onClick={() => setZoom(renderUrl(ref.scan_id, ref.renders[v.key]))}
                >
                  <img
                    src={renderUrl(ref.scan_id, ref.renders[v.key])}
                    alt={`Foot ${v.label}`}
                    loading="lazy"
                  />
                  <span>{v.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="refscan__info">
            <span className="sheet-eyebrow">3D reconstruction</span>
            <h2 className="refscan__title">{ref.title}</h2>
            <p className="refscan__note">{ref.note}</p>

            <div className="spec">
              <div className="spec__head">
                <h3 className="spec__title">Measurements</h3>
                <span className="spec__unit mono">millimetres</span>
              </div>
              <ol
                ref={measBlock.nodeRef}
                className={`mstack ${measBlock.inView ? "is-in" : ""}`}
              >
                {rows.map((r, i) => (
                  <MeasureRow
                    key={r.label}
                    index={i}
                    label={r.label}
                    value={r.value}
                    reliable={r.reliable}
                    sub={r.sub}
                    run={measBlock.inView}
                    reduced={reduced}
                  />
                ))}
              </ol>
              {ref.flag_note && <p className="spec__note">{ref.flag_note}</p>}
            </div>

            <div className="read">
              <div className="read__head">
                <h3 className="read__title">AI biomechanics read</h3>
                <span className="chip chip--live">{ref.vision?.source}</span>
              </div>
              <div className="read__grid">
                <ReadCell label="Arch type" value={ref.vision?.arch_type} big />
                <ReadCell label="Pronation" value={ref.vision?.pronation} big />
                <ReadCell label="Confidence" value={pct(ref.vision?.confidence)} big />
              </div>
              {ref.vision?.pressure_zones?.length > 0 && (
                <div className="read__zones">
                  <span className="read__zones-label mono">Load zones</span>
                  {ref.vision.pressure_zones.map((z: string) => (
                    <span key={z} className="zone">
                      {z}
                    </span>
                  ))}
                </div>
              )}
              {ref.vision?.notes && <p className="read__notes">{ref.vision.notes}</p>}
            </div>

            {ref.attribution && (
              <p className="refscan__attr">{ref.attribution}</p>
            )}
          </div>
        </section>
      )}

      <section
        ref={delivers.nodeRef}
        className={`delivers reveal ${delivers.inView ? "is-in" : ""}`}
      >
        <div className="delivers__head">
          <span className="sheet-eyebrow">Scope</span>
          <h2 className="delivers__title">What the pipeline delivers</h2>
        </div>
        <ul className="delivers__grid">
          {data.solved.map((s, i) => (
            <li
              key={i}
              className="delivers__item"
              style={{ ["--d"]: `${i * 70}ms` } as React.CSSProperties}
            >
              <Check className="delivers__ico" />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      </section>

      {SHOW_PAST && (
        <section className="case__feet">
          {data.feet.map((foot) => (
            <FootPlate key={foot.side} foot={foot} onZoom={setZoom} />
          ))}
        </section>
      )}

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
    </div>
  );
}

function MeasureRow({
  index,
  label,
  value,
  reliable,
  sub,
  run,
  reduced,
}: {
  index: number;
  label: string;
  value: number | null | undefined;
  reliable: boolean;
  sub: string;
  run: boolean;
  reduced: boolean;
}) {
  const counted = useCountUp(value ?? 0, run, reduced);
  const shown = value == null ? "-" : counted.toFixed(1);
  return (
    <li
      className="mline"
      style={{ ["--d"]: `${index * 150}ms` } as React.CSSProperties}
    >
      <span className="mline__label mono">{label}</span>
      <span className="mline__bar" aria-hidden="true">
        <i className="mline__cap" />
        <i className="mline__rule mline__rule--l" />
        <span className="mline__val mono">
          {shown}
          <em>mm</em>
        </span>
        <i className="mline__rule mline__rule--r" />
        <i className="mline__cap" />
      </span>
      <span className={`mline__flag mono ${reliable ? "is-ok" : "is-warn"}`}>
        <i className="mline__flagdot" aria-hidden="true" />
        {reliable ? "reliable" : "flagged"}
        <em>{sub}</em>
      </span>
    </li>
  );
}

function FootPlate({
  foot,
  onZoom,
}: {
  foot: CaseFoot;
  onZoom: (url: string) => void;
}) {
  const m = foot.measurements;
  const v = foot.validation;
  const vision = foot.vision;
  const mockSource = String(vision.source ?? "").toLowerCase().includes("mock");
  const heroKey = foot.renders[HERO_VIEW] ? HERO_VIEW : "plantar_top";
  const heroIsPhoto = heroKey === "capture";
  const heroSrc = foot.renders[heroKey]
    ? renderUrl(foot.scan_id, foot.renders[heroKey])
    : null;

  return (
    <article className="plate">
      <header className="plate__head">
        <h2 className="plate__title">{foot.side} foot</h2>
        <span className="mono plate__scan">scan · {foot.scan_id}</span>
      </header>

      {heroSrc && (
        <figure className="plate__hero">
          <button
            type="button"
            className="plate__hero-btn"
            onClick={() => onZoom(heroSrc)}
          >
            <img
              src={heroSrc}
              alt={`${foot.side} foot, ${heroIsPhoto ? "capture photo" : "plantar render"}`}
            />
          </button>
          <figcaption className="plate__caption">
            <span className="plate__caption-view">
              {heroIsPhoto ? "Capture · plantar photo" : "Plantar view"}
            </span>
            <span className="plate__caption-note">
              {heroIsPhoto ? "Input capture" : "Standardized render"} · {foot.side} foot
            </span>
          </figcaption>
        </figure>
      )}

      <div className="plate__strip">
        {STRIP_VIEWS.filter((view) => foot.renders[view.key]).map((view) => (
          <figure key={view.key} className={`shot shot--${view.kind}`}>
            <button
              type="button"
              className="shot__btn"
              onClick={() => onZoom(renderUrl(foot.scan_id, foot.renders[view.key]))}
            >
              <img
                src={renderUrl(foot.scan_id, foot.renders[view.key])}
                alt={`${foot.side} foot, ${view.label}`}
                loading="lazy"
              />
            </button>
            <figcaption>{view.label}</figcaption>
          </figure>
        ))}
      </div>

      <div className="plate__block">
        <h3 className="sheet-h3">Measurements</h3>
        <div className="dims">
          <div className="dimrow">
            <DimLine label="Length" value={m.length_mm} />
            <CalloutTag reliable okLabel="anchored to gt" />
          </div>
          <div className="dimrow">
            <DimLine label="Width" value={m.width_mm} />
            <CalloutTag
              reliable={m.width_reliable}
              reason="Width flagged: floor/clutter likely fused into the foot mesh, or a mis-orientation inflated it."
            />
          </div>
          <div className="dimrow">
            <DimLine label="Arch height" value={m.arch_height_mm} />
            <CalloutTag
              reliable={m.arch_reliable}
              reason="Arch height is not clinically reliable: non-weight-bearing capture with no floor reference."
            />
          </div>
        </div>
      </div>

      <div className="plate__block">
        <h3 className="sheet-h3">Validation vs ground truth</h3>
        <table className="dtable dtable--val">
          <thead>
            <tr>
              <th />
              <th>meas</th>
              <th>gt</th>
              <th>dev</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Length</th>
              <td className="mono">{num(m.length_mm)}</td>
              <td className="mono">{num(v.gt_length_mm)}</td>
              <td className="mono">{num(v.length_dev_mm)}</td>
            </tr>
            <tr>
              <th>Width</th>
              <td className="mono">{num(m.width_mm)}</td>
              <td className="mono">{num(v.gt_width_mm)}</td>
              <td className="mono dtable__dev">{num(v.width_dev_mm)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="plate__block">
        <h3 className="sheet-h3">
          AI biomechanics read
          <span className={`chip ${mockSource ? "chip--mock" : "chip--live"}`}>
            {vision.source}
          </span>
        </h3>
        <div className="bio">
          <BioCell label="Arch type" value={vision.arch_type} />
          <BioCell label="Pronation" value={vision.pronation} />
          <BioCell label="Confidence" value={pct(vision.confidence)} />
        </div>
        {vision.notes && <p className="bio__notes">{vision.notes}</p>}
      </div>
    </article>
  );
}

function MetaField({ label, value }: { label: string; value: string }) {
  return (
    <div className="mast__field">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function FormField({ label, value }: { label: string; value: string }) {
  return (
    <div className="formfield">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function ReadCell({
  label,
  value,
  big,
}: {
  label: string;
  value?: string;
  big?: boolean;
}) {
  return (
    <div className={`read__cell ${big ? "read__cell--big" : ""}`}>
      <span className="read__label mono">{label}</span>
      <span className="read__value">{value ?? "-"}</span>
    </div>
  );
}

function BioCell({ label, value }: { label: string; value?: string }) {
  return (
    <div className="bio__cell">
      <span className="bio__label">{label}</span>
      <span className="bio__value">{value ?? "-"}</span>
    </div>
  );
}

function Check({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 16 16"
      width="14"
      height="14"
      className={className}
      aria-hidden="true"
    >
      <path
        d="M3 8.5l3 3 7-8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.4"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
