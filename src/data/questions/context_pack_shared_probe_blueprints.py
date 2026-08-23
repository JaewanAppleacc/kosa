"""ContextPack 공용 Adaptive Probe Blueprint — 2026-08-23 Trait Ontology v2(2.9단계) §5.

신규 12개 Context Pack은 각자 `direct_probe_candidates=[]`다(T·S·L 소유 파일, A가 직접
채우지 않는다 — CLAUDE.md "A가 소유하지 않는 영역"). 이 파일은 그 공백을 "Context마다
새 Trait Mapping을 만드는" 방식이 아니라, 이미 검토된 기존 14개 Legacy V2 Direct Probe
Blueprint(`trait_v2_direct_probe_blueprints.py`, game/media/school_life 전용)의
**role_id → Trait Signal Mapping을 그대로 재사용**하고 `allowed_context_ids`만 신규
12개 배치 Context로 넓힌 별도 사본으로 채운다(§5 "질문 Mapping은 공통으로 유지하고
표현만 Context화").

원본 14개는 전혀 건드리지 않는다(Legacy game/media/school_life Direct Probe 흐름과
완전히 분리) — 이 파일의 Blueprint는 새 blueprint_id·question_id·option_id를 쓰고,
`review_status="draft"`로 시작한다. 문구·Mapping이 원본과 같아도 "새 Context에서
쓰기에 적절한가"는 아직 사람이 확인하지 않았으므로 자동 승인하지 않는다(§5/§11 —
Claude가 검수 상태를 대신 채우지 않는다). 실제 서빙 시 문구는 Anchor·Context 정보로
LLM이 다시 표현한다(`v2_direct_probe_generator.py`, 이 파일이 만드는 `base_question`은
LLM이 꺼졌을 때만 쓰이는 Fallback이다).

`ContextPackRuntime.get_direct_probe_candidates()`가 이 목록을 검수 상태
(`context_pack_shared_probe_review_store.py`)로 걸러 Context별 후보에 병합한다 —
`context_pack_registry.py`/`main.py`에 Context 이름을 하드코딩하지 않는다."""

from __future__ import annotations

from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.schemas.question import FinalizedOption
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

_SHARED_ALLOWED_CONTEXT_IDS: list[str] = sorted(ALL_BATCH_CONTEXT_IDS)
# base_question.context는 스키마상 allowed_context_ids 중 하나여야 한다(단일 고정값 —
# 실제 서빙 시 LLM 경로는 항상 실제 선택된 Context로 다시 쓰고, Fallback 경로에서만
# main.py가 이 자리표시자를 실제 current_context로 덮어쓴다).
_PLACEHOLDER_CONTEXT_ID: str = _SHARED_ALLOWED_CONTEXT_IDS[0]


def _to_shared_copy(original: V2DirectProbeBlueprint) -> V2DirectProbeBlueprint:
    new_blueprint_id = f"pack_shared_{original.blueprint_id}"
    new_question_id = f"pack_shared_{original.base_question.question_id}"

    new_options = [
        FinalizedOption(
            option_id=f"{new_question_id}_o{i}", role_id=o.role_id, text=o.text,
            primary_trait_delta=o.primary_trait_delta,
        )
        for i, o in enumerate(original.base_question.options, start=1)
    ]
    new_base_question = original.base_question.model_copy(
        update={"question_id": new_question_id, "context": _PLACEHOLDER_CONTEXT_ID, "options": new_options}
    )
    return original.model_copy(
        update={
            "blueprint_id": new_blueprint_id,
            "allowed_context_ids": list(_SHARED_ALLOWED_CONTEXT_IDS),
            "base_question": new_base_question,
            "review_status": "draft",
        }
    )


CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS: list[V2DirectProbeBlueprint] = [
    _to_shared_copy(b) for b in V2_DIRECT_PROBE_BLUEPRINTS
]

CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS_BY_ID: dict[str, V2DirectProbeBlueprint] = {
    b.blueprint_id: b for b in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
}


def _validate_shared_pool_uniqueness() -> None:
    blueprint_ids = [b.blueprint_id for b in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS]
    if len(blueprint_ids) != len(set(blueprint_ids)):
        raise ValueError(f"ContextPack 공용 Adaptive Probe blueprint_id 중복: {blueprint_ids}")
    question_ids = [b.base_question.question_id for b in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS]
    if len(question_ids) != len(set(question_ids)):
        raise ValueError(f"ContextPack 공용 Adaptive Probe question_id 중복: {question_ids}")
    option_ids = [
        o.option_id for b in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS for o in b.base_question.options
    ]
    if len(option_ids) != len(set(option_ids)):
        raise ValueError("ContextPack 공용 Adaptive Probe option_id 중복")
    # 원본 14개와도 전역적으로 겹치면 안 된다(Legacy Direct Probe Registry와의 충돌 방지).
    original_ids = {b.blueprint_id for b in V2_DIRECT_PROBE_BLUEPRINTS}
    original_question_ids = {b.base_question.question_id for b in V2_DIRECT_PROBE_BLUEPRINTS}
    if original_ids & set(blueprint_ids):
        raise ValueError("ContextPack 공용 Adaptive Probe blueprint_id가 원본 14개와 겹친다")
    if original_question_ids & set(question_ids):
        raise ValueError("ContextPack 공용 Adaptive Probe question_id가 원본 14개와 겹친다")


_validate_shared_pool_uniqueness()
