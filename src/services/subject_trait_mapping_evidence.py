"""Subject–Trait Mapping Evidence — A 소유, 2026-08-23/24 14차 리뷰.

`src/services/major_trait_mapping_evidence.py`(12차 리뷰)와 같은 구조를 과목 단위로
적용한다. 기존 `data/master/subjects.jsonl`의 `trait_vector`는 공식 근거 없이 사람이
손으로 채운 값이었다 — 이 파일은 그 대신 "왜 이 과목에서 이 Trait를 관찰·활용할 수
있는가"를 2022 개정 교육과정 공식 성취기준(교육부 고시 제2022-33호)으로 뒷받침하는
근거 구조를 정의한다.

핵심 원칙(major_trait_mapping_evidence.py와 동일): **공식 근거를 찾지 못함 ≠ Trait
중요도 0.** UNMAPPED/REVIEW_REQUIRED는 grade를 채우지 않고, 빌드 단계가 이 둘을
SubjectProfile.trait_vector에서 완전히 제외한다.

2026-08-24 리뷰로 등급 규칙을 한 단계 더 명확히 한다(major_trait_mapping_evidence.py도
같은 라운드에 동일하게 강화됨): NO_DIRECT_EVIDENCE는 "공식 자료로 이 활동이 명시적으로
중요하지 않음을 확인했다"는 뜻이라 grade가 반드시 0이어야 하고, EVIDENCED는 "공식
자료로 어느 정도 중요함을 확인했다"는 뜻이라 grade가 반드시 1~3이어야 한다(0은
NO_DIRECT_EVIDENCE로 표현한다) — 이 파일은 처음부터 이 규칙으로 만든다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

MappingStatus = Literal["EVIDENCED", "NO_DIRECT_EVIDENCE", "REVIEW_REQUIRED", "UNMAPPED"]

DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "subject_trait_mapping_evidence.jsonl"
)


class SubjectTraitCurriculumEvidence(BaseModel):
    source_url: str
    source_type: str
    course_goal_or_standard: str
    reason: str


class SubjectTraitMappingRecord(BaseModel):
    """`subject_trait_mapping_evidence.jsonl`의 한 행 — 과목 하나 × Trait 하나."""

    subject_id: str
    trait_id: str
    mapping_status: MappingStatus
    grade: int | None = None
    curriculum_evidence: list[SubjectTraitCurriculumEvidence] = []
    author_id: str
    review_status: Literal["draft", "team_reviewed"] = "draft"
    mapping_version: str
    note: str = ""

    @model_validator(mode="after")
    def _grade_range(self) -> "SubjectTraitMappingRecord":
        if self.grade is not None and self.grade not in (0, 1, 2, 3):
            raise ValueError(f"{self.subject_id}/{self.trait_id}: grade는 0~3 정수여야 한다, got {self.grade!r}")
        return self

    @model_validator(mode="after")
    def _evidenced_requires_grade_and_evidence(self) -> "SubjectTraitMappingRecord":
        if self.mapping_status in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
            if self.grade is None:
                raise ValueError(f"{self.subject_id}/{self.trait_id}: {self.mapping_status}인데 grade가 없다")
            if not self.curriculum_evidence:
                raise ValueError(
                    f"{self.subject_id}/{self.trait_id}: {self.mapping_status}인데 근거(curriculum_evidence)가 비어 있다"
                )
        return self

    @model_validator(mode="after")
    def _status_specific_grade_range(self) -> "SubjectTraitMappingRecord":
        """§2: EVIDENCED는 grade 1~3, NO_DIRECT_EVIDENCE는 grade 0 고정 — "공식 근거
        없음 ≠ 0"과 "공식 근거로 명시적으로 0을 확인함"을 등급 범위 자체로 구분한다."""

        if self.mapping_status == "NO_DIRECT_EVIDENCE" and self.grade != 0:
            raise ValueError(
                f"{self.subject_id}/{self.trait_id}: NO_DIRECT_EVIDENCE는 grade가 반드시 0이어야 한다"
                f"(got {self.grade!r})"
            )
        if self.mapping_status == "EVIDENCED" and self.grade not in (1, 2, 3):
            raise ValueError(
                f"{self.subject_id}/{self.trait_id}: EVIDENCED는 grade가 1~3이어야 한다"
                f"(0은 NO_DIRECT_EVIDENCE로 표현한다 — got {self.grade!r})"
            )
        return self

    @model_validator(mode="after")
    def _unmapped_and_review_required_have_no_grade(self) -> "SubjectTraitMappingRecord":
        if self.mapping_status in ("UNMAPPED", "REVIEW_REQUIRED") and self.grade is not None:
            raise ValueError(
                f"{self.subject_id}/{self.trait_id}: {self.mapping_status}에는 grade를 채우지 않는다"
                "(등급 없음 = Matching 비교에서 제외, 0점과는 다르다)"
            )
        return self

    @model_validator(mode="after")
    def _high_grade_requires_evidence(self) -> "SubjectTraitMappingRecord":
        if self.grade == 3 and not self.curriculum_evidence:
            raise ValueError(f"{self.subject_id}/{self.trait_id}: 근거 없이 grade=3을 매길 수 없다")
        return self


def load_subject_trait_mapping_evidence(path: Path | None = None) -> list[SubjectTraitMappingRecord]:
    source = path or DEFAULT_EVIDENCE_PATH
    if not source.exists():
        return []
    return [
        SubjectTraitMappingRecord.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
