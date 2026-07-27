import { useEffect, useRef, useState } from "react";
import {
  createScan,
  getHealth,
  openEventStream,
  resumeReview,
  runScan,
} from "../api";
import type {
  FootSide,
  Health,
  Posture,
  ReviewEdits,
  ReviewInterrupt,
  ScanState,
  StageName,
  StreamEvent,
} from "../types";
import { STAGES, STAGE_LABEL } from "../types";
import UploadPanel from "./UploadPanel";
import ChatLog from "./ChatLog";
import ReviewPanel from "./ReviewPanel";
import ResultsPanel from "./ResultsPanel";

type Phase = "setup" | "running" | "review" | "resuming" | "done" | "error";
type StageData = Partial<Record<StageName, Partial<ScanState>>>;

function nextStage(stage: StageName): StageName | null {
  const i = STAGES.indexOf(stage);
  return i >= 0 && i < STAGES.length - 1 ? STAGES[i + 1] : null;
}

// The interactive pipeline runner. Kept intact but not mounted in the current
// case-study-only shell; re-add <LiveScan/> to a view to bring it back.
export default function LiveScan() {
  const [health, setHealth] = useState<Health | null>(null);
  const [phase, setPhase] = useState<Phase>("setup");
  const [scanId, setScanId] = useState<string | null>(null);

  const [stageData, setStageData] = useState<StageData>({});
  const [completed, setCompleted] = useState<StageName[]>([]);
  const [activeStage, setActiveStage] = useState<StageName | null>(null);

  const [review, setReview] = useState<ReviewInterrupt | null>(null);
  const [finalState, setFinalState] = useState<ScanState | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
    return () => esRef.current?.close();
  }, []);

  function handleEvent(ev: StreamEvent) {
    if (ev.event === "node") {
      const node = ev.node;
      setStageData((prev) => ({
        ...prev,
        [node]: { ...(prev[node] ?? {}), ...ev.data },
      }));
      setCompleted((prev) => (prev.includes(node) ? prev : [...prev, node]));

      const qualityFailed =
        node === "quality_gate" && ev.data.quality?.ok === false;
      const stageFailed =
        typeof ev.data.status === "string" &&
        /failed|timeout|rejected/.test(ev.data.status);

      if (node === "review") {
        setActiveStage(null);
      } else if (qualityFailed || stageFailed) {
        setActiveStage(null);
      } else {
        setActiveStage(nextStage(node));
      }
    } else if (ev.event === "interrupt") {
      if (ev.payload?.kind === "podiatrist_review") {
        setReview(ev.payload);
        setActiveStage("review");
        setPhase("review");
      }
    } else if (ev.event === "done") {
      setFinalState(ev.state);
      setActiveStage(null);
      setPhase("done");
    } else if (ev.event === "error") {
      setErrorMsg(ev.message);
      setActiveStage(null);
      setPhase("error");
    }
  }

  async function handleStart(
    files: File[],
    footSide: FootSide,
    posture: Posture,
  ) {
    esRef.current?.close();
    setStageData({});
    setCompleted([]);
    setReview(null);
    setFinalState(null);
    setErrorMsg(null);

    const created = await createScan(files, footSide, posture);
    setScanId(created.scan_id);
    setActiveStage("quality_gate");
    setPhase("running");

    await runScan(created.scan_id, footSide, posture);

    esRef.current = openEventStream(created.scan_id, {
      onEvent: handleEvent,
    });
  }

  async function handleApprove(approved: boolean, edits: ReviewEdits) {
    if (!scanId) return;
    setPhase("resuming");
    setActiveStage("review");
    setReview(null);
    await resumeReview(scanId, approved, edits);
  }

  function handleReset() {
    esRef.current?.close();
    setPhase("setup");
    setScanId(null);
    setStageData({});
    setCompleted([]);
    setActiveStage(null);
    setReview(null);
    setFinalState(null);
    setErrorMsg(null);
  }

  const sessionStarted = phase !== "setup" || scanId !== null;

  return (
    <div className="app">
      <aside className="rail">
        <HealthBar health={health} />
        <UploadPanel
          onStart={handleStart}
          busy={phase === "running" || phase === "resuming"}
          locked={sessionStarted}
          scanId={scanId}
          onReset={handleReset}
        />
        <footer className="rail__foot">
          <span>Proof of concept</span>
          <span className="rail__foot-note">
            KIRI photogrammetry · Claude vision · LangGraph
          </span>
        </footer>
      </aside>

      <main className="session">
        {!sessionStarted ? (
          <EmptyState />
        ) : (
          <div className="session__scroll">
            <ChatLog
              scanId={scanId}
              stageData={stageData}
              completed={completed}
              activeStage={activeStage}
              phase={phase}
              health={health}
              errorMsg={errorMsg}
            />

            {review && scanId && (
              <ReviewPanel
                scanId={scanId}
                interrupt={review}
                onDecision={handleApprove}
              />
            )}

            {finalState && scanId && (
              <ResultsPanel
                scanId={scanId}
                state={finalState}
                onNewScan={handleReset}
              />
            )}
          </div>
        )}
      </main>
    </div>
  );
}

function HealthBar({ health }: { health: Health | null }) {
  return (
    <div className="health" role="status" aria-live="polite">
      <span className="health__label">Backend</span>
      <div className="health__pills">
        <ServicePill name="KIRI" live={health?.kiri_live} unknown={!health} />
        <ServicePill name="Claude" live={health?.claude_live} unknown={!health} />
      </div>
    </div>
  );
}

function ServicePill({
  name,
  live,
  unknown,
}: {
  name: string;
  live?: boolean;
  unknown: boolean;
}) {
  const state = unknown ? "unknown" : live ? "live" : "mock";
  return (
    <span className={`pill pill--${state}`} title={`${name}: ${state}`}>
      <span className="pill__dot" />
      <span className="pill__name">{name}</span>
      <span className="pill__state">{state}</span>
    </span>
  );
}

function EmptyState() {
  return (
    <div className="empty">
      <div className="empty__ticks" aria-hidden="true" />
      <h1 className="empty__title">Capture a foot. Read the biomechanics.</h1>
      <p className="empty__body">
        Upload a batch of foot photos, pick the side and posture, and start the
        scan. Each pipeline stage streams in as it runs: quality gate,
        reconstruction, measurement, vision read, then pauses for your review
        before the insole spec is written.
      </p>
      <ol className="empty__flow">
        {STAGES.map((s, i) => (
          <li key={s}>
            <span className="empty__num">{String(i + 1).padStart(2, "0")}</span>
            {STAGE_LABEL[s]}
          </li>
        ))}
      </ol>
    </div>
  );
}
