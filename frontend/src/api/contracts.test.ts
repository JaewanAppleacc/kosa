/**
 * 계약 회귀 테스트 — A가 Schema를 바꾸고 outputs/mock_api/*.json을 재생성하면
 * 화면을 열어보기 전에 여기서 먼저 깨진다.
 */
import { describe, expect, it } from "vitest";
import type { ZodTypeAny } from "zod";
import * as c from "./contracts";
import { contextCatalogSchema } from "./endpoints";

import sessionCreate from "@mock/session_create_normal.json";
import interestRating from "@mock/interest_rating_normal.json";
import contextSelect from "@mock/context_select_normal.json";
import contextConfirm from "@mock/context_confirm_normal.json";
import nextQuestionNormal from "@mock/next_question_normal.json";
import nextQuestionCacheUsed from "@mock/next_question_cache_used__hand_crafted.json";
import nextQuestionBackupUsed from "@mock/next_question_backup_used__hand_crafted.json";
import nextQuestionRegenerating from "@mock/next_question_regenerating__hand_crafted.json";
import nextQuestionEarlyTerminated from "@mock/next_question_context_early_terminated__hand_crafted.json";
import answer from "@mock/answer_normal.json";
import profileNormal from "@mock/profile_normal.json";
import profilePartial from "@mock/profile_partial__hand_crafted.json";
import majors from "@mock/majors_normal.json";
import departmentsNormal from "@mock/departments_normal.json";
import departmentsEmpty from "@mock/departments_empty.json";
import subjects from "@mock/subjects_normal.json";
import courseUpload from "@mock/course_upload_normal.json";
import courseConfirm from "@mock/course_confirm_normal.json";
import subgraph from "@mock/subgraph_normal.json";
import sessionRestore from "@mock/session_restore_normal.json";
import errorEvidenceNotReady from "@mock/error_evidence_not_ready__hand_crafted.json";
import errorLlmUnavailable from "@mock/error_llm_unavailable__hand_crafted.json";
import errorValidation from "@mock/error_validation__hand_crafted.json";
import profileErrorSessionNotFound from "@mock/profile_error_session_not_found.json";
import contexts from "@mock/contexts_normal.json";

const cases: Array<[string, ZodTypeAny, unknown]> = [
  ["session_create_normal", c.createSessionResponseSchema, sessionCreate],
  ["interest_rating_normal", c.interestRatingResponseSchema, interestRating],
  ["context_select_normal", c.contextSelectResponseSchema, contextSelect],
  ["context_confirm_normal", c.contextConfirmResponseSchema, contextConfirm],
  ["next_question_normal", c.nextQuestionResponseSchema, nextQuestionNormal],
  ["next_question_cache_used", c.nextQuestionResponseSchema, nextQuestionCacheUsed],
  ["next_question_backup_used", c.nextQuestionResponseSchema, nextQuestionBackupUsed],
  ["next_question_regenerating", c.nextQuestionResponseSchema, nextQuestionRegenerating],
  ["next_question_early_terminated", c.nextQuestionResponseSchema, nextQuestionEarlyTerminated],
  ["answer_normal", c.answerResponseSchema, answer],
  ["profile_normal", c.careerProfileSchema, profileNormal],
  ["profile_partial", c.careerProfileSchema, profilePartial],
  ["majors_normal", c.majorsResponseSchema, majors],
  ["departments_normal", c.departmentsResponseSchema, departmentsNormal],
  ["departments_empty", c.departmentsResponseSchema, departmentsEmpty],
  ["subjects_normal", c.courseProfileSchema, subjects],
  ["course_upload_normal", c.courseUploadResponseSchema, courseUpload],
  ["course_confirm_normal", c.courseConfirmResponseSchema, courseConfirm],
  ["subgraph_normal", c.subgraphResponseSchema, subgraph],
  ["session_restore_normal", c.sessionRestoreResponseSchema, sessionRestore],
  ["contexts_normal", contextCatalogSchema, contexts],
];

describe("outputs/mock_api가 프론트 Schema와 일치한다", () => {
  it.each(cases)("%s", (_name, schema, payload) => {
    const result = schema.safeParse(payload);
    expect(result.success ? null : result.error.issues).toBeNull();
  });
});

describe("오류 응답", () => {
  it("HTTPException 형태({detail:{...}})를 파싱한다", () => {
    const parsed = c.apiErrorEnvelopeSchema.safeParse(profileErrorSessionNotFound);
    expect(parsed.success).toBe(true);
  });

  it.each([
    ["EVIDENCE_NOT_READY", errorEvidenceNotReady],
    ["LLM_UNAVAILABLE", errorLlmUnavailable],
    ["VALIDATION_ERROR", errorValidation],
  ])("%s 본문을 파싱한다", (code, payload) => {
    const parsed = c.apiErrorBodySchema.safeParse(payload);
    expect(parsed.success).toBe(true);
    if (parsed.success) expect(parsed.data.error_code).toBe(code);
  });
});

describe("화면에 내부 숫자가 새어나갈 수 있는 지점", () => {
  it("MajorRelevance에는 점수 필드 자체가 없다", () => {
    const major = c.majorRelevanceSchema.parse(majors.relevant_majors[0]);
    expect(Object.keys(major).sort()).toEqual([
      "description",
      "evidence_sufficiency",
      "label",
      "major_id",
      "relevance_label",
      "repeated_context_count",
    ]);
  });
});

describe("MajorRelevance.description 계약(2026-08-24 A3 지시서)", () => {
  it("Mock 정본의 모든 전공 항목에 description이 채워져 있다", () => {
    const all = [...majors.relevant_majors, ...majors.explore_together_majors];
    expect(all.length).toBeGreaterThan(0);
    for (const item of all) {
      const parsed = c.majorRelevanceSchema.parse(item);
      expect(parsed.description.trim().length).toBeGreaterThan(0);
    }
  });

  it("description이 누락된 응답은 계약 오류로 탐지한다(임의 문구로 대체하지 않는다)", () => {
    const { description: _omitted, ...withoutDescription } = majors.relevant_majors[0] as Record<
      string,
      unknown
    >;
    const result = c.majorRelevanceSchema.safeParse(withoutDescription);
    expect(result.success).toBe(false);
    if (!result.success) {
      expect(result.error.issues.some((issue) => issue.path[0] === "description")).toBe(true);
    }
  });
});
