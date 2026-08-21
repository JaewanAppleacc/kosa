"""Explicit Conflict / Context Dependency 판정 — 설계안 §12-1 순수 계산 로직. LLM·DB 호출 없음.

CLAUDE.md: "단순 Context 차이를 Conflict로 판정하지 않는다. 사전 정의한 Contrast Pair의
명시적 상충만 Conflict로 처리한다." 이 파일은 그 규칙을 그대로 코드로 옮긴다 — 서로 다른
Context에서 서로 다른 Trait가 나왔다는 이유만으로는 절대 CONFLICTING을 만들지 않고, 반드시
사전 정의된 ContrastDefinition(양쪽 Role, 비교 가능한 Frame, 최소 Evidence 개수)을 통과해야만
Explicit Conflict로 판정한다.
"""

from __future__ import annotations

from src.schemas.evidence import (
    ConflictDetectionResult,
    ContrastDefinition,
    ContrastPairResult,
    EvidenceOrigin,
    EvidenceRecord,
)


def detect_explicit_conflicts(
    evidence_ledger: list[EvidenceRecord],
    contrast_definitions: list[ContrastDefinition],
) -> ConflictDetectionResult:
    """§12-1 판정 순서를 그대로 구현한다.

    1. 이 ContrastDefinition의 positive_role_ids/opposite_role_ids로 기록된 Evidence를
       각각 모은다(Secondary Hypothesis는 §12/CLAUDE.md 원칙대로 제외 — 확정 전까지는
       계산에 넣지 않는다).
    2. 어느 한쪽이라도 Evidence가 아예 없으면 판정 자체가 불가능하다(insufficient_evidence).
    3. 양쪽 다 있으면, comparable_frame_ids 안에서 관찰된 것만 다시 걸러
       minimum_evidence_each_side를 각각 채우는지 본다.
       - 채우면 EXPLICIT_CONFLICT: 그 Evidence들이 실제로 기록한 Trait(들)이 Mask 대상이다.
       - 못 채우면(같은 상황에서 직접 대조된 게 아니라 서로 다른 상황에서 나온 반대
         Evidence다) CONTEXT_DEPENDENT — Mask하지 않는다.

    Trait id는 ContrastDefinition에 별도로 저장하지 않는다 — 매칭된 EvidenceRecord 자신의
    `applied_primary_trait_delta`가 이미 "이 Role을 골랐을 때 실제로 어떤 Trait가 기록됐는지"를
    갖고 있으므로 그걸 그대로 쓴다(중복 정의로 인한 불일치 위험을 없앤다).
    """

    primary = [e for e in evidence_ledger if e.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT]

    pair_results: list[ContrastPairResult] = []
    unresolved_conflict_trait_ids: set[str] = set()
    explicit_conflict_count_by_trait: dict[str, int] = {}
    context_dependency_flag_by_trait: dict[str, bool] = {}

    for contrast in contrast_definitions:
        positive_evidence = [e for e in primary if e.option_role_id in contrast.positive_role_ids]
        opposite_evidence = [e for e in primary if e.option_role_id in contrast.opposite_role_ids]

        if not positive_evidence or not opposite_evidence:
            pair_results.append(
                ContrastPairResult(contrast_id=contrast.contrast_id, status="insufficient_evidence", trait_ids=set())
            )
            continue

        trait_ids: set[str] = set()
        for e in positive_evidence + opposite_evidence:
            trait_ids.update(e.applied_primary_trait_delta)

        positive_comparable = [e for e in positive_evidence if e.question_frame_id in contrast.comparable_frame_ids]
        opposite_comparable = [e for e in opposite_evidence if e.question_frame_id in contrast.comparable_frame_ids]

        if (
            len(positive_comparable) >= contrast.minimum_evidence_each_side
            and len(opposite_comparable) >= contrast.minimum_evidence_each_side
        ):
            unresolved_conflict_trait_ids.update(trait_ids)
            for trait_id in trait_ids:
                explicit_conflict_count_by_trait[trait_id] = explicit_conflict_count_by_trait.get(trait_id, 0) + 1
            pair_results.append(
                ContrastPairResult(contrast_id=contrast.contrast_id, status="explicit_conflict", trait_ids=trait_ids)
            )
        else:
            for trait_id in trait_ids:
                context_dependency_flag_by_trait[trait_id] = True
            pair_results.append(
                ContrastPairResult(contrast_id=contrast.contrast_id, status="context_dependent", trait_ids=trait_ids)
            )

    return ConflictDetectionResult(
        pair_results=pair_results,
        unresolved_conflict_trait_ids=unresolved_conflict_trait_ids,
        explicit_conflict_count_by_trait=explicit_conflict_count_by_trait,
        context_dependency_flag_by_trait=context_dependency_flag_by_trait,
    )
