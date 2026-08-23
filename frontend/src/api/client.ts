/**
 * HTTP 클라이언트 — 주소를 아는 유일한 곳이다.
 * 모든 응답은 zod Schema를 통과해야 화면으로 넘어간다.
 */
import type { ZodTypeAny, output } from "zod";
import { env } from "@/config/env";
import { ContractError, NetworkError, parseErrorBody } from "./errors";

type Query = Record<string, string | undefined>;

function buildUrl(path: string, query?: Query): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined) search.set(key, value);
  }
  const qs = search.toString();
  return `${env.apiBaseUrl}${path}${qs ? `?${qs}` : ""}`;
}

async function readBody(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export interface RequestOptions {
  method: "GET" | "POST";
  path: string;
  query?: Query;
  json?: unknown;
  formData?: FormData;
  signal?: AbortSignal;
}

/**
 * 응답을 Schema로 검증해서 돌려준다. 실패하면 ApiError/NetworkError/ContractError를 던진다.
 *
 * Schema의 **출력** 타입으로 좁힌다 — `.default()`가 있는 필드는 입력에선 optional이지만
 * 검증 후에는 항상 채워져 있다. 화면은 출력 타입만 보면 된다.
 */
export async function request<S extends ZodTypeAny>(
  schema: S,
  options: RequestOptions,
): Promise<output<S>> {
  const { method, path, query, json, formData, signal } = options;
  const url = buildUrl(path, query);

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      // FormData는 boundary를 브라우저가 정해야 하므로 Content-Type을 지정하지 않는다.
      headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: json !== undefined ? JSON.stringify(json) : formData,
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new NetworkError(cause);
  }

  const body = await readBody(response);
  if (!response.ok) throw parseErrorBody(body, response.status);

  const parsed = schema.safeParse(body);
  if (!parsed.success) throw new ContractError(`${method} ${path}`, parsed.error);
  return parsed.data;
}
