"""Context–Trait Coverage Matrix(ContextPack 전용) — 2026-08-23 Trait Ontology
v2(2.8단계) §6. A 소유(중앙 통합).

`src/data/contexts/context_trait_coverage.py`(Legacy, 12-Trait, Contrast Context
Selector용 0~3 등급표)와는 완전히 다른 목적·다른 파일이다 — 이 모듈은 "이 ContextPack
안에 어떤 Trait를 관찰할 질문 후보가 실제로 존재하는가"(24-Trait 범위, Adaptive
Planner가 "이 Context에서 이 Trait를 더 물어볼 수 있는가"를 판단하는 자료)만 계산한다.
학생의 실제 관찰 점수가 아니다 — Evidence Confidence·Stop Condition 공식은 전혀
건드리지 않는다(§6 규칙 그대로)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from src.schemas.context_pack import ContextPack


class ContextTraitCoverageError(ValueError):
    """Pack이 24개 Trait Ontology에 없는 trait_id를 참조할 때(Fail-Closed)."""


class ContextTraitCoverage(BaseModel):
    context_id: str
    primary_trait_ids: set[str] = Field(default_factory=set)
    related_trait_ids: set[str] = Field(default_factory=set)
    direct_probe_trait_ids: set[str] = Field(default_factory=set)
    anchor_count: int = 0
    seed_question_count: int = 0
    backup_question_count: int = 0
    uncovered_trait_ids: set[str] = Field(default_factory=set)


def compute_context_trait_coverage(pack: ContextPack, known_trait_ids: set[str]) -> ContextTraitCoverage:
    """§6 규칙:
    - Seed·Backup Option의 `primary_trait_delta`(비어 있으면 NO_SIGNAL, 계산에서 제외)에
      등장하는 Trait는 PRIMARY로 센다.
    - Direct Probe Candidate의 `V2ProbeOptionMapping.trait_signals`는 `signal_role`로
      PRIMARY/RELATED를 구분해서 각각 센다(RELATED만 있는 Trait를 PRIMARY로 승격하지
      않는다 — §6 "RELATED-only Trait를 PRIMARY Coverage처럼 취급하지 마세요").
    - 같은 Trait가 여러 Option에 나와도 집합이라 자동으로 중복 제거된다.
    - 존재하지 않는(24개 Ontology 밖) trait_id가 하나라도 있으면 즉시 예외를 던진다
      (Fail-Closed — 이 함수는 검증하지 않고 조용히 넘어가지 않는다)."""

    primary_trait_ids: set[str] = set()
    related_trait_ids: set[str] = set()
    direct_probe_trait_ids: set[str] = set()

    for seed in pack.seed_anchor_variants:
        for option in seed.question.options:
            primary_trait_ids.update(option.primary_trait_delta)
    for backup in pack.anchor_backup_questions:
        for option in backup.question.options:
            primary_trait_ids.update(option.primary_trait_delta)

    for probe in pack.direct_probe_candidates:
        direct_probe_trait_ids.add(probe.trait_id)
        for mapping in probe.option_mappings:
            for signal in mapping.trait_signals:
                if signal.signal_role == "PRIMARY":
                    primary_trait_ids.add(signal.trait_id)
                elif signal.signal_role == "RELATED":
                    related_trait_ids.add(signal.trait_id)

    all_referenced = primary_trait_ids | related_trait_ids | direct_probe_trait_ids
    unknown = all_referenced - known_trait_ids
    if unknown:
        raise ContextTraitCoverageError(
            f"{pack.context_id}: 24개 Trait Ontology에 없는 trait_id {sorted(unknown)}"
        )

    uncovered_trait_ids = known_trait_ids - all_referenced

    return ContextTraitCoverage(
        context_id=pack.context_id,
        primary_trait_ids=primary_trait_ids,
        related_trait_ids=related_trait_ids,
        direct_probe_trait_ids=direct_probe_trait_ids,
        anchor_count=len(pack.anchor_presentations),
        seed_question_count=len(pack.seed_anchor_variants),
        backup_question_count=len(pack.anchor_backup_questions),
        uncovered_trait_ids=uncovered_trait_ids,
    )
