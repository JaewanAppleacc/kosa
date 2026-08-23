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
    ContrastResolutionRecord,
    ContrastResolutionStatus,
    ContrastPairResult,
    EvidenceOrigin,
    EvidenceRecord,
)


def detect_explicit_conflicts(
    evidence_ledger: list[EvidenceRecord],
    contrast_definitions: list[ContrastDefinition],
    resolutions: dict[str, ContrastResolutionRecord] | None = None,
) -> ConflictDetectionResult:
    """§12-1 판정 + 2026-08-22 리뷰 반영 해소(Resolution) 로직.

    2026-08-22 리뷰로 발견한 버그: Evidence는 계속 누적되기만 하므로, "양쪽 다
    minimum_evidence_each_side 이상"이라는 조건은 한 번 참이 되면 그 뒤로 답변이 아무리
    쌓여도 절대 거짓이 될 수 없다(Evidence를 지우지 않는 한). 그래서 "추가 Evidence가
    쌓이면 자동으로 조건에서 빠진다"는 예전 설명은 틀렸다 — 탐지 조건만으로는 Conflict가
    영원히 해소되지 않는다. 이 함수는 그래서 탐지와 해소를 분리한다:

    1. 이 ContrastDefinition에 이미 ContrastResolutionRecord가 있으면(학생이 확인 질문에
       답했으면) Evidence 재계산과 무관하게 그 Record의 상태를 그대로 따른다:
       - RESOLVED_POSITIVE/RESOLVED_OPPOSITE → status="resolved", Mask 해제.
       - RESOLVED_CONTEXT_DEPENDENT → status="context_dependent", Mask 해제,
         context_dependency_flag만 표시(§12-1: 두 Trait 다 결함처럼 표현하지 않는다).
       - UNRESOLVED → status="explicit_conflict"로 계속 Mask하되, 이미 한 번 확인
         질문을 물어봤으므로 `contrast_ids_needing_resolution_question`에는 다시
         올리지 않는다(무한 반복 방지).
    2. Record가 없으면 예전과 같은 Evidence 기반 탐지를 한다. 조건을 새로 충족하면
       DETECTED 상태이므로 `contrast_ids_needing_resolution_question`에 추가한다 —
       Target Planner가 이걸 보고 다음 질문을 확인 질문으로 정한다.

    Trait id는 ContrastDefinition에 별도로 저장하지 않는다 — 매칭된 EvidenceRecord 자신의
    `applied_primary_trait_delta`가 이미 "이 Role을 골랐을 때 실제로 어떤 Trait가 기록됐는지"를
    갖고 있으므로 그걸 그대로 쓴다(중복 정의로 인한 불일치 위험을 없앤다).
    """

    resolutions = resolutions or {}
    primary = [e for e in evidence_ledger if e.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT]

    pair_results: list[ContrastPairResult] = []
    unresolved_conflict_trait_ids: set[str] = set()
    explicit_conflict_count_by_trait: dict[str, int] = {}
    context_dependency_flag_by_trait: dict[str, bool] = {}
    contrast_ids_needing_resolution_question: set[str] = set()

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

        resolution = resolutions.get(contrast.contrast_id)
        if resolution is not None:
            if resolution.status == ContrastResolutionStatus.RESOLVED_CONTEXT_DEPENDENT:
                for trait_id in trait_ids:
                    context_dependency_flag_by_trait[trait_id] = True
                pair_results.append(
                    ContrastPairResult(contrast_id=contrast.contrast_id, status="context_dependent", trait_ids=trait_ids)
                )
            elif resolution.status in (
                ContrastResolutionStatus.RESOLVED_POSITIVE,
                ContrastResolutionStatus.RESOLVED_OPPOSITE,
            ):
                pair_results.append(
                    ContrastPairResult(contrast_id=contrast.contrast_id, status="resolved", trait_ids=trait_ids)
                )
            else:  # UNRESOLVED — 계속 Mask하되 다시 물어보진 않는다.
                unresolved_conflict_trait_ids.update(trait_ids)
                for trait_id in trait_ids:
                    explicit_conflict_count_by_trait[trait_id] = explicit_conflict_count_by_trait.get(trait_id, 0) + 1
                pair_results.append(
                    ContrastPairResult(contrast_id=contrast.contrast_id, status="explicit_conflict", trait_ids=trait_ids)
                )
            continue

        positive_comparable = [e for e in positive_evidence if e.question_frame_id in contrast.comparable_frame_ids]
        opposite_comparable = [e for e in opposite_evidence if e.question_frame_id in contrast.comparable_frame_ids]

        if (
            len(positive_comparable) >= contrast.minimum_evidence_each_side
            and len(opposite_comparable) >= contrast.minimum_evidence_each_side
        ):
            unresolved_conflict_trait_ids.update(trait_ids)
            contrast_ids_needing_resolution_question.add(contrast.contrast_id)
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
        contrast_ids_needing_resolution_question=contrast_ids_needing_resolution_question,
    )
