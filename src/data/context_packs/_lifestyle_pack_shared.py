"""sports/art_design/cooking/fashion_beauty Context Pack 4개가 공유하는 순수 빌더.

`_`로 시작해 Registry 자동 발견 대상이 아니다(`_example_pack_builder.py`와 같은 관례,
`context_pack_development_guide.md` §1). 이 파일은 `CONTEXT_PACK`을 노출하지 않는다.

목적은 하나뿐이다 — 네 Context 파일에서 반복되는 `FinalizedQuestion`/
`OptionMappingRationale`/`ContextAnchorPresentation`/`ContextRoutingBlueprint` 조립
보일러플레이트를 줄여서, 각 Context 파일은 실제 상황·문구·Trait Mapping 같은 콘텐츠에만
집중하게 한다. Schema 자체의 Cross-field 검증(Anchor 5개, Rationale 1:1 등)은 여전히
`src/schemas/context_pack.py`가 한다 — 이 파일은 그 검증을 통과할 입력을 조립할 뿐이다."""

from __future__ import annotations

from typing import NamedTuple

from src.ids import generate_option_id
from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.context_pack import OptionMappingRationale
from src.schemas.context_routing import ContextRoutingBlueprint, ContextRoutingOptionMapping
from src.schemas.question import FinalizedOption, FinalizedQuestion


class OptionSpec(NamedTuple):
    """선택지 하나 — `trait_id=None`이면 NO_SIGNAL. `rationale`은 왜 이 선택지가 그
    Trait(또는 NO_SIGNAL)로 연결되는지 사람이 읽을 한 문장(§9 관례:
    `anchor_backup_mapping_rationale.py`와 동일 어투)."""

    role_id: str
    text: str
    trait_id: str | None
    rationale: str


def build_question(
    *, question_id: str, context_id: str, frame_id: str, question_text: str, options: list[OptionSpec],
) -> FinalizedQuestion:
    finalized_options = [
        FinalizedOption(
            option_id=generate_option_id(question_id, i),
            role_id=spec.role_id,
            text=spec.text,
            primary_trait_delta={spec.trait_id: 1} if spec.trait_id else {},
        )
        for i, spec in enumerate(options, start=1)
    ]
    return FinalizedQuestion(
        question_id=question_id, context=context_id, target_traits=[], frame_id=frame_id,
        question_text=question_text, options=finalized_options,
    )


def build_rationales(question: FinalizedQuestion, source: str, options: list[OptionSpec]) -> list[OptionMappingRationale]:
    return [
        OptionMappingRationale(
            source=source, question_id=question.question_id, role_id=spec.role_id,
            trait_id=spec.trait_id, mapping_rationale_draft=spec.rationale,
        )
        for spec in options
    ]


class AnchorSpec(NamedTuple):
    anchor_id: str
    label: str
    situation_terms: list[str]
    preferred_scenarios: list[str]
    forbidden_assumptions: list[str]


def build_anchor_presentation(context_id: str, spec: AnchorSpec) -> ContextAnchorPresentation:
    return ContextAnchorPresentation(
        context_id=context_id, anchor_id=spec.anchor_id, label=spec.label,
        situation_terms=spec.situation_terms, preferred_scenarios=spec.preferred_scenarios,
        forbidden_assumptions=spec.forbidden_assumptions,
    )


class RoutingOptionSpec(NamedTuple):
    role_id: str
    text: str
    anchor_id: str
    anchor_label: str


def build_routing_blueprint(
    *, context_id: str, blueprint_id: str, question_id: str, question_text: str,
    options: list[RoutingOptionSpec],
) -> ContextRoutingBlueprint:
    finalized_options = [
        FinalizedOption(
            option_id=generate_option_id(question_id, i), role_id=spec.role_id, text=spec.text,
            primary_trait_delta={},
        )
        for i, spec in enumerate(options, start=1)
    ]
    base_question = FinalizedQuestion(
        question_id=question_id, context=context_id, target_traits=[], frame_id="routing",
        question_text=question_text, options=finalized_options,
    )
    return ContextRoutingBlueprint(
        context_id=context_id, blueprint_id=blueprint_id,
        option_mappings=[
            ContextRoutingOptionMapping(role_id=spec.role_id, context_anchor=spec.anchor_id, anchor_label=spec.anchor_label)
            for spec in options
        ],
        base_question=base_question,
    )
