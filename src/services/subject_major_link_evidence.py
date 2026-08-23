"""Subject–Major 연결 근거 — A 소유, 2026-08-24 14차 리뷰, 설계안 §20 보조.

"이 과목이 이 전공과 관련 있다"는 근거는 "이 과목에서 이 Trait를 관찰·활용할 수 있다"는
근거(subject_trait_mapping_evidence.py)와 다른 질문이다 — 과목 성취기준이 특정 전공의
공식 교육과정(Major-Trait Mapping Evidence, 12차 리뷰)과 실제로 맞닿아 있는지를 별도로
기록한다. 이 파일이 없으면 `related_major_ids`에 왜 그 전공이 들어갔는지 아무도
역추적할 수 없다.

RELATED: 과목 성취기준과 전공 공식 교육과정(학과 교육목표·교과과정)이 직접 대응됨을
확인. NOT_RELATED: 확인했지만 명시적으로 관련 없음(공통 필수 교과처럼 특정 전공을
예측하지 못하는 경우 등). REVIEW_REQUIRED: 개념적으로는 그럴듯하나 공식 자료로 직접
대응을 확인하지 못함 — 2인 검토 필요. UNMAPPED: 이번 라운드 조사 범위 밖.

"공식 근거를 찾지 못함 ≠ 관련 없음"과 대칭으로, RELATED만 결정론적 빌드에서
SubjectProfile.related_major_ids에 반영한다(REVIEW_REQUIRED를 "관련 없음"으로 자동
확정하지 않는다 — 그렇다고 확정된 관련으로 승격하지도 않는다, 그냥 빈 채로 둔다).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, model_validator

LinkStatus = Literal["RELATED", "NOT_RELATED", "REVIEW_REQUIRED", "UNMAPPED"]

DEFAULT_LINK_EVIDENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "master" / "subject_major_link_evidence.jsonl"
)


class SubjectMajorLinkCurriculumEvidence(BaseModel):
    source_url: str
    source_type: str
    reason: str


class SubjectMajorLinkRecord(BaseModel):
    """`subject_major_link_evidence.jsonl`의 한 행 — 과목 하나 × 대표 전공 하나."""

    subject_id: str
    major_id: str
    link_status: LinkStatus
    evidence: list[SubjectMajorLinkCurriculumEvidence] = []
    author_id: str
    review_status: Literal["draft", "team_reviewed"] = "draft"
    mapping_version: str
    note: str = ""

    @model_validator(mode="after")
    def _related_requires_evidence(self) -> "SubjectMajorLinkRecord":
        if self.link_status in ("RELATED", "NOT_RELATED") and not self.evidence:
            raise ValueError(
                f"{self.subject_id}/{self.major_id}: {self.link_status}인데 근거(evidence)가 비어 있다"
            )
        return self


def load_subject_major_link_evidence(path: Path | None = None) -> list[SubjectMajorLinkRecord]:
    source = path or DEFAULT_LINK_EVIDENCE_PATH
    if not source.exists():
        return []
    return [
        SubjectMajorLinkRecord.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
