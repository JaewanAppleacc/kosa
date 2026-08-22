"""학과 단위 추천 적격성 정책 — A 소유, 설계안 §18 보조.

2026-08-22 10차 리뷰: `EXCLUDED_RECOMMENDATION_MAJOR_IDS`(major_id 하나 통째로 막는
방식, major_exploration_service.py)만으로는 "다른 canonical_major_id로 잘못 Mapping된
예체능 학과"를 막지 못한다 — 예를 들어 산업디자인학과가 실수로 `hci_ux`로 Mapping되면
major_id 차단을 그대로 통과한다. 이 파일은 그 빈틈을 메우는 "학과(department_id) 단위"
정책이다.

CLAUDE.md 책임 분리를 그대로 따른다:
- Repository(C 소유)는 데이터 조회만 한다.
- 이 Policy(A 소유)는 "이 학과 하나를 사용자에게 추천해도 되는가"만 판정한다 — 학과명
  문자열을 즉석에서 분류하지 않고, 미리 검토해 기록해 둔 `data/master/
  department_recommendation_scope.jsonl`(사람이 공식 자료로 확인한 근거)만 읽는다.
- MajorExplorationService(A 소유)가 이 Policy와 상태·출처 필터를 조합해 최종 노출을
  결정한다.

Fail-Closed: 검토 기록이 아예 없는 학과는 승인된 것으로 취급하지 않는다(§4) — 이 Policy
는 "명시적으로 APPROVED라고 확인된 것만 통과시킨다"는 방향으로만 동작한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel

EligibilityStatus = Literal["APPROVED", "EXCLUDED_ARTS_SPORTS", "REVIEW_REQUIRED"]
AcademicField = Literal[
    "HUMANITIES_SOCIAL", "NATURAL_SCIENCE", "ENGINEERING", "EDUCATION",
    "INTERDISCIPLINARY", "ARTS_SPORTS", "UNKNOWN",
]

DEFAULT_SCOPE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "department_recommendation_scope.jsonl"
)


class ClassificationEvidence(BaseModel):
    evidence_type: str
    source_url: str
    summary: str


class CourseEvidence(BaseModel):
    course_name: str
    source_url: str


class DepartmentRecommendationScopeRecord(BaseModel):
    """`department_recommendation_scope.jsonl`의 한 행 — 학과 하나의 추천 적격성 검토
    기록. `is_arts_or_pe=false` 같은 자기선언 한 값이 아니라, 공식 계열·입학·교육과정
    근거를 각각 URL과 함께 분리해서 담는다."""

    department_id: str
    university_name: str
    department_name: str
    college_name: str
    canonical_major_id: str
    academic_field: AcademicField
    eligibility_status: EligibilityStatus
    recommendation_eligible: bool
    classification_evidence: list[ClassificationEvidence] = []
    hci_ux_curriculum_evidence: list[CourseEvidence] = []
    reviewer_id: str
    reviewed_at: str
    decision_reason: str


def load_department_recommendation_scope(
    path: Path | None = None,
) -> dict[str, DepartmentRecommendationScopeRecord]:
    source = path or DEFAULT_SCOPE_PATH
    if not source.exists():
        return {}
    records = [
        DepartmentRecommendationScopeRecord.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {r.department_id: r for r in records}


class DepartmentRecommendationScopePolicy(Protocol):
    """MajorExplorationService가 참조하는 판정 인터페이스 — Fake로 교체 가능하도록
    Protocol로 둔다(테스트에서 실제 JSONL 없이도 정책 로직을 검증할 수 있게)."""

    def is_approved(self, department_id: str) -> bool: ...


class JsonlDepartmentRecommendationScopePolicy:
    """`department_recommendation_scope.jsonl`을 앱 시작 시 한 번 읽어 메모리에 들고
    있는 기본 구현. `APPROVED` 상태의 명시적 검토 기록이 있는 학과만 통과시킨다 —
    `EXCLUDED_ARTS_SPORTS`·`REVIEW_REQUIRED`·기록 없음은 전부 거부(Fail-Closed)."""

    def __init__(
        self,
        records: dict[str, DepartmentRecommendationScopeRecord] | None = None,
        path: Path | None = None,
    ) -> None:
        self._records = records if records is not None else load_department_recommendation_scope(path)

    def is_approved(self, department_id: str) -> bool:
        record = self._records.get(department_id)
        return record is not None and record.eligibility_status == "APPROVED"
