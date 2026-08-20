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
    subject_id: str
    category: Literal["core", "explore", "alternative"]
    is_actually_offered: bool  # False면 절대 "핵심"으로 노출하지 않는다 (policy_guard 규칙 6)
    reason: str


class CourseProfile(BaseModel):
    """세션 하나의 과목 추천 결과 집계. PRE_SURVEY/POST_OFFERING 어느 쪽이든 이 형태로 반환한다."""

    session_id: str
    source: Literal["PRE_SURVEY", "POST_OFFERING"]
    recommendations: list[CourseRecommendationItem]
    unresolved_candidates: list[ParsedSubjectCandidate] = []  # 사용자 확인 대기 중인 것들
