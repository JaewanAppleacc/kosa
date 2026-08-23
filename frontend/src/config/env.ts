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

/**
 * Mock 응답은 즉시 돌아와서 Loading UI가 눈에 보이지 않는다. 값을 지정하지 않은
 * 환경(=.env.local이 없는 새 clone)에서도 실제와 비슷한 전환을 보도록 기본 지연을 준다.
 * 0을 명시하면 지연 없이 동작한다(테스트가 이 경로를 쓴다).
 */
const DEFAULT_MOCK_LATENCY_MS = 400;

function readLatency(): number {
  const raw = import.meta.env.VITE_MOCK_LATENCY_MS;
  if (raw === undefined || raw.trim() === "") return DEFAULT_MOCK_LATENCY_MS;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : DEFAULT_MOCK_LATENCY_MS;
}

export const env = {
  apiMode: readMode(),
  /** live 모드 fetch prefix. Vite dev proxy가 /api → 127.0.0.1:8000으로 넘긴다. */
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL ?? "/api",
  /** mock 모드에서 Loading UI를 확인하기 위한 인위적 지연. */
  mockLatencyMs: readLatency(),
} as const;

export const isMockMode = () => env.apiMode === "mock";
