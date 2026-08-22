"""Major–Trait Mapping Evidence — A 소유, 설계안 §15/§16 보조.

2026-08-22 12차 리뷰: 기존 `src/data/majors/vertical_slice_major_profiles.py`의 Trait
등급은 공식 근거 없이 사람이 손으로 채운 숫자였다("이 전공엔 이 정도가 어울릴 것 같다"는
직관). 이 파일은 그 대신 "왜 이 전공에 이 Trait가 중요한가"를 실제 학과 공식 자료
(교육목표·교육과정)로 뒷받침하는 근거 구조를 정의한다.

핵심 원칙(사용자 지시 그대로): **공식 근거를 찾지 못함 ≠ Trait 중요도 0.** 등급을 매길
근거가 없는 조합은 `UNMAPPED`(아예 조사 못함)나 `REVIEW_REQUIRED`(단서는 있지만 확신
부족)로 남기고, `career_build_major_profiles.py`(빌드 단계)가 이 둘을 MajorProfile
Vector에서 완전히 제외한다 — 0.00으로 채우지 않는다("Trait가 중요하지 않다"와 "아직
확인 못했다"는 다른 뜻이므로).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

# EVIDENCED: 공식 자료로 등급까지 확정. NO_DIRECT_EVIDENCE: 공식 자료를 확인했지만 이
# Trait에 해당하는 활동이 명시적으로 중요하지 않음을 확인함(적극적 "0" 확정 — 조사하지
# 않은 UNMAPPED와 다르다). REVIEW_REQUIRED: 단서는 있으나 확신이 부족해 2인 검토 필요.
# UNMAPPED: 이번 1차 조사 범위에서 아예 확인하지 못함 — 존재 여부를 모른다는 뜻이다.
MappingStatus = Literal["EVIDENCED", "NO_DIRECT_EVIDENCE", "REVIEW_REQUIRED", "UNMAPPED"]

DEFAULT_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "major_trait_mapping_evidence.jsonl"
)


class MajorTraitCourseEvidence(BaseModel):
    university_name: str
    department_name: str
    evidence_type: str
    course_or_goal: str
    source_url: str
    reason: str


class MajorTraitMappingRecord(BaseModel):
    """`major_trait_mapping_evidence.jsonl`의 한 행 — 대표 전공 하나 × Trait 하나."""

    major_id: str
    trait_id: str
    mapping_status: MappingStatus
    grade: int | None = None
    evidence: list[MajorTraitCourseEvidence] = []
    author_id: str
    review_status: Literal["draft", "team_reviewed"] = "draft"
    mapping_version: str
    note: str = ""

    @model_validator(mode="after")
    def _grade_range(self) -> "MajorTraitMappingRecord":
        if self.grade is not None and self.grade not in (0, 1, 2, 3):
            raise ValueError(f"{self.major_id}/{self.trait_id}: grade는 0~3 정수여야 한다, got {self.grade!r}")
        return self

    @model_validator(mode="after")
    def _evidenced_requires_grade_and_evidence(self) -> "MajorTraitMappingRecord":
        if self.mapping_status in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
            if self.grade is None:
                raise ValueError(f"{self.major_id}/{self.trait_id}: {self.mapping_status}인데 grade가 없다")
            if not self.evidence:
                raise ValueError(f"{self.major_id}/{self.trait_id}: {self.mapping_status}인데 근거(evidence)가 비어 있다")
        return self

    @model_validator(mode="after")
    def _unmapped_and_review_required_have_no_grade(self) -> "MajorTraitMappingRecord":
        # 2026-08-22 12차: "공식 근거를 찾지 못함 ≠ Trait 중요도 0" — UNMAPPED/
        # REVIEW_REQUIRED에 실수로 grade(특히 0)를 적어 넣으면 빌드 단계가 "확정된 0점"과
        # "아직 모름"을 혼동할 수 있으므로 아예 Schema에서 막는다.
        if self.mapping_status in ("UNMAPPED", "REVIEW_REQUIRED") and self.grade is not None:
            raise ValueError(
                f"{self.major_id}/{self.trait_id}: {self.mapping_status}에는 grade를 채우지 않는다"
                "(등급 없음 = Matching 비교에서 제외, 0점과는 다르다)"
            )
        return self

    @model_validator(mode="after")
    def _high_grade_requires_evidence(self) -> "MajorTraitMappingRecord":
        # grade==3(핵심·필수 활동)은 근거 없이 매길 수 없다 — EVIDENCED 자체가 이미
        # evidence 비어있지 않음을 요구하지만, 이 규칙을 명시적으로 한 번 더 못박는다.
        if self.grade == 3 and not self.evidence:
            raise ValueError(f"{self.major_id}/{self.trait_id}: 근거 없이 grade=3을 매길 수 없다")
        return self


def load_major_trait_mapping_evidence(path: Path | None = None) -> list[MajorTraitMappingRecord]:
    source = path or DEFAULT_EVIDENCE_PATH
    if not source.exists():
        return []
    return [
        MajorTraitMappingRecord.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def normalized_grade_value(grade: int) -> float:
    """§13/§15와 동일한 0/.33/.67/1.00 정규화 — trait_normalizer.normalize_grade()를
    그대로 호출한다(정규화 정책을 이 파일이 복제하지 않는다)."""

    from src.engines.trait_normalizer import normalize_grade

    return normalize_grade(grade)
