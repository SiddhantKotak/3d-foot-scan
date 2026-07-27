// Shared shapes mirroring the FastAPI backend contract.

export type FootSide = "left" | "right";
export type Posture = "weight_bearing" | "non_weight_bearing";

export type StageName =
  | "quality_gate"
  | "submit_reconstruction"
  | "await_reconstruction"
  | "measure"
  | "vision_read"
  | "review";

export const STAGES: StageName[] = [
  "quality_gate",
  "submit_reconstruction",
  "await_reconstruction",
  "measure",
  "vision_read",
  "review",
];

export const STAGE_LABEL: Record<StageName, string> = {
  quality_gate: "Quality gate",
  submit_reconstruction: "Submit reconstruction",
  await_reconstruction: "Reconstruct 3D mesh",
  measure: "Measure geometry",
  vision_read: "Vision biomechanics",
  review: "Podiatrist review",
};

export interface Health {
  ok: boolean;
  kiri_live: boolean;
  claude_live: boolean;
}

export interface CreateScanResponse {
  scan_id: string;
  n_files: number;
  foot_side: FootSide;
  posture: Posture;
}

export interface ImageVerdict {
  path: string;
  passed: boolean;
  blur_var: number;
  skin_frac: number;
  dark_frac?: number;
  bright_frac?: number;
  reasons: string[];
}

export interface Quality {
  ok: boolean;
  n_accepted: number;
  n_input: number;
  n_rejected?: number;
  distinct_viewpoints: number;
  batch_reasons?: string[];
  images: ImageVerdict[];
}

export interface Measurements {
  length_mm: number | null;
  width_mm: number | null;
  arch_height_mm: number | null;
  arch_peak_fraction?: number | null;
  arch_engine?: string;
  midfoot?: { width_mm: number | null; height_mm: number | null };
}

export interface Scale {
  method?: string;
  reliable: boolean;
  notes?: string[];
}

export interface Validation {
  gt_length_mm?: number | null;
  gt_width_mm?: number | null;
  meas_length_mm?: number | null;
  meas_width_mm?: number | null;
  length_dev_mm?: number | null;
  width_dev_mm?: number | null;
  tolerance_mm?: number | null;
  within_tolerance?: boolean | null;
  scale_reliable?: boolean;
  notes?: string[];
}

export interface Geometry {
  measurements: Measurements;
  scale: Scale;
  validation: Validation;
  repair?: { method_used?: string; output_watertight?: boolean };
  warnings?: string[];
  ok?: boolean;
}

export interface Vision {
  arch_type?: string;
  pronation?: string;
  weight_distribution?: string;
  pressure_zones?: string[];
  confidence?: number | string;
  notes?: string;
  source?: string;
}

export interface InsoleSpec {
  foot_side?: FootSide;
  approved?: boolean;
  length_mm?: number | null;
  width_mm?: number | null;
  arch_height_mm?: number | null;
  arch_type?: string;
  arch_support?: string;
  note?: string;
}

export type RenderPaths = Record<string, string>;

export interface ScanState {
  scan_id?: string;
  quality?: Quality;
  serialize?: string;
  model_url?: string;
  geometry?: Geometry;
  render_paths?: RenderPaths;
  vision?: Vision;
  review?: { approved?: boolean; edits?: Record<string, unknown> };
  insole_spec?: InsoleSpec;
  status?: string;
  errors?: string[];
}

export interface ReviewInterrupt {
  kind: string;
  measurements?: Measurements;
  validation?: Validation;
  warnings?: string[];
  vision?: Vision;
  render_paths?: RenderPaths;
}

// Server-sent event variants.
export type StreamEvent =
  | { event: "node"; node: StageName; data: Partial<ScanState> }
  | { event: "interrupt"; payload: ReviewInterrupt & Record<string, unknown> }
  | { event: "done"; state: ScanState }
  | { event: "error"; message: string };

export interface ReviewEdits {
  length_mm?: number;
  width_mm?: number;
  arch_height_mm?: number;
}

// ---- Case study (pre-baked real results, imported from JSON) ----
export interface CaseFoot {
  side: FootSide;
  scan_id: string;
  measurements: {
    length_mm: number;
    width_mm: number;
    width_reliable: boolean;
    arch_height_mm: number;
    arch_reliable: boolean;
    arch_engine: string;
  };
  scale: { method: string; reliable: boolean };
  validation: {
    gt_length_mm: number;
    gt_width_mm: number;
    length_dev_mm: number;
    width_dev_mm: number;
    within_tolerance: boolean;
    scale_reliable: boolean;
  };
  repair: { method_used: string; output_watertight: boolean };
  vision: Vision;
  warnings: string[];
  renders: Record<string, string>;
}

export interface CaseStudyData {
  patient: string;
  capture: string;
  ground_truth_source: string;
  data_issues: string[];
  solved: string[];
  feet: CaseFoot[];
}
