"""ContextPack 예제 Fixture 빌더 — 2026-08-23 Trait Ontology v2(2.7단계) §3.

**이 파일은 실제 Context Pack이 아니다.** Context Pack Registry의 자동 발견은 이
디렉터리(`src/data/context_packs/`)의 모듈 중 `CONTEXT_PACK`이라는 최상위 상수를 가진
것만 골라 읽는다(`src/services/context_pack_registry.py::discover_context_packs()`
참고) — 이 파일은 그 이름을 일부러 쓰지 않아서(`build_example_context_pack()`이라는
함수만 노출) Registry가 절대 이 파일을 실제 Pack으로 집어가지 않는다.

목적은 두 가지뿐이다.
1. `ContextPack` Schema의 12개 필드·9개 Cross-field 검증 규칙이 실제로 어떻게 채워지는
   구조인지 보여주는 참고 예제(Context 제작 에이전트가 자기 Pack을 만들 때 참고).
2. 계약 테스트(`tests/test_context_pack_schema.py`)가 "정상 Pack이 통과하는지"를
   검증할 때 쓰는 재사용 가능한 Fixture.

**Context 질문 문구를 실제로 작성하는 작업이 아니다** — 선택지 문구는 전부
기계적으로 생성한 자리표시자("옵션 1 문구" 형태)이고, 실제 서비스에 노출되는 값이
아니다. `context_id="example_context"`는 `CONTEXT_DEFINITIONS`에 등록되지 않은
가짜 값이라 Registry가 실제 Context로 인식할 수 없다(등록 시점에 별도로 거부된다)."""

from __future__ import annotations

from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.context_pack import (
    ContextPack,
    ContextPackAnchorBackupQuestion,
    ContextPackSeedAnchorQuestion,
    OptionMappingRationale,
)
from src.schemas.context_routing import ContextRoutingBlueprint, ContextRoutingOptionMapping
from src.schemas.question import FinalizedOption, FinalizedQuestion

EXAMPLE_ANCHOR_IDS = ["anchor_a", "anchor_b", "anchor_c", "anchor_d", "anchor_e"]
# 예제이므로 24개 Ontology에 실제로 존재하는 Trait 2개만 쓴다(Registry 계층의 Ontology
# 존재 검증까지 통과하는 예제를 보여주기 위함 — Schema 계층 자체는 이 값을 모른다).
EXAMPLE_TRAIT_IDS = ["causal_analysis", "pattern_finding"]


def _finalized_question(question_id: str, context_id: str, frame_id: str, target_trait_id: str) -> FinalizedQuestion:
    options = []
    for i in range(1, 6):
        role_id = f"role_{i}"
        # 5개 중 1개만 target_trait_id를 PRIMARY로, 1개는 NO_SIGNAL, 나머지는 다른 예제
        # Trait로 — 실제 Pack의 "Option 5개, PRIMARY/NO_SIGNAL 혼합" 구조를 보여준다.
        if i == 1:
            delta = {target_trait_id: 1}
        elif i == 2:
            delta = {}  # NO_SIGNAL
        else:
            other_trait = next(t for t in EXAMPLE_TRAIT_IDS if t != target_trait_id)
            delta = {other_trait: 1}
        options.append(
            FinalizedOption(
                option_id=f"{question_id}_o{i}", role_id=role_id, text=f"{question_id} 옵션 {i} 문구",
                primary_trait_delta=delta,
            )
        )
    return FinalizedQuestion(
        question_id=question_id, context=context_id, target_traits=[], frame_id=frame_id,
        question_text=f"{question_id} 예제 질문 문구", options=options,
    )


def _rationales_for(question: FinalizedQuestion, source: str) -> list[OptionMappingRationale]:
    rationales = []
    for option in question.options:
        trait_id = next(iter(option.primary_trait_delta), None)
        rationales.append(
            OptionMappingRationale(
                source=source, question_id=question.question_id, role_id=option.role_id, trait_id=trait_id,
                mapping_rationale_draft=(
                    f"{option.role_id} 선택이 {trait_id} 후보로 연결된다(예제)"
                    if trait_id else f"{option.role_id}은 예제상 NO_SIGNAL이다"
                ),
            )
        )
    return rationales


def build_example_context_pack(context_id: str = "example_context") -> ContextPack:
    anchor_presentations = [
        ContextAnchorPresentation(
            context_id=context_id, anchor_id=anchor_id, label=f"{anchor_id} 라벨",
            situation_terms=["예제"], preferred_scenarios=["예제 상황"], forbidden_assumptions=[],
        )
        for anchor_id in EXAMPLE_ANCHOR_IDS
    ]

    routing_options = [
        FinalizedOption(
            option_id=f"{context_id}_routing_o{i+1}", role_id=f"routing_role_{i+1}", text=f"라우팅 옵션 {i+1}",
            primary_trait_delta={},
        )
        for i, _ in enumerate(EXAMPLE_ANCHOR_IDS)
    ]
    routing_blueprint = ContextRoutingBlueprint(
        context_id=context_id, blueprint_id=f"{context_id}_routing_blueprint",
        option_mappings=[
            ContextRoutingOptionMapping(
                role_id=routing_options[i].role_id, context_anchor=anchor_id, anchor_label=f"{anchor_id} 라벨",
            )
            for i, anchor_id in enumerate(EXAMPLE_ANCHOR_IDS)
        ],
        base_question=FinalizedQuestion(
            question_id=f"{context_id}_routing_question", context=context_id, target_traits=[],
            frame_id="routing", question_text="라우팅 예제 질문", options=routing_options,
        ),
    )

    seed_variants = []
    backup_questions = []
    rationales: list[OptionMappingRationale] = []
    for i, anchor_id in enumerate(EXAMPLE_ANCHOR_IDS):
        target_trait_id = EXAMPLE_TRAIT_IDS[i % len(EXAMPLE_TRAIT_IDS)]
        seed_question = _finalized_question(f"{context_id}_seed_{anchor_id}", context_id, "seed_frame", target_trait_id)
        backup_question = _finalized_question(f"{context_id}_backup_{anchor_id}", context_id, "backup", target_trait_id)
        seed_variants.append(ContextPackSeedAnchorQuestion(anchor_id=anchor_id, question=seed_question))
        backup_questions.append(ContextPackAnchorBackupQuestion(anchor_id=anchor_id, question=backup_question))
        rationales.extend(_rationales_for(seed_question, "seed_anchor"))
        rationales.extend(_rationales_for(backup_question, "anchor_backup"))

    return ContextPack(
        context_id=context_id, routing_blueprint=routing_blueprint, anchor_presentations=anchor_presentations,
        seed_anchor_variants=seed_variants, anchor_backup_questions=backup_questions,
        option_mapping_rationales=rationales, direct_probe_candidates=[],
        forbidden_assumptions=["예제 Context는 실제 서비스에 노출되지 않는다"],
        review_artifact_paths=[], pack_version="example_v0.1",
    )
