/**
 * Mock Transport — `request()`와 같은 시그니처로 정적 응답을 돌려준다.
 * VITE_API_MODE=mock일 때만 쓰이며, live 모드에서는 이 파일이 실행되지 않는다.
 *
 * ⚠️ 여기 있는 건 개발용 Fixture 재생 로직이지 업무 규칙이 아니다.
 *    Trait 판정·전공 Matching·과목 추천은 절대 이 파일에서 흉내내지 않는다 —
 *    서버가 계산한 결과 JSON을 그대로 돌려줄 뿐이다 (CLAUDE.md 아키텍처 불변식).
 *
 * 응답 원본은 복사본이 아니라 A가 생성하는 정본 outputs/mock_api/*.json이다.
 */
import type { ZodTypeAny, output } from "zod";
import { env } from "@/config/env";
import { ContractError, parseErrorBody } from "../errors";
import type { RequestOptions } from "../client";

import sessionCreate from "@mock/session_create_normal.json";
import interestRating from "@mock/interest_rating_normal.json";
import contextSelect from "@mock/context_select_normal.json";
import contextConfirm from "@mock/context_confirm_normal.json";
import nextQuestion from "@mock/next_question_normal.json";
import nextQuestionCacheUsed from "@mock/next_question_cache_used__hand_crafted.json";
import nextQuestionBackupUsed from "@mock/next_question_backup_used__hand_crafted.json";
import answer from "@mock/answer_normal.json";
import profile from "@mock/profile_normal.json";
import majors from "@mock/majors_normal.json";
import departments from "@mock/departments_normal.json";
import departmentsEmpty from "@mock/departments_empty.json";
import subjects from "@mock/subjects_normal.json";
import courseUpload from "@mock/course_upload_normal.json";
import courseConfirm from "@mock/course_confirm_normal.json";
import subgraph from "@mock/subgraph_normal.json";
import sessionRestore from "@mock/session_restore_normal.json";
import contexts from "@mock/contexts_normal.json";

/** 시나리오 진행 상태. 새로고침하면 초기화된다(실제 서버도 In-Memory라 성격이 같다). */
interface MockSessionState {
  answeredInCurrentContext: number;
  contextIndex: number;
  hasConfirmedCourses: boolean;
}

const MOCK_CONTEXTS = ["game", "media", "school_life"] as const;
/** 실제 서버는 Adaptive하게 5~7문항이지만, Mock은 화면 확인용으로 5문항 고정이다. */
const MOCK_QUESTIONS_PER_CONTEXT = 5;

let state: MockSessionState = {
  answeredInCurrentContext: 0,
  contextIndex: 0,
  hasConfirmedCourses: false,
};

export function resetMockSession(): void {
  state = { answeredInCurrentContext: 0, contextIndex: 0, hasConfirmedCourses: false };
}

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

/** status 변형(CACHE_USED / BACKUP_USED)을 순환시켜 Fallback UI를 실제로 볼 수 있게 한다. */
function questionPayload(): unknown {
  const asked = state.answeredInCurrentContext;
  const contextId = MOCK_CONTEXTS[state.contextIndex] ?? MOCK_CONTEXTS[0];

  let base: Record<string, unknown>;
  if (asked === 2) base = { ...nextQuestionCacheUsed };
  else if (asked === 3) base = { ...nextQuestionBackupUsed };
  else base = { ...nextQuestion };

  const question = base.question as Record<string, unknown> | null;
  return {
    ...base,
    question:
      question === null
        ? null
        : // 같은 Fixture를 반복해도 question_id가 겹치지 않게 한다 — 중복 제출 방지 로직이
          // Mock에서도 실제처럼 동작해야 하기 때문이다.
          { ...question, question_id: `${String(question.question_id)}_${contextId}_${asked}`, context: contextId },
    current_context_id: contextId,
    questions_asked_in_current_context: asked,
    assessment_complete: false,
  };
}

function answerPayload(): unknown {
  state.answeredInCurrentContext += 1;
  if (state.answeredInCurrentContext < MOCK_QUESTIONS_PER_CONTEXT) {
    return { ...answer, next_action: "NEXT_QUESTION" };
  }
  state.answeredInCurrentContext = 0;
  state.contextIndex += 1;
  const hasNextContext = state.contextIndex < MOCK_CONTEXTS.length;
  return { ...answer, next_action: hasNextContext ? "CONTEXT_COMPLETE" : "ASSESSMENT_COMPLETE" };
}

interface MockOutcome {
  body: unknown;
  status?: number;
}

function resolve(options: RequestOptions): MockOutcome {
  const { method, path } = options;

  // path parameter가 섞여 있어 정확 일치가 안 되므로 접두어로 매칭한다.
  if (method === "POST" && path === "/assessment/session") return { body: sessionCreate };
  if (method === "POST" && path === "/assessment/interest-rating") return { body: interestRating };
  if (method === "POST" && path === "/assessment/context-select") return { body: contextSelect };
  if (method === "POST" && path === "/assessment/context-confirm") return { body: contextConfirm };
  if (method === "POST" && path === "/assessment/next-question") return { body: questionPayload() };
  if (method === "POST" && path === "/assessment/answer") return { body: answerPayload() };
  if (method === "GET" && path === "/contexts") return { body: contexts };
  if (method === "GET" && path.startsWith("/profile/")) return { body: profile };
  if (method === "GET" && path.startsWith("/majors/")) return { body: majors };
  if (method === "GET" && path.startsWith("/departments/")) {
    const majorId = path.slice("/departments/".length);
    // 학과가 연결되지 않은 전공은 200 + 빈 목록이다(오류가 아니다).
    return { body: majorId === departments.major_id ? departments : { ...departmentsEmpty, major_id: majorId } };
  }
  // selected_major_id는 Mock에서 분기에 쓰지 않는다 — 확정 여부만으로 PRE/POST를 가른다.
  if (method === "GET" && path.startsWith("/subjects/")) {
    return { body: state.hasConfirmedCourses ? courseConfirm.course_profile : subjects };
  }
  if (method === "POST" && path === "/course/upload") return { body: courseUpload };
  if (method === "POST" && path === "/course/confirm") {
    state.hasConfirmedCourses = true;
    return { body: courseConfirm };
  }
  if (method === "GET" && path.startsWith("/subgraph/")) return { body: subgraph };
  if (method === "GET" && path.startsWith("/session/")) return { body: sessionRestore };

  throw new Error(`Mock 응답이 정의되지 않은 경로입니다: ${method} ${path}`);
}

export async function mockRequest<S extends ZodTypeAny>(
  schema: S,
  options: RequestOptions,
): Promise<output<S>> {
  if (env.mockLatencyMs > 0) await delay(env.mockLatencyMs);

  const outcome = resolve(options);
  if (outcome.status !== undefined && outcome.status >= 400) {
    throw parseErrorBody(outcome.body, outcome.status);
  }

  const parsed = schema.safeParse(outcome.body);
  if (!parsed.success) {
    // Mock이 Schema를 못 통과하면 A가 Schema를 바꿨는데 Mock JSON이 오래된 것이다.
    throw new ContractError(`[mock] ${options.method} ${options.path}`, parsed.error);
  }
  return parsed.data;
}
