"""Subject / Course Planning Schema — 설계안 §20 구현.

CourseProfile은 개별 과목 식별자가 아니라 학생 세션의 "과목 추천 결과 집계" 객체다.
개별 과목은 항상 `subject_id`로 가리킨다(course_id 아님 — A 지시서 §3, 2026-08-20 정정).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

VectorScale = dict[str, float]


class SubjectProfile(BaseModel):
    """§20 Subject Vector. subject_id는 ids.generate_subject_id()로 생성한다."""

    subject_id: str
    label: str
    trait_vector: VectorScale = {}
    related_major_ids: list[str] = []
    source_id: str
    # 2026-08-25 15차 리뷰: 추천 이유(reason)에 넣을, 사람이 직접 짧게 요약한 대표 학습
    # 활동 한 줄("~하는 활동" 형태). Subject-Trait Evidence의 EVIDENCED 레코드 중 등급이
    # 가장 높은 것에서 결정론적으로 뽑는다(career_build_subject_profiles.py) — 성취기준
    # 원문을 그대로 노출하지 않기 위한 짧은 요약이다. 근거 기반으로 옮기지 않은 과목은
    # 빈 문자열(활동 요약을 지어내지 않는다).
    activity_summary: str = ""


class ParsedSubjectCandidate(BaseModel):
    """§20 POST_OFFERING / course_document_parser.py 출력. C가 만들고 B가 확인 UI에서 쓴다.

    Agent 판단이나 최종 추천은 여기 없다 — 추출 결과와 확신도만 담는다(CLAUDE.md:
    "과목 문서 Parser에는 입력 조건과 출력 Schema만 제공하고, 확정된 파싱 결과를 Course
    Planning에 반영한다").
    """

    raw_text: str  # PDF/Excel에서 그대로 추출된 문자열
    matched_subject_id: str | None  # Canonical Subject Mapping 성공 시
    confidence: Literal["high", "low", "unmatched"]
    requires_user_confirmation: bool


class CourseRecommendationItem(BaseModel):
    """2026-08-24 14차 리뷰: `is_actually_offered`를 `bool`에서 `bool | None`으로 바꿨다.
    PRE_SURVEY 시점에는 학교가 이 과목을 실제로 개설할지 아직 알 수 없다 — 예전
    `bool` 하나로는 True(실제 개설 확인)/False(미개설 확정)/모름 세 상태를 구분할 수
    없었다(미확정 상태를 False로 표현하면 "미개설이 확정됐다"는 거짓 정보가 된다).

    - `None`: PRE_SURVEY. 개설 여부 미확정 — 이때 `category="core"`는 "실제 개설이
      확인된 핵심 과목"이 아니라 "학생 Trait 근거가 충분한 희망 우선과목"이라는 뜻이다.
    - `True`: POST_OFFERING. 학교가 실제로 개설함을 확인.
    - `False`: POST_OFFERING. 미개설 또는 대체과목으로 전환됨.

    `src/engines/policy_guard.py::guard_offered_status_matches_core_category`가
    POST_OFFERING에서만 `is_actually_offered is True`인 과목만 `core`로 노출하도록
    강제한다 — PRE_SURVEY의 `core`는 이 검사 대상이 아니다(아직 미확정이라 막을
    이유가 없다)."""

    subject_id: str
    # 2026-08-25 15차 리뷰: subject_id만으로는 B가 화면에 과목명을 못 띄웠다 — 정본
    # SubjectProfile.label을 그대로 함께 내려준다(화면 표시용 이름을 별도로 지어내지
    # 않는다).
    label: str
    category: Literal["core", "explore", "alternative"]
    is_actually_offered: bool | None
    reason: str
    # 2026-08-26 16차 리뷰: category="alternative"일 때만 채운다 — "이 과목이 어떤
    # 미개설 희망과목을 대신하는가"를 가리킨다(UnavailableSubjectItem.subject_id와
    # 짝을 이룬다). core/explore는 대체가 아니라 원래부터의 추천이므로 항상 None이다.
    replaces_subject_id: str | None = None


class UnavailableSubjectItem(BaseModel):
    """2026-08-26 16차 리뷰: POST_OFFERING에서 원래 PRE_SURVEY 희망과목이었지만 학교가
    실제로 개설하지 않은 과목. `recommendations`에 category="alternative"로 섞어
    넣지 않고 별도 목록으로 분리한다 — "이 과목은 못 듣는다"는 사실 자체가 학생에게
    중요한 정보라 추천 목록 속에 파묻히면 안 된다."""

    subject_id: str
    label: str
    reason: str


class CourseProfile(BaseModel):
    """세션 하나의 과목 추천 결과 집계. PRE_SURVEY/POST_OFFERING 어느 쪽이든 이 형태로 반환한다.

    2026-08-26 16차 리뷰: `unavailable_subjects`를 추가했다. PRE_SURVEY에서는 항상
    빈 리스트다(개설 여부 자체가 아직 미확정이라 "미개설"이라는 사실이 존재하지
    않는다) — POST_OFFERING에서만 실제로 채워진다."""

    session_id: str
    source: Literal["PRE_SURVEY", "POST_OFFERING"]
    recommendations: list[CourseRecommendationItem]
    unresolved_candidates: list[ParsedSubjectCandidate] = []  # 사용자 확인 대기 중인 것들
    unavailable_subjects: list[UnavailableSubjectItem] = []


class CourseParseWarning(BaseModel):
    """2026-08-26 16차 리뷰: 문서 파싱 중 발생한 문제를 사용자에게 안전하게 알리는 값.
    로컬 임시 파일 경로·Stack Trace·원본 전체 텍스트는 절대 담지 않는다 — `stage`(
    course_document_parser.ParseError.stage와 동일한 값: "input"/"extract"/"normalize")
    와 사람이 읽을 수 있는 `message`만 담는다."""

    stage: str
    message: str


class CoursePlanningSessionState(BaseModel):
    """2026-08-26 16차 리뷰 §4: 업로드·확인 상태는 AssessmentState에 넣지 않는다
    (Assessment 질문 Planner는 이 상태를 볼 수 없어야 한다 — CLAUDE.md "Assessment
    단계에서 전공 추천 결과나 성적을 Planner 입력으로 사용하지 않는다"와 같은 방향).
    session_id 기준으로 `CoursePlanningStore`에 저장한다. 원본 파일 bytes와 임시
    파일 경로는 여기에도 저장하지 않는다 — `raw_text`(추출된 문자열)와 정규화된
    후보(`ParsedSubjectCandidate`)만 필요한 범위에서 담는다.

    새 파일을 다시 업로드하면 이전 미확정 결과는 명시적으로 통째로 교체된다(과거
    업로드의 후보가 새 업로드 후보와 섞이지 않는다) — `CoursePlanningStore.save()`가
    항상 이 객체 전체를 덮어쓰는 방식으로 구현된다."""

    session_id: str
    selected_major_id: str
    parsed_candidates: list[ParsedSubjectCandidate] = []
    confirmed_offered_subject_ids: list[str] = []
    # PARSED: 방금 파싱됨(모든 후보가 high 확신, 모호함 없음 — 그래도 자동 확정은 안 됨).
    # CONFIRMATION_REQUIRED: low 또는 unmatched 후보가 있어 사용자 확인이 꼭 필요함.
    # CONFIRMED: POST /course/confirm으로 실제 개설과목이 확정됨.
    upload_status: Literal["PARSED", "CONFIRMATION_REQUIRED", "CONFIRMED"] = "PARSED"
