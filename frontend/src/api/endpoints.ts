/**
 * TRAIL API — 화면이 서버와 대화하는 유일한 통로.
 * Component는 fetch도 URL도 모른다. 여기 있는 함수만 호출한다.
 */
import { z } from "zod";
import { request, type RequestOptions } from "./client";
import * as c from "./contracts";

/**
 * import.meta.env는 빌드 시 리터럴로 치환된다 — VITE_API_MODE=live로 빌드하면 아래 분기가
 * 상수 false가 되어 Mock Transport와 outputs/mock_api JSON이 번들에서 통째로 빠진다.
 */
const MOCK_ENABLED = import.meta.env.VITE_API_MODE !== "live";

async function send<S extends z.ZodTypeAny>(
  schema: S,
  options: RequestOptions,
): Promise<z.output<S>> {
  if (MOCK_ENABLED) {
    const { mockRequest } = await import("./mock/transport");
    return mockRequest(schema, options);
  }
  return request(schema, options);
}

/* ── Context Catalog ────────────────────────────────────────────────── */

/** `ContextCatalogItem` (src/schemas/api.py). 15개가 서버 정본과 같은 순서로 온다. */
export const contextCatalogItemSchema = z.object({
  context_id: z.string(),
  label: z.string(),
  description: z.string(),
  example_activities: z.array(z.string()),
  interest_rating_prompt: z.string(),
  is_core: z.boolean(),
  /**
   * 실제 심층 질문 흐름을 지원하는 Context인지. 관심도 평가는 15개 전부 받지만,
   * 선호 Context로 고를 수 있는 건 이 값이 true인 것뿐이다(false면 서버가 422로 막는다).
   */
  assessment_supported: z.boolean(),
});
export type ContextCatalogItem = z.infer<typeof contextCatalogItemSchema>;

/**
 * 선택 개수 제한. 서버가 실제로 검증하는 값이라 화면에 상수로 박지 않는다 —
 * Full Mode로 바뀌면 이 응답만 바뀌고 화면 코드는 그대로 동작해야 한다.
 */
export const contextSelectionPolicySchema = z.object({
  preferred_context_min_count: z.number().int(),
  preferred_context_max_count: z.number().int(),
  contrast_context_count: z.number().int(),
  final_context_min_count: z.number().int(),
  final_context_max_count: z.number().int(),
  /** false면 Coverage 교체 기능이 꺼져 있다는 뜻 — 교체 제안 UI를 아예 숨긴다. */
  coverage_replacement_enabled: z.boolean(),
});
export type ContextSelectionPolicy = z.infer<typeof contextSelectionPolicySchema>;

export const contextCatalogSchema = z.object({
  contexts: z.array(contextCatalogItemSchema),
  selection_policy: contextSelectionPolicySchema,
});
export type ContextCatalog = z.infer<typeof contextCatalogSchema>;

/**
 * Context 목록·지원 여부·개수 정책은 전부 서버에서 온다. 프론트에 상수로 두지 않는다.
 * 세션과 무관하므로 앱 시작 시 한 번 불러 재사용해도 된다.
 */
export function fetchContextCatalog(signal?: AbortSignal): Promise<ContextCatalog> {
  return send(contextCatalogSchema, { method: "GET", path: "/contexts", signal });
}

/* ── Assessment ─────────────────────────────────────────────────────── */

/** user_id는 서버가 고정한다 — 화면이 보내지도, 사용자에게 묻지도 않는다. */
export function createSession(signal?: AbortSignal): Promise<c.CreateSessionResponse> {
  return send(c.createSessionResponseSchema, { method: "POST", path: "/assessment/session", signal });
}

/** ratings 값은 반드시 JSON 정수 1~5. 문자열/실수는 서버가 422로 거부한다. */
export function submitInterestRating(
  sessionId: string,
  ratings: Record<string, number>,
  signal?: AbortSignal,
) {
  return send(c.interestRatingResponseSchema, {
    method: "POST",
    path: "/assessment/interest-rating",
    json: { session_id: sessionId, ratings },
    signal,
  });
}

export function selectContexts(
  sessionId: string,
  selectedPreferredContextIds: string[],
  signal?: AbortSignal,
): Promise<c.ContextSelectResponse> {
  return send(c.contextSelectResponseSchema, {
    method: "POST",
    path: "/assessment/context-select",
    json: { session_id: sessionId, selected_preferred_context_ids: selectedPreferredContextIds },
    signal,
  });
}

export function confirmContexts(
  sessionId: string,
  finalContextIds: string[],
  signal?: AbortSignal,
): Promise<c.ContextConfirmResponse> {
  return send(c.contextConfirmResponseSchema, {
    method: "POST",
    path: "/assessment/context-confirm",
    json: { session_id: sessionId, final_context_ids: finalContextIds },
    signal,
  });
}

/** session_id를 Body가 아니라 Query Parameter로 보낸다 (README_B §3). */
export function fetchNextQuestion(
  sessionId: string,
  signal?: AbortSignal,
): Promise<c.NextQuestionResponse> {
  return send(c.nextQuestionResponseSchema, {
    method: "POST",
    path: "/assessment/next-question",
    query: { session_id: sessionId },
    signal,
  });
}

export function submitAnswer(
  sessionId: string,
  questionId: string,
  selectedOptionId: string,
  signal?: AbortSignal,
): Promise<c.AnswerResponse> {
  return send(c.answerResponseSchema, {
    method: "POST",
    path: "/assessment/answer",
    json: { session_id: sessionId, question_id: questionId, selected_option_id: selectedOptionId },
    signal,
  });
}

/* ── 결과 조회 ──────────────────────────────────────────────────────── */

/** 답변이 하나도 없으면 422 EVIDENCE_NOT_READY다 — 최소 1문항 답변 후에만 호출한다. */
export function fetchProfile(sessionId: string, signal?: AbortSignal): Promise<c.CareerProfile> {
  return send(c.careerProfileSchema, { method: "GET", path: `/profile/${sessionId}`, signal });
}

export function fetchMajors(sessionId: string, signal?: AbortSignal): Promise<c.MajorsResponse> {
  return send(c.majorsResponseSchema, { method: "GET", path: `/majors/${sessionId}`, signal });
}

/** 학과가 연결되지 않은 전공은 200 + 빈 목록이다. 오류로 처리하지 않는다. */
export function fetchDepartments(
  majorId: string,
  signal?: AbortSignal,
): Promise<c.DepartmentsResponse> {
  return send(c.departmentsResponseSchema, { method: "GET", path: `/departments/${majorId}`, signal });
}

/**
 * 확정 여부에 따라 PRE_SURVEY / POST_OFFERING이 자동으로 갈린다 — 응답의 `source`로 판단한다.
 * selected_major_id는 학생이 "이 전공으로 과목 추천받기"를 명시적으로 눌렀을 때만 넘긴다.
 */
export function fetchSubjects(
  sessionId: string,
  selectedMajorId: string,
  signal?: AbortSignal,
): Promise<c.CourseProfile> {
  return send(c.courseProfileSchema, {
    method: "GET",
    path: `/subjects/${sessionId}`,
    query: { selected_major_id: selectedMajorId },
    signal,
  });
}

/* ── 학교 개설과목 업로드·확정 ──────────────────────────────────────── */

/** PDF·XLSX만 허용(XLS 거부), 10MB 상한. 위반 시 422 VALIDATION_ERROR / PARSE_FAILED. */
export function uploadCourseDocument(
  sessionId: string,
  selectedMajorId: string,
  file: File,
  signal?: AbortSignal,
): Promise<c.CourseUploadResponse> {
  const formData = new FormData();
  formData.append("session_id", sessionId);
  formData.append("selected_major_id", selectedMajorId);
  formData.append("file", file);
  return send(c.courseUploadResponseSchema, {
    method: "POST",
    path: "/course/upload",
    formData,
    signal,
  });
}

/** confirmed_subject_ids는 matched_subject_id가 있는 후보에서만 모은다. 빈 배열도 유효하다. */
export function confirmCourseSelection(
  sessionId: string,
  confirmedSubjectIds: string[],
  signal?: AbortSignal,
): Promise<c.CourseConfirmResponse> {
  return send(c.courseConfirmResponseSchema, {
    method: "POST",
    path: "/course/confirm",
    json: { session_id: sessionId, confirmed_subject_ids: confirmedSubjectIds },
    signal,
  });
}

/* ── 관계 그래프 · Session 복원 ─────────────────────────────────────── */

/** 과목 미확정이면 과목 Node가 없는 부분 그래프가 정상이다(오류 아님). */
export function fetchSubgraph(sessionId: string, signal?: AbortSignal): Promise<c.SubgraphResponse> {
  return send(c.subgraphResponseSchema, { method: "GET", path: `/subgraph/${sessionId}`, signal });
}

export function restoreSession(
  sessionId: string,
  signal?: AbortSignal,
): Promise<c.SessionRestoreResponse> {
  return send(c.sessionRestoreResponseSchema, { method: "GET", path: `/session/${sessionId}`, signal });
}
