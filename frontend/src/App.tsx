import CaseStudy from "./components/CaseStudy";

// Case-study-only shell: a slim masthead bar over the pipeline case study.
// The interactive runner still lives in components/LiveScan.tsx if it's needed.
export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar__inner">
          <Brand />
          <span className="topbar__meta mono">
            KIRI · Claude · LangGraph
          </span>
        </div>
      </header>
      <div className="viewpane">
        <CaseStudy />
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="brand">
      <span className="brand__mark" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="26" height="26">
          {/* stylised plantar footprint */}
          <path
            d="M14.5 3.2c1.9 0 3 1.7 3 3.9 0 2.4-1.1 4.3-1.1 6.2 0 1.4.7 2.2.7 3.6 0 2.1-1.4 3.5-3.2 3.5-1.9 0-3-1.3-3-3.3 0-2.2.9-3.4.9-5 0-.9-.5-1.4-.5-2.4 0-1 .3-1.7.3-2.6 0-2.2 1-3.9 2.6-3.9Z"
            fill="currentColor"
          />
          <circle cx="7.4" cy="7.2" r="1.5" fill="currentColor" />
          <circle cx="5.4" cy="10.6" r="1.2" fill="currentColor" />
          <circle cx="5.1" cy="14" r="1.05" fill="currentColor" />
        </svg>
      </span>
      <span className="brand__text">
        <span className="brand__name">Pes Console</span>
        <span className="brand__sub">foot-scan worksheet</span>
      </span>
    </div>
  );
}
