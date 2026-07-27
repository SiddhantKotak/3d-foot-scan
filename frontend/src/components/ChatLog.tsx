import type { Health, ScanState, StageName } from "../types";
import { STAGES, STAGE_LABEL } from "../types";

type Phase = "setup" | "running" | "review" | "resuming" | "done" | "error";
type StageData = Partial<Record<StageName, Partial<ScanState>>>;
type RowStatus = "pending" | "active" | "paused" | "done" | "failed" | "skipped";

interface Props {
  scanId: string | null;
  stageData: StageData;
  completed: StageName[];
  activeStage: StageName | null;
  phase: Phase;
  health: Health | null;
  errorMsg: string | null;
}

const mm = (n: number | null | undefined): string =>
  n == null ? "—" : `${Number(n).toFixed(1)} mm`;

const ACTIVE_TEXT: Record<StageName, string> = {
  quality_gate: "Scoring sharpness, exposure and viewpoint diversity…",
  submit_reconstruction: "Uploading images and queuing photogrammetry…",
  await_reconstruction:
    "Reconstructing the 3D mesh — this can take several minutes when KIRI is live.",
  measure: "Cleaning, scaling, aligning and measuring the mesh…",
  vision_read: "Reading arch, pronation and load from the renders…",
  review: "Writing the insole spec…",
};

export default function ChatLog({
  scanId,
  stageData,
  completed,
  activeStage,
  phase,
  errorMsg,
}: Props) {
  const qualityFailed = stageData.quality_gate?.quality?.ok === false;
  const haltIndex = qualityFailed ? STAGES.indexOf("quality_gate") : -1;

  function statusFor(stage: StageName, idx: number): RowStatus {
    if (completed.includes(stage)) {
      const st = stageData[stage]?.status ?? "";
      if (/failed|timeout|rejected/.test(st)) return "failed";
      if (stage === "quality_gate" && qualityFailed) return "failed";
      return "done";
    }
    if (stage === "review" && activeStage === "review" && phase === "review")
      return "paused";
    if (activeStage === stage) return "active";
    if (haltIndex >= 0 && idx > haltIndex) return "skipped";
    return "pending";
  }

  return (
    <section className="log">
      <header className="log__head">
        <h2 className="log__title">Pipeline</h2>
        {scanId && <span className="log__scan mono">scan {scanId}</span>}
      </header>

      <ol className="track">
        {STAGES.map((stage, idx) => {
          const status = statusFor(stage, idx);
          return (
            <li key={stage} className={`track__row track__row--${status}`}>
              <span className="track__rail" aria-hidden="true">
                <span className="track__node">
                  {status === "active" && <span className="spinner" />}
                  {status === "done" && <Check />}
                  {status === "failed" && <span className="track__x">×</span>}
                  {status === "paused" && <span className="track__pause" />}
                </span>
              </span>
              <div className="track__body">
                <div className="track__label">
                  <span>{STAGE_LABEL[stage]}</span>
                  <StatusTag status={status} />
                </div>
                <div className="track__detail">
                  {status === "active" ? (
                    <span className="track__running">{ACTIVE_TEXT[stage]}</span>
                  ) : status === "paused" ? (
                    <span className="track__running">
                      Waiting for your review below.
                    </span>
                  ) : (
                    <Summary stage={stage} data={stageData[stage]} status={status} />
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {errorMsg && (
        <div className="log__error">
          <strong>Pipeline error.</strong> {errorMsg}
        </div>
      )}
    </section>
  );
}

function Summary({
  stage,
  data,
  status,
}: {
  stage: StageName;
  data?: Partial<ScanState>;
  status: RowStatus;
}) {
  if (status === "pending")
    return <span className="track__muted">queued</span>;
  if (status === "skipped")
    return <span className="track__muted">skipped — quality gate blocked run</span>;
  if (!data) return null;

  switch (stage) {
    case "quality_gate": {
      const q = data.quality;
      if (!q) return null;
      if (!q.ok)
        return (
          <span className="track__fail-text">
            Blocked — {(q.batch_reasons ?? []).join("; ") || "unusable batch"}
          </span>
        );
      return (
        <span>
          <span className="mono">
            {q.n_accepted}/{q.n_input}
          </span>{" "}
          images accepted ·{" "}
          <span className="mono">{q.distinct_viewpoints}</span> distinct
          viewpoints
        </span>
      );
    }
    case "submit_reconstruction": {
      const mock = (data.status ?? "").includes("mock");
      return (
        <span>
          Queued at KIRI · task <span className="mono">{data.serialize}</span>
          {mock && <span className="chip chip--mock">mock</span>}
        </span>
      );
    }
    case "await_reconstruction": {
      if (status === "failed")
        return (
          <span className="track__fail-text">
            {(data.errors ?? []).join("; ") || data.status}
          </span>
        );
      return <span>3D mesh reconstructed and downloaded.</span>;
    }
    case "measure": {
      const m = data.geometry?.measurements;
      const reliable = data.geometry?.scale?.reliable;
      return (
        <span>
          <span className="mono">{mm(m?.length_mm)}</span> long ·{" "}
          <span className="mono">{mm(m?.width_mm)}</span> wide · arch{" "}
          <span className="mono">{mm(m?.arch_height_mm)}</span>
          {reliable === false && (
            <span className="chip chip--warn">shape-only scale</span>
          )}
        </span>
      );
    }
    case "vision_read": {
      const v = data.vision;
      if (!v) return null;
      const mock = (v.source ?? "").toLowerCase().includes("mock");
      return (
        <span>
          {[v.arch_type && `${v.arch_type} arch`, v.pronation, v.weight_distribution]
            .filter(Boolean)
            .join(" · ")}
          {mock ? (
            <span className="chip chip--mock">mock</span>
          ) : (
            v.source && <span className="chip chip--live">claude</span>
          )}
        </span>
      );
    }
    case "review": {
      const approved = data.insole_spec?.approved ?? data.review?.approved;
      return (
        <span>
          Insole spec {approved ? "approved" : "recorded"} — see summary below.
        </span>
      );
    }
    default:
      return null;
  }
}

function StatusTag({ status }: { status: RowStatus }) {
  const label: Record<RowStatus, string> = {
    pending: "queued",
    active: "running",
    paused: "review",
    done: "done",
    failed: "failed",
    skipped: "skipped",
  };
  return <span className={`stag stag--${status}`}>{label[status]}</span>;
}

function Check() {
  return (
    <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">
      <path
        d="M3 8.5l3 3 7-8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
