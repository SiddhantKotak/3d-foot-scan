import { useEffect, useMemo, useRef, useState } from "react";
import type { FootSide, Posture } from "../types";

const MIN_RECOMMENDED = 8;

interface Props {
  onStart: (files: File[], footSide: FootSide, posture: Posture) => Promise<void>;
  busy: boolean;
  locked: boolean;
  scanId: string | null;
  onReset: () => void;
}

export default function UploadPanel({
  onStart,
  busy,
  locked,
  scanId,
  onReset,
}: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [footSide, setFootSide] = useState<FootSide>("left");
  const [posture, setPosture] = useState<Posture>("non_weight_bearing");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const previews = useMemo(
    () => files.map((f) => ({ name: f.name, url: URL.createObjectURL(f) })),
    [files],
  );
  useEffect(
    () => () => previews.forEach((p) => URL.revokeObjectURL(p.url)),
    [previews],
  );

  function addFiles(list: FileList | null) {
    if (!list) return;
    const imgs = Array.from(list).filter((f) => f.type.startsWith("image/"));
    setFiles((prev) => dedupe([...prev, ...imgs]));
  }

  async function start() {
    setError(null);
    try {
      await onStart(files, footSide, posture);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start scan");
    }
  }

  const disabled = locked || busy;

  return (
    <section className="panel upload">
      <h2 className="panel__title">
        <span className="panel__index">A</span> Capture
      </h2>

      {!locked ? (
        <>
          <div
            className={`drop ${dragOver ? "drop--over" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              addFiles(e.dataTransfer.files);
            }}
            onClick={() => inputRef.current?.click()}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
            }}
          >
            <input
              ref={inputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => addFiles(e.target.files)}
            />
            <span className="drop__icon" aria-hidden="true">
              +
            </span>
            <span className="drop__lead">Drop foot images</span>
            <span className="drop__hint">or click to browse · JPG / PNG</span>
          </div>

          {files.length > 0 && (
            <div className="thumbs">
              <div className="thumbs__grid">
                {previews.slice(0, 12).map((p) => (
                  <img key={p.name} src={p.url} alt={p.name} />
                ))}
                {previews.length > 12 && (
                  <span className="thumbs__more">
                    +{previews.length - 12}
                  </span>
                )}
              </div>
              <div className="thumbs__meta">
                <span className="mono">{files.length}</span> images
                <button
                  type="button"
                  className="linkbtn"
                  onClick={() => setFiles([])}
                >
                  clear
                </button>
              </div>
              {files.length < MIN_RECOMMENDED && (
                <p className="hint hint--warn">
                  Photogrammetry wants ≥ {MIN_RECOMMENDED} images from distinct
                  angles.
                </p>
              )}
            </div>
          )}

          <fieldset className="field">
            <legend>Foot side</legend>
            <div className="seg">
              {(["left", "right"] as FootSide[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`seg__opt ${footSide === s ? "is-on" : ""}`}
                  onClick={() => setFootSide(s)}
                >
                  {s}
                </button>
              ))}
            </div>
          </fieldset>

          <fieldset className="field">
            <legend>Posture</legend>
            <div className="seg">
              {(
                [
                  ["weight_bearing", "Weight-bearing"],
                  ["non_weight_bearing", "Non-weight-bearing"],
                ] as [Posture, string][]
              ).map(([val, label]) => (
                <button
                  key={val}
                  type="button"
                  className={`seg__opt ${posture === val ? "is-on" : ""}`}
                  onClick={() => setPosture(val)}
                >
                  {label}
                </button>
              ))}
            </div>
          </fieldset>

          <button
            type="button"
            className="btn btn--primary"
            disabled={disabled || files.length === 0}
            onClick={start}
          >
            {busy ? "Starting…" : "Start scan"}
          </button>

          {error && <p className="hint hint--error">{error}</p>}
        </>
      ) : (
        <div className="locked">
          <dl className="locked__meta">
            <div>
              <dt>Scan</dt>
              <dd className="mono">{scanId}</dd>
            </div>
            <div>
              <dt>Side</dt>
              <dd>{footSide}</dd>
            </div>
            <div>
              <dt>Posture</dt>
              <dd>{posture.replace(/_/g, "-")}</dd>
            </div>
            <div>
              <dt>Images</dt>
              <dd className="mono">{files.length}</dd>
            </div>
          </dl>
          <button
            type="button"
            className="btn btn--ghost"
            onClick={onReset}
            disabled={busy}
          >
            New scan
          </button>
        </div>
      )}
    </section>
  );
}

function dedupe(list: File[]): File[] {
  const seen = new Set<string>();
  return list.filter((f) => {
    const key = `${f.name}:${f.size}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
