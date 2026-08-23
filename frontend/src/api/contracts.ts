/**
 * API 응답 Schema — src/schemas/*.py의 Pydantic 정의를 그대로 옮긴 것.
 *
 * 원칙:
 * - 서버가 강제하는 "업무 규칙"(highlights 5~8개 등)은 여기서 다시 검사하지 않는다.
 *   구조(필드 이름·타입·enum 값)만 검증한다. 규칙 위반은 서버 책임이고, 화면이
 *   중복 검사하면 정상 응답을 오류로 만들 수 있다.
 * - 내부 점수 필드는 애초에 계약에 없다. 여기 없는 필드를 임의로 추가하지 않는다.
 */
import { z } from "zod";

/* ── 공통 ───────────────────────────────────────────────────────────── */

export const apiErrorCodeSchema = z.enum([
  "VALIDATION_ERROR",
  "SESSION_NOT_FOUND",
  "LLM_UNAVAILABLE",
  "LANGSMITH_UNAVAILABLE",
  "INTERNAL_ERROR",
  "EVIDENCE_NOT_READY",
  "MAJOR_NOT_SELECTABLE",
  "PARSE_FAILED",
  "COURSE_UPLOAD_NOT_FOUND",
]);
export type ApiErrorCode = z.infer<typeof apiErrorCodeSchema>;

/** 서버는 모든 오류를 {"detail": {error_code, message}} 하나로 통일해 내려준다. */
export const apiErrorBodySchema = z.object({
  error_code: apiErrorCodeSchema,
  message: z.string(),
});
export const apiErrorEnvelopeSchema = z.object({ detail: apiErrorBodySchema });
export type ApiErrorBody = z.infer<typeof apiErrorBodySchema>;

/* ── Assessment: 세션·Context ───────────────────────────────────────── */

export const createSessionResponseSchema = z.object({
  session_id: z.string(),
  user_id: z.string(),
});
export type CreateSessionResponse = z.infer<typeof createSessionResponseSchema>;

export const interestRatingResponseSchema = z.object({
  session_id: z.string(),
  accepted: z.boolean(),
});

export const contextSelectResponseSchema = z.object({
  session_id: z.string(),
  contrast_context_id: z.string(),
  contrast_reason: z.string(),
  coverage_replacement_offered: z.array(z.string()).default([]),
});
export type ContextSelectResponse = z.infer<typeof contextSelectResponseSchema>;

export const contextConfirmResponseSchema = z.object({
  session_id: z.string(),
  final_context_ids: z.array(z.string()),
  processing_order: z.array(z.string()),
});
export type ContextConfirmResponse = z.infer<typeof contextConfirmResponseSchema>;

/* ── Assessment: 질문·답변 ──────────────────────────────────────────── */

export const questionDeliveryStatusSchema = z.enum([
  "GENERATED",
  "REGENERATING",
  "CACHE_USED",
  "BACKUP_USED",
  "CONTEXT_EARLY_TERMINATED",
]);
export type QuestionDeliveryStatus = z.infer<typeof questionDeliveryStatusSchema>;

export const finalizedOptionSchema = z.object({
  option_id: z.string(),
  role_id: z.string(),
  text: z.string(),
  // 내부 Trait 보정값. 화면에 절대 노출하지 않는다 (README_B §4).
  primary_trait_delta: z.record(z.string(), z.number()),
  next_probe: z.string().nullable().default(null),
});
export type FinalizedOption = z.infer<typeof finalizedOptionSchema>;

export const finalizedQuestionSchema = z.object({
  question_id: z.string(),
  context: z.string(),
  target_traits: z.array(z.string()),
  frame_id: z.string(),
  question_text: z.string(),
  options: z.array(finalizedOptionSchema),
  // Explicit Conflict 확인 질문에서만 값이 있다. 일반 질문과 동일하게 렌더링한다.
  contrast_id: z.string().nullable().default(null),
});
export type FinalizedQuestion = z.infer<typeof finalizedQuestionSchema>;

export const nextQuestionResponseSchema = z.object({
  session_id: z.string(),
  status: questionDeliveryStatusSchema,
  // CONTEXT_EARLY_TERMINATED면 null일 수 있다 — 이때 질문 Component를 렌더링하지 않는다.
  question: finalizedQuestionSchema.nullable(),
  current_context_id: z.string().nullable(),
  questions_asked_in_current_context: z.number().int(),
  assessment_complete: z.boolean().default(false),
});
export type NextQuestionResponse = z.infer<typeof nextQuestionResponseSchema>;

export const answerResponseSchema = z.object({
  session_id: z.string(),
  accepted: z.boolean(),
  next_action: z.enum(["NEXT_QUESTION", "CONTEXT_COMPLETE", "ASSESSMENT_COMPLETE"]),
});
export type AnswerResponse = z.infer<typeof answerResponseSchema>;

/* ── Career Profile ─────────────────────────────────────────────────── */

export const careerProfileHighlightSchema = z.object({
  text: z.string(),
  supporting_trait_ids: z.array(z.string()),
});

export const dimensionEvidenceItemSchema = z.object({
  context_id: z.string(),
  description: z.string(),
});

export const careerProfileSchema = z.object({
  session_id: z.string(),
  user_id: z.string(),
  // "~형"/"~타입"이 아닌 관찰 서술 문장. 화면에서 유형 뱃지로 감싸지 않는다.
  title: z.string(),
  highlights: z.array(careerProfileHighlightSchema),
  hashtags: z.array(z.string()),
  disclaimer: z.string(),
  detailed_evidence_by_dimension: z.record(z.string(), z.array(dimensionEvidenceItemSchema)),
  generated_at: z.string(),
});
export type CareerProfile = z.infer<typeof careerProfileSchema>;

/* ── 전공 · 학과 ────────────────────────────────────────────────────── */

export const relevanceLabelSchema = z.enum([
  "관련성 높음",
  "함께 탐색해볼 분야",
  "비교해볼 만한 분야",
]);
export type RelevanceLabel = z.infer<typeof relevanceLabelSchema>;

export const evidenceSufficiencyLabelSchema = z.enum(["충분", "보통", "제한적"]);
export type EvidenceSufficiencyLabel = z.infer<typeof evidenceSufficiencyLabelSchema>;

export const majorRelevanceSchema = z.object({
  major_id: z.string(),
  label: z.string(),
  relevance_label: relevanceLabelSchema,
  evidence_sufficiency: evidenceSufficiencyLabelSchema,
  repeated_context_count: z.number().int(),
});
export type MajorRelevance = z.infer<typeof majorRelevanceSchema>;

export const majorsResponseSchema = z.object({
  session_id: z.string(),
  relevant_majors: z.array(majorRelevanceSchema),
  explore_together_majors: z.array(majorRelevanceSchema),
  // null이 아니면 목록 UI 대신 이 문구를 보여준다 (README_B §4).
  insufficient_evidence_message: z.string().nullable().default(null),
});
export type MajorsResponse = z.infer<typeof majorsResponseSchema>;

export const departmentSchema = z.object({
  department_id: z.string(),
  university_name: z.string(),
  campus: z.string().nullable().default(null),
  region: z.string(),
  department_name: z.string(),
  college_name: z.string(),
  admission_unit: z.string().nullable().default(null),
  department_status: z.enum(["EXISTING", "NEW", "MERGED", "SPLIT", "ABOLISHED"]),
  source_svy_year: z.number().int(),
  source_url: z.string(),
  canonical_major_id: z.string().nullable().default(null),
});
export type Department = z.infer<typeof departmentSchema>;

export const departmentsResponseSchema = z.object({
  major_id: z.string(),
  departments: z.array(departmentSchema),
});
export type DepartmentsResponse = z.infer<typeof departmentsResponseSchema>;

/* ── 과목 (고교학점제) ──────────────────────────────────────────────── */

export const courseRecommendationItemSchema = z.object({
  subject_id: z.string(),
  label: z.string(),
  category: z.enum(["core", "explore", "alternative"]),
  // null = PRE_SURVEY 미확정. false(미개설 확정)로 해석하면 거짓 정보가 된다.
  is_actually_offered: z.boolean().nullable(),
  reason: z.string(),
  replaces_subject_id: z.string().nullable().default(null),
});
export type CourseRecommendationItem = z.infer<typeof courseRecommendationItemSchema>;

export const unavailableSubjectItemSchema = z.object({
  subject_id: z.string(),
  label: z.string(),
  reason: z.string(),
});
export type UnavailableSubjectItem = z.infer<typeof unavailableSubjectItemSchema>;

export const parsedSubjectCandidateSchema = z.object({
  raw_text: z.string(),
  // unmatched면 null이라 확정 대상이 될 수 없다 — 화면에서 선택 불가로 표시한다.
  matched_subject_id: z.string().nullable(),
  confidence: z.enum(["high", "low", "unmatched"]),
  requires_user_confirmation: z.boolean(),
});
export type ParsedSubjectCandidate = z.infer<typeof parsedSubjectCandidateSchema>;

export const courseProfileSchema = z.object({
  session_id: z.string(),
  source: z.enum(["PRE_SURVEY", "POST_OFFERING"]),
  recommendations: z.array(courseRecommendationItemSchema),
  unresolved_candidates: z.array(parsedSubjectCandidateSchema).default([]),
  unavailable_subjects: z.array(unavailableSubjectItemSchema).default([]),
});
export type CourseProfile = z.infer<typeof courseProfileSchema>;

export const courseParseWarningSchema = z.object({
  stage: z.string(),
  message: z.string(),
});
export type CourseParseWarning = z.infer<typeof courseParseWarningSchema>;

export const courseUploadResponseSchema = z.object({
  session_id: z.string(),
  selected_major_id: z.string(),
  parsed_candidates: z.array(parsedSubjectCandidateSchema),
  parse_warnings: z.array(courseParseWarningSchema).default([]),
});
export type CourseUploadResponse = z.infer<typeof courseUploadResponseSchema>;

export const courseConfirmResponseSchema = z.object({
  session_id: z.string(),
  accepted: z.boolean(),
  course_profile: courseProfileSchema,
});
export type CourseConfirmResponse = z.infer<typeof courseConfirmResponseSchema>;

/* ── Knowledge Subgraph ─────────────────────────────────────────────── */

export const subgraphNodeTypeSchema = z.enum([
  "Student",
  "Trait",
  "RelatedConcept",
  "CareerDimension",
  "CanonicalMajor",
  "Department",
  "University",
  "HighSchoolSubject",
  "Occupation",
]);
export type SubgraphNodeType = z.infer<typeof subgraphNodeTypeSchema>;

export const subgraphRelationTypeSchema = z.enum([
  "HAS_TRAIT",
  "RELATED_CONCEPT",
  "GROUPED_AS",
  "RELATED_TO",
  "HAS_DEPARTMENT",
  "BELONGS_TO",
  "RECOMMENDS",
]);
export type SubgraphRelationType = z.infer<typeof subgraphRelationTypeSchema>;

export const subgraphNodeSchema = z.object({
  node_id: z.string(),
  node_type: subgraphNodeTypeSchema,
  label: z.string(),
});
export type SubgraphNode = z.infer<typeof subgraphNodeSchema>;

export const subgraphEdgeSchema = z.object({
  source_node_id: z.string(),
  target_node_id: z.string(),
  relation_type: subgraphRelationTypeSchema,
  // 1~3. 숫자로 표시하지 않고 선 굵기·투명도로만 쓴다 (README_B 2026-08-29 §5).
  relevance_level: z.number().int(),
  evidence_ids: z.array(z.string()).default([]),
  source_ids: z.array(z.string()).default([]),
  mapping_version: z.string(),
  created_at: z.string(),
});
export type SubgraphEdge = z.infer<typeof subgraphEdgeSchema>;

export const subgraphResponseSchema = z.object({
  session_id: z.string(),
  nodes: z.array(subgraphNodeSchema),
  edges: z.array(subgraphEdgeSchema),
});
export type SubgraphResponse = z.infer<typeof subgraphResponseSchema>;

/* ── Session 복원 ───────────────────────────────────────────────────── */

export const sessionRestoreResponseSchema = z.object({
  session_id: z.string(),
  user_id: z.string(),
  phase: z.string(),
  has_previous_completed_profile: z.boolean(),
});
export type SessionRestoreResponse = z.infer<typeof sessionRestoreResponseSchema>;
