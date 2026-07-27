// Typed fetch helpers + an SSE helper for the scan pipeline.
// Every path is same-origin "/api/..." — Vite proxies it to the FastAPI backend.

import type {
  CreateScanResponse,
  FootSide,
  Health,
  Posture,
  ReviewEdits,
  StreamEvent,
} from "./types";

const BASE = "/api";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* keep statusText */
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json() as Promise<T>;
}

export async function getHealth(): Promise<Health> {
  return asJson<Health>(await fetch(`${BASE}/health`));
}

export async function createScan(
  files: File[],
  footSide: FootSide,
  posture: Posture,
): Promise<CreateScanResponse> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f, f.name));
  form.append("foot_side", footSide);
  form.append("posture", posture);
  return asJson<CreateScanResponse>(
    await fetch(`${BASE}/scans`, { method: "POST", body: form }),
  );
}

export async function runScan(
  scanId: string,
  footSide: FootSide,
  posture: Posture,
): Promise<{ status: string; scan_id: string; n_images: number }> {
  const form = new FormData();
  form.append("foot_side", footSide);
  form.append("posture", posture);
  return asJson(
    await fetch(`${BASE}/scans/${scanId}/run`, { method: "POST", body: form }),
  );
}

export async function resumeReview(
  scanId: string,
  approved: boolean,
  edits: ReviewEdits,
): Promise<{ status: string }> {
  return asJson(
    await fetch(`${BASE}/scans/${scanId}/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approved, edits }),
    }),
  );
}

// Basename of a backend absolute path -> a render URL the browser can load.
export function renderUrl(scanId: string, absPath: string): string {
  const name = absPath.split(/[\\/]/).pop() ?? absPath;
  return `${BASE}/scans/${scanId}/renders/${name}`;
}

export interface StreamHandlers {
  onEvent: (ev: StreamEvent) => void;
  onClose?: () => void;
  onSocketError?: (err: Event) => void;
}

// Open the pipeline event stream. The connection stays open across the review
// interrupt — a resume pushes more events onto the same stream. We only tear it
// down on the backend's terminal `close` event.
export function openEventStream(
  scanId: string,
  handlers: StreamHandlers,
): EventSource {
  const es = new EventSource(`${BASE}/scans/${scanId}/events`);

  es.onmessage = (msg) => {
    if (!msg.data) return;
    try {
      handlers.onEvent(JSON.parse(msg.data) as StreamEvent);
    } catch {
      /* ignore keep-alive / unparseable frames */
    }
  };

  // Backend sends a named `close` event when the run is fully finished.
  es.addEventListener("close", () => {
    es.close();
    handlers.onClose?.();
  });

  es.onerror = (err) => {
    // EventSource auto-reconnects; surface the blip but let it retry unless the
    // stream was already closed by us.
    if (es.readyState === EventSource.CLOSED) {
      handlers.onClose?.();
    } else {
      handlers.onSocketError?.(err);
    }
  };

  return es;
}
