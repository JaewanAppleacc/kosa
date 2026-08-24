"""Trait Evidence Coverage Shadow Schema — a/trait-evidence-coverage-shadow.

**Shadow 전용 내부 진단 모델이다.** 학생 API에 노출하지 않는다(공개 Schema는 절대
수정하지 않는다). Runtime Stop Condition·Matching·질문 흐름 어디에도 아직 연결하지
않는다 — `src/engines/trait_evidence_coverage_engine.py`가 이 모델을 채우는 순수
계산만 한다.

`SUFFICIENT`가 뜻하는 것: "이 Trait가 높다"가 아니라 "높음/낮음/상황 의존적을 판단할
만큼 근거가 충분하다"는 뜻뿐이다. 어떤 상태도 Trait의 방향(높다/낮다)을 담지 않는다 —
그건 이미 존재하는 `TraitState`/`TraitVectorEntry`의 몫이고, 이 모델은 "판단이
가능한가"만 본다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CoverageStatus = Literal["UNOBSERVED", "LIMITED", "SUPPORTED", "SUFFICIENT", "CONFLICTED"]


class TraitCoverageResult(BaseModel):
    """Trait 하나의 Coverage 진단 결과. 학생 화면·공개 API에 노출하지 않는다."""

    trait_id: str
    coverage_status: CoverageStatus
    effective_evidence_weight: float
    primary_evidence_count: int
    related_evidence_count: int
    distinct_context_count: int
    distinct_frame_count: int
    # 상반 방향 Evidence가 전혀 없으면(이 Trait이 등록된 Contrast Pair의 어느 쪽에도
    # 관여하지 않거나, 관여해도 반대쪽 근거가 아직 없으면) 1.0 — "불일치가 없다"는 뜻이지
    # "확인했더니 100% 같았다"는 뜻이 아니다. 두 경우를 구분해야 하면 unresolved_conflict_
    # count와 함께 봐야 한다(이 필드 하나만으로 "측정된 적 없음"과 "완전히 일치함"을
    # 구분할 수 없다는 걸 알고 쓴다 — CLAUDE.md "Missing과 0점을 같게 취급하지 않는다"
    # 원칙은 coverage_status의 UNOBSERVED/CONFLICTED 분기로 지킨다).
    directional_consistency: float = 1.0
    unresolved_conflict_count: int = 0
    # SUFFICIENT 기준 중 아직 충족되지 않은 항목의 사람이 읽을 수 있는 설명. SUFFICIENT일
    # 때는 항상 빈 리스트다.
    missing_requirements: list[str] = Field(default_factory=list)
    # 원본 EvidenceRecord.evidence_id — 등장 순서를 보존한 중복 없는 목록(dict.fromkeys
    # 패턴, trait_vector_snapshot_engine.py와 동일 관례).
    contributing_evidence_ids: list[str] = Field(default_factory=list)
