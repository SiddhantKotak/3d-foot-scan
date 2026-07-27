// Shared "measurement worksheet" primitives — the visual signature.
// DimLine renders a value as a technical-drawing dimension line (red extension
// ticks flanking a Space Mono readout). CalloutTag is a drafting-style
// reliability annotation with a leader tick.

export function DimLine({
  label,
  value,
  unit = "mm",
  size = "md",
}: {
  label: string;
  value: number | null | undefined;
  unit?: string;
  size?: "md" | "lg";
}) {
  const text = value == null ? "—" : Number(value).toFixed(1);
  return (
    <div className={`dim dim--${size}`}>
      <span className="dim__label">{label}</span>
      <div className="dim__line">
        <span className="dim__cap" aria-hidden="true" />
        <span className="dim__rule" aria-hidden="true" />
        <span className="dim__val mono">
          {text}
          {value != null && <span className="dim__unit">{unit}</span>}
        </span>
        <span className="dim__rule" aria-hidden="true" />
        <span className="dim__cap" aria-hidden="true" />
      </div>
    </div>
  );
}

export function CalloutTag({
  reliable,
  reason,
  okLabel = "reliable",
  flagLabel = "flagged",
}: {
  reliable: boolean;
  reason?: string;
  okLabel?: string;
  flagLabel?: string;
}) {
  if (reliable) {
    return (
      <span className="callout callout--ok" title="Reliable">
        <span className="callout__leader" aria-hidden="true" />
        <Check />
        {okLabel}
      </span>
    );
  }
  return (
    <span className="callout callout--flag" title={reason}>
      <span className="callout__leader" aria-hidden="true" />
      <span className="callout__mark" aria-hidden="true">
        !
      </span>
      {flagLabel}
    </span>
  );
}

function Check() {
  return (
    <svg viewBox="0 0 16 16" width="11" height="11" aria-hidden="true">
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
