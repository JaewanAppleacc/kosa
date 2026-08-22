"""학과 단위 추천 적격성 정책 — A 소유, 설계안 §18 보조.

2026-08-22 10차 리뷰: `EXCLUDED_RECOMMENDATION_MAJOR_IDS`(major_id 하나 통째로 막는
방식, major_exploration_service.py)만으로는 "다른 canonical_major_id로 잘못 Mapping된
예체능 학과"를 막지 못한다 — 예를 들어 산업디자인학과가 실수로 `hci_ux`로 Mapping되면
major_id 차단을 그대로 통과한다. 이 파일은 그 빈틈을 메우는 "학과(department_id) 단위"
정책이다.

2026-08-22 11차 리뷰: department_id만으로 승인 여부를 판정하면, 같은 학과가 원래
승인된 전공과 "다른" 전공으로 나중에 잘못 Mapping돼도(예: 고려대 미디어학부가 실수로
hci_ux로 재매핑) department_id는 그대로라 승인이 따라와 버린다 — 그래서 판정은 항상
(department_id, canonical_major_id) 쌍으로 한다. 이 파일 자체에도 다음 방어를 추가했다:
  - Pydantic model_validator로 eligibility_status↔recommendation_eligible 모순, APPROVED
    근거 최소조건, hci_ux 승인 학과의 HCI/UX 과목 근거를 데이터 로딩 시점에 강제한다.
  - Loader가 중복 department_id를 조용히 덮어쓰지 않고 즉시 예외를 던진다.

CLAUDE.md 책임 분리를 그대로 따른다:
- Repository(C 소유)는 데이터 조회만 한다.
- 이 Policy(A 소유)는 "이 학과를 이 전공으로 사용자에게 추천해도 되는가"만 판정한다 —
  학과명 문자열을 즉석에서 분류하지 않고, 미리 검토해 기록해 둔 `data/master/
  department_recommendation_scope.jsonl`(사람이 공식 자료로 확인한 근거)만 읽는다.
- MajorExplorationService(A 소유)가 이 Policy와 상태·출처 필터를 조합해 최종 노출을
  결정한다.

Fail-Closed: 검토 기록이 아예 없거나, 기록은 있어도 요청받은 canonical_major_id와
다르면 승인된 것으로 취급하지 않는다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, model_validator

EligibilityStatus = Literal["APPROVED", "EXCLUDED_ARTS_SPORTS", "REVIEW_REQUIRED"]
AcademicField = Literal[
    "HUMANITIES_SOCIAL", "NATURAL_SCIENCE", "ENGINEERING", "EDUCATION",
    "INTERDISCIPLINARY", "ARTS_SPORTS", "UNKNOWN",
]

DEFAULT_SCOPE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "department_recommendation_scope.jsonl"
)


class DuplicateDepartmentScopeRecordError(ValueError):
    """정책 파일에 같은 department_id가 두 번 이상 등장할 때 — 어느 검토 결과가 맞는지
    알 수 없으므로 조용히 뒤 항목으로 덮어쓰지 않고 즉시 실패시킨다."""


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

    @model_validator(mode="after")
    def _status_and_boolean_must_agree(self) -> "DepartmentRecommendationScopeRecord":
        expected = self.eligibility_status == "APPROVED"
        if self.recommendation_eligible != expected:
            raise ValueError(
                f"{self.department_id}: eligibility_status={self.eligibility_status!r}인데 "
                f"recommendation_eligible={self.recommendation_eligible!r} — "
                f"APPROVED는 반드시 true, 나머지는 반드시 false여야 한다"
            )
        return self

    @model_validator(mode="after")
    def _approved_requires_minimum_evidence(self) -> "DepartmentRecommendationScopeRecord":
        if self.eligibility_status != "APPROVED":
            return self
        if not self.classification_evidence:
            raise ValueError(f"{self.department_id}: APPROVED인데 classification_evidence가 비어 있다")
        for evidence in self.classification_evidence:
            if not evidence.source_url.strip():
                raise ValueError(f"{self.department_id}: classification_evidence에 빈 source_url이 있다")
        if not self.reviewer_id.strip():
            raise ValueError(f"{self.department_id}: APPROVED인데 reviewer_id가 비어 있다")
        if not self.decision_reason.strip():
            raise ValueError(f"{self.department_id}: APPROVED인데 decision_reason이 비어 있다")
        return self

    @model_validator(mode="after")
    def _approved_hci_ux_requires_curriculum_evidence(self) -> "DepartmentRecommendationScopeRecord":
        # hci_ux 승인 학과만 HCI/UX 교과목 근거를 강제한다 — 다른 전공(media_communication·
        # industrial_engineering 등)에는 이 요구를 강제하지 않는다.
        if self.eligibility_status != "APPROVED" or self.canonical_major_id != "hci_ux":
            return self
        if not self.hci_ux_curriculum_evidence:
            raise ValueError(f"{self.department_id}: hci_ux APPROVED인데 hci_ux_curriculum_evidence가 비어 있다")
        for course in self.hci_ux_curriculum_evidence:
            if not course.course_name.strip() or not course.source_url.strip():
                raise ValueError(f"{self.department_id}: hci_ux_curriculum_evidence에 빈 course_name/source_url이 있다")
        return self


def load_department_recommendation_scope(
    path: Path | None = None,
) -> dict[str, DepartmentRecommendationScopeRecord]:
    """중복 department_id를 조용히 덮어쓰지 않는다 — 발견 즉시
    DuplicateDepartmentScopeRecordError를 던진다(원본 학생 데이터·민감정보는 담지 않고
    department_id만 메시지에 남긴다)."""

    source = path or DEFAULT_SCOPE_PATH
    if not source.exists():
        return {}

    result: dict[str, DepartmentRecommendationScopeRecord] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = DepartmentRecommendationScopeRecord.model_validate(json.loads(line))
        if record.department_id in result:
            raise DuplicateDepartmentScopeRecordError(
                f"duplicate department recommendation scope record: {record.department_id}"
            )
        result[record.department_id] = record
    return result


class DepartmentRecommendationScopePolicy(Protocol):
    """MajorExplorationService가 참조하는 판정 인터페이스 — Fake로 교체 가능하도록
    Protocol로 둔다(테스트에서 실제 JSONL 없이도 정책 로직을 검증할 수 있게).

    2026-08-22 11차: department_id만으로 판정하면, 같은 학과가 나중에 다른 major_id로
    잘못 Mapping돼도 department_id가 같다는 이유로 승인이 그대로 따라온다 — 그래서
    "이 학과를 이 전공으로" 승인했는지, 즉 (department_id, canonical_major_id) 쌍으로
    판정한다."""

    def is_approved(self, department_id: str, canonical_major_id: str) -> bool: ...


class JsonlDepartmentRecommendationScopePolicy:
    """`department_recommendation_scope.jsonl`을 앱 시작 시 한 번 읽어 메모리에 들고
    있는 기본 구현. 다음을 모두 만족해야 승인한다(Fail-Closed) — 하나라도 어긋나면 거부:

    1. department_id에 대한 검토 기록이 존재
    2. eligibility_status == "APPROVED"
    3. recommendation_eligible is True
    4. 기록의 canonical_major_id == 요청받은 canonical_major_id

    2·3은 Schema의 model_validator가 이미 항상 일치하도록 강제하지만, Schema 검증만
    믿지 않고 여기서도 다시 확인한다(방어적 이중 확인)."""

    def __init__(
        self,
        records: dict[str, DepartmentRecommendationScopeRecord] | None = None,
        path: Path | None = None,
    ) -> None:
        self._records = records if records is not None else load_department_recommendation_scope(path)

    def is_approved(self, department_id: str, canonical_major_id: str) -> bool:
        record = self._records.get(department_id)
        if record is None:
            return False
        return (
            record.eligibility_status == "APPROVED"
            and record.recommendation_eligible is True
            and record.canonical_major_id == canonical_major_id
        )
