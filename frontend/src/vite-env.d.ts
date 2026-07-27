/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base URL the Case Study renders/mesh load from. "" for a static deploy. */
  readonly VITE_RENDER_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
