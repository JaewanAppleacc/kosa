/**
 * 오류 표현 — 화면은 이 세 종류만 구분하면 된다.
 *
 * 1. ApiError        서버가 계약대로 내려준 오류 (error_code로 분기)
 * 2. NetworkError    서버에 닿지 못함
 * 3. ContractError   응답이 왔지만 Schema와 다름 (계약 위반 — 조용히 넘기지 않는다)
 */
import type { ZodError } from "zod";
import { apiErrorEnvelopeSchema, type ApiErrorCode } from "./contracts";

export class ApiError extends Error {
  readonly kind = "api" as const;
  constructor(
    readonly code: ApiErrorCode,
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  readonly kind = "network" as const;
  constructor(cause: unknown) {
    super("서버에 연결하지 못했습니다.");
    this.name = "NetworkError";
    this.cause = cause;
  }
}

export class ContractError extends Error {
  readonly kind = "contract" as const;
  constructor(
    readonly endpoint: string,
    readonly zodError: ZodError,
  ) {
    super(`응답 형식이 API 계약과 다릅니다: ${endpoint}`);
    this.name = "ContractError";
  }
}

export type TrailError = ApiError | NetworkError | ContractError;

export function isApiError(error: unknown, code?: ApiErrorCode): error is ApiError {
  if (!(error instanceof ApiError)) return false;
  return code === undefined || error.code === code;
}

/**
 * 오류 본문 파싱. 계약을 벗어난 응답(프록시 502 HTML 등)도 화면이 멈추지 않도록
 * INTERNAL_ERROR로 정규화한다.
 */
export function parseErrorBody(body: unknown, status: number): ApiError {
  const parsed = apiErrorEnvelopeSchema.safeParse(body);
  if (parsed.success) {
    return new ApiError(parsed.data.detail.error_code, parsed.data.detail.message, status);
  }
  return new ApiError("INTERNAL_ERROR", `예상하지 못한 오류가 발생했습니다. (HTTP ${status})`, status);
}

/** 사용자에게 보여줄 문구. 내부 코드·Stack은 노출하지 않는다. */
export function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof NetworkError) return "서버에 연결하지 못했습니다. 잠시 후 다시 시도해주세요.";
  if (error instanceof ContractError) return "결과를 표시하는 중 문제가 생겼습니다. 잠시 후 다시 시도해주세요.";
  return "알 수 없는 문제가 발생했습니다.";
}
