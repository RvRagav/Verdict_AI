/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Base URL of the VerdictAI backend API (without trailing slash).
   * In dev, leave empty — vite proxy forwards /api to localhost:8000.
   * In production (Vercel), set to the full Railway URL,
   * e.g. https://verdictai-backend.up.railway.app
   */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
