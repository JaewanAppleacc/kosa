/**
 * API 접속 설정 — 이 파일이 유일한 진입점이다.
 * Component나 api 모듈이 주소·모드를 직접 읽지 않는다 (README_B §1).
 */

export type ApiMode = "mock" | "live";

function readMode(): ApiMode {
  const raw = import.meta.env.VITE_API_MODE;
  if (raw === "live") return "live";
  if (raw === "mock") return "mock";
  // 값이 없거나 오타면 조용히 live로 새지 않도록 mock으로 떨어뜨린다.
  return "mock";
}

function readLatency(): number {
  const raw = Number(import.meta.env.VITE_MOCK_LATENCY_MS);
  return Number.isFinite(raw) && raw >= 0 ? raw : 0;
}

export const env = {
  apiMode: readMode(),
  /** live 모드 fetch prefix. Vite dev proxy가 /api → 127.0.0.1:8000으로 넘긴다. */
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  /** mock 모드에서 Loading UI를 확인하기 위한 인위적 지연. */
  mockLatencyMs: readLatency(),
} as const;

export const isMockMode = () => env.apiMode === "mock";
