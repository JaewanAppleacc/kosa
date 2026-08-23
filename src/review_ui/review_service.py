"""V2 Direct Probe 검수 UI 서비스 계층 — 2026-08-23 Trait Ontology v2(2.4단계) §2/§3/§9.

Blueprint 원문(`src/data/questions/trait_v2_direct_probe_blueprints.py`)·Trait
Ontology 정본(`src/services/trait_ontology_v2.py`)·검수 상태 정본
(`data/reviews/v2_direct_probe_*_review_status.json`)을 그대로 읽어 조합한다 — 질문·
Trait의 새 복제본을 만들지 않는다. 이 모듈은 어떤 항목도 스스로 APPROVE/REVISE/HOLD로
바꾸지 않는다 — 오직 사람이 보낸 요청을 그대로 저장할 뿐이다."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from src.api.mock_data import seed_question_as_finalized
from src.data.contexts.context_anchor_presentations import (
    CONTEXT_ANCHOR_PRESENTATIONS,
    CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY,
)
from src.data.questions.anchor_backup_applicability import ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID
from src.data.questions.anchor_backup_mapping_rationale import ANCHOR_BACKUP_MAPPING_RATIONALE_BY_KEY
from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS, ANCHOR_BACKUP_QUESTIONS_BY_ID
from src.data.questions.backup_mapping_rationale import BACKUP_MAPPING_RATIONALE_BY_KEY
from src.data.questions.backup_question_applicability import BACKUP_APPLICABILITY_BY_QUESTION_ID
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS
from src.data.questions.seed_anchor_variants import SEED_ANCHOR_VARIANTS
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.engines.backup_applicability_check import check_backup_candidate
from src.engines.v2_direct_probe_quality_checks import question_level_flags, worksheet_row_flags
from src.review_ui.schemas import (
    AnchorPreviewOptionView,
    AnchorPreviewResponse,
    BackupAnchorPreviewResponse,
    BackupOptionItem,
    BackupQuestionItem,
    BackupQuestionListResponse,
    MappingSignalView,
    OptionItem,
    OptionReviewView,
    QuestionItem,
    QuestionReviewView,
    RoutingOptionItem,
    RoutingQuestionItem,
    RoutingQuestionListResponse,
    SeedAnchorOptionItem,
    SeedAnchorQuestionItem,
    SeedAnchorQuestionListResponse,
    SummaryResponse,
)
from src.schemas.v2_direct_probe_review import OptionReviewEntry, QuestionReviewEntry
from src.services.trait_ontology_v2 import load_trait_ontology_v2
from src.services.v2_direct_probe_review_store import (
    OPTION_REVIEW_PATH,
    QUESTION_REVIEW_PATH,
    load_option_review_entries,
    load_question_review_entries,
)
from src.services.context_routing_review_store import (
    ROUTING_OPTION_REVIEW_PATH,
    ROUTING_QUESTION_REVIEW_PATH,
    load_routing_option_review_entries,
    load_routing_question_review_entries,
)
from src.services.seed_anchor_review_store import (
    SEED_ANCHOR_OPTION_REVIEW_PATH,
    SEED_ANCHOR_QUESTION_REVIEW_PATH,
    load_seed_anchor_option_review_entries,
    load_seed_anchor_question_review_entries,
)
from src.services.backup_question_review_store import (
    BACKUP_OPTION_REVIEW_PATH,
    BACKUP_QUESTION_REVIEW_PATH,
    load_backup_option_review_entries,
    load_backup_question_review_entries,
)
from src.services.anchor_backup_review_store import (
    ANCHOR_BACKUP_OPTION_REVIEW_PATH,
    ANCHOR_BACKUP_QUESTION_REVIEW_PATH,
    load_anchor_backup_option_review_entries,
    load_anchor_backup_question_review_entries,
)

_CONTEXT_LABELS = {c.context_id: c.label for c in CONTEXT_DEFINITIONS}
_TRAIT_ONTOLOGY_BY_ID = {t.trait_id: t for t in load_trait_ontology_v2()}

# 2.3단계 §3(v2_direct_probe_target_length_review.md)에서 실제로 문구를 수정한 7개
# (blueprint_id, role_id) — 그 문서에 이미 적힌 수정 전/후/이유를 그대로 옮긴다. 새로운
# 판단을 추가하지 않는다 — 검수 페이지가 참고 정보로 보여주기만 한다.
LENGTH_REVIEW_HISTORY: dict[tuple[str, str], dict[str, str]] = {
    ("systems_thinking_game_v1", "st_ripple_check"): {
        "before": "이게 다른 아이템이나 전략에 어떤 영향을 주는지 같이 살펴본다",
        "after": "다른 아이템이나 전략에 어떤 영향을 주는지 살펴본다",
        "reason": "'이게'/'같이'는 의미에 기여하지 않는 군더더기 — 삭제해도 핵심 행동은 그대로다.",
    },
    ("systems_thinking_school_life_v1", "st_map_impact"): {
        "before": "이 변화가 다른 사람의 역할과 어떻게 서로 얽혀 영향을 주는지 짚어본다",
        "after": "이 변화가 다른 역할과 얽혀 영향을 주는지 짚어본다",
        "reason": "'사람의'/'서로'/'어떻게'를 정리했다. '얽혀'는 유지해 관계망(systems_thinking) 의미를 지켰다.",
    },
    ("detail_orientation_school_life_v1", "do_check_conditions"): {
        "before": "시간이 촉박해도 제출 조건을 하나하나 놓치지 않았는지 세세히 확인한다",
        "after": "촉박해도 조건을 하나하나 놓치지 않는지 확인한다",
        "reason": "'시간이'/'제출'/'세세히'는 중복 표현이었다. '하나하나 놓치지 않는지'(핵심)와 '촉박해도'(Trade-off)는 유지했다.",
    },
    ("persistence_completion_game_v1", "pc_keep_going"): {
        "before": "결과가 잘 안 나오고 다른 목표를 시작할 시간이 늦어져도, 지금 목표는 그대로 두고 끝까지 시도를 이어간다",
        "after": "잘 안 나와도 다른 목표로 넘어가지 않고 끝까지 이어간다",
        "reason": "Trade-off 절이 장황했다 — 같은 기회비용을 더 짧게 표현했다. '같은 목표를 유지'하는 핵심은 그대로다.",
    },
    ("persistence_completion_school_life_v1", "pc_finish_through"): {
        "before": "다른 일에 쓸 시간이 줄어들어도, 지루한 과제를 끝까지 마무리하는 데 가장 오래 매달린다",
        "after": "시간이 걸려도 과제를 끝까지 마무리하는 데 가장 오래 매달린다",
        "reason": "Trade-off 절을 '시간이 걸려도'로 압축했다.",
    },
    ("opinion_expression_media_v1", "oe_state_view"): {
        "before": "분위기가 어색해질 수 있어도 내 생각을 먼저 분명하게 말한다",
        "after": "분위기가 어색해져도 내 생각을 먼저 분명하게 말한다",
        "reason": "'질 수 있어도'→'져도'로 축약. 의미·Trade-off 동일.",
    },
    ("creative_ideation_game_v1", "ci_invent_rule"): {
        "before": "여러 요소를 새롭게 엮어서 지금까지와 다른 방식을 스스로 만들어본다",
        "after": "여러 요소를 새롭게 엮어서 다른 방식을 스스로 만들어본다",
        "reason": "'지금까지와'를 삭제해도 '다른 방식'이 이미 차별성을 전달한다.",
    },
}


class ReviewServiceError(Exception):
    """검수 UI 서비스 계층에서 발생하는 오류의 공통 기반 클래스."""


class UnknownBlueprintError(ReviewServiceError):
    pass


class UnknownRoleError(ReviewServiceError):
    pass


class InvalidReviewStatusError(ReviewServiceError):
    pass


class UnknownAnchorError(ReviewServiceError):
    """2.5.1단계 §11 — Preview 요청의 (context_id, anchor_id)가 실제 Anchor Presentation
    레지스트리에 없을 때."""


class StaleRevisionError(ReviewServiceError):
    """§9: 낙관적 잠금 실패 — 호출자가 오래된 revision으로 저장을 시도했다."""


def _file_revision(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _blueprint_by_id(blueprint_id: str):
    for bp in V2_DIRECT_PROBE_BLUEPRINTS:
        if bp.blueprint_id == blueprint_id:
            return bp
    raise UnknownBlueprintError(f"blueprint_id {blueprint_id!r}가 존재하지 않는다")


def _question_review_view(entry: QuestionReviewEntry) -> QuestionReviewView:
    return QuestionReviewView(
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        final_status=entry.final_status, resolution_note=entry.resolution_note,
    )


def _option_review_view(entry: OptionReviewEntry) -> OptionReviewView:
    return OptionReviewView(
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        final_status=entry.final_status, resolution_note=entry.resolution_note,
    )


def build_question_list(
    *, question_path: Path = QUESTION_REVIEW_PATH, option_path: Path = OPTION_REVIEW_PATH,
) -> tuple[list[QuestionItem], str, str]:
    """14개 질문 × 5개 선택지를 실제 Blueprint·Ontology·검수 상태에서 조합한다.
    반환값은 (질문 목록, 질문 파일 revision, 선택지 파일 revision)이다."""

    question_reviews = {e.blueprint_id: e for e in load_question_review_entries(question_path)}
    option_reviews = {(e.blueprint_id, e.role_id): e for e in load_option_review_entries(option_path)}

    questions: list[QuestionItem] = []
    for bp in V2_DIRECT_PROBE_BLUEPRINTS:
        trait = _TRAIT_ONTOLOGY_BY_ID.get(bp.trait_id)
        auto_flags = question_level_flags(bp)
        has_no_signal = any(m.mapping_type == "NO_SIGNAL" for m in bp.option_mappings)
        has_length_history = any(
            (bp.blueprint_id, m.role_id) in LENGTH_REVIEW_HISTORY for m in bp.option_mappings
        )

        options: list[OptionItem] = []
        for i, option in enumerate(bp.base_question.options, start=1):
            mapping = bp.mapping_by_role(option.role_id)
            is_target = mapping.mapping_type == "TRAIT_SIGNAL" and mapping.primary_trait_id == bp.trait_id
            row_flags = worksheet_row_flags(bp, option)
            length_outlier = "Target Option 문장이 김(구체성 편중 검토)" in row_flags or any(
                "길이" in f for f in row_flags
            )
            history = LENGTH_REVIEW_HISTORY.get((bp.blueprint_id, option.role_id))
            option_review = option_reviews.get((bp.blueprint_id, option.role_id))
            if option_review is None:
                raise UnknownRoleError(
                    f"{bp.blueprint_id}/{option.role_id}: 검수 상태 파일에 항목이 없다 — "
                    "data/reviews/v2_direct_probe_option_review_status.json을 확인하라"
                )
            options.append(OptionItem(
                role_id=option.role_id, text=option.text, length=len(option.text), display_order=i,
                mapping_type=mapping.mapping_type, is_target=is_target,
                signals=[
                    MappingSignalView(trait_id=s.trait_id, signal_role=s.signal_role, weight=s.weight)
                    for s in mapping.trait_signals
                ],
                no_signal_reason=mapping.no_signal_reason,
                quality_flags=row_flags,
                length_outlier=length_outlier,
                length_review_before=history["before"] if history else None,
                length_review_after=history["after"] if history else None,
                length_review_reason=history["reason"] if history else None,
                review=_option_review_view(option_review),
            ))

        question_review = question_reviews.get(bp.blueprint_id)
        if question_review is None:
            raise UnknownBlueprintError(
                f"{bp.blueprint_id}: 검수 상태 파일에 항목이 없다 — "
                "data/reviews/v2_direct_probe_question_review_status.json을 확인하라"
            )

        questions.append(QuestionItem(
            blueprint_id=bp.blueprint_id, context_id=bp.base_question.context,
            context_label=_CONTEXT_LABELS.get(bp.base_question.context, bp.base_question.context),
            frame_id=bp.question_frame_id, question_text=bp.base_question.question_text,
            trait_id=bp.trait_id,
            trait_label=trait.label if trait else bp.trait_id,
            trait_definition=trait.definition if trait else "",
            neighboring_trait_ids=list(trait.neighboring_trait_ids) if trait else [],
            distinction_notes=trait.distinction_notes if trait else "",
            question_quality_flags=auto_flags,
            has_no_signal_option=has_no_signal,
            has_length_review_history=has_length_history,
            options=options,
            review=_question_review_view(question_review),
        ))

    return questions, _file_revision(question_path), _file_revision(option_path)


def build_routing_question_list(
    *,
    question_path: Path = ROUTING_QUESTION_REVIEW_PATH,
    option_path: Path = ROUTING_OPTION_REVIEW_PATH,
) -> RoutingQuestionListResponse:
    """2.5단계 §10 — Context Routing 질문 3개 × 선택지 5개를 조합한다. v2 Direct
    Probe와 달리 Trait Ontology를 전혀 참조하지 않는다 — Routing 질문은 애초에 Trait를
    측정하지 않으므로 보여줄 Mapping이 없다. `trait_signal_free`는
    `ContextRoutingBlueprint`의 model_validator가 이미 구조적으로 강제한 사실을 그대로
    다시 확인해서 보여주는 것뿐이다(이 함수가 새로 판단하지 않는다)."""

    question_reviews = {e.blueprint_id: e for e in load_routing_question_review_entries(question_path)}
    option_reviews = {(e.blueprint_id, e.role_id): e for e in load_routing_option_review_entries(option_path)}

    questions: list[RoutingQuestionItem] = []
    for bp in CONTEXT_ROUTING_BLUEPRINTS:
        anchors = [m.context_anchor for m in bp.option_mappings]
        options: list[RoutingOptionItem] = []
        for i, option in enumerate(bp.base_question.options, start=1):
            mapping = next(m for m in bp.option_mappings if m.role_id == option.role_id)
            option_review = option_reviews.get((bp.blueprint_id, option.role_id))
            if option_review is None:
                raise UnknownRoleError(
                    f"{bp.blueprint_id}/{option.role_id}: Routing 검수 상태 파일에 항목이 없다 — "
                    "data/reviews/v2_context_routing_option_review_status.json을 확인하라"
                )
            options.append(RoutingOptionItem(
                role_id=option.role_id, text=option.text, display_order=i,
                context_anchor=mapping.context_anchor, anchor_label=mapping.anchor_label,
                review=_option_review_view(option_review),
            ))

        question_review = question_reviews.get(bp.blueprint_id)
        if question_review is None:
            raise UnknownBlueprintError(
                f"{bp.blueprint_id}: Routing 검수 상태 파일에 항목이 없다 — "
                "data/reviews/v2_context_routing_question_review_status.json을 확인하라"
            )

        # 구조적 보장 재확인 — primary_trait_delta는 model_validator가 이미 {}로
        # 강제했다(생성 시점에 실패했다면 이 코드에 도달하지도 못한다).
        trait_signal_free = all(o.primary_trait_delta == {} for o in bp.base_question.options)

        questions.append(RoutingQuestionItem(
            blueprint_id=bp.blueprint_id, context_id=bp.context_id,
            context_label=_CONTEXT_LABELS.get(bp.context_id, bp.context_id),
            question_text=bp.base_question.question_text,
            trait_signal_free=trait_signal_free,
            distinct_anchor_count=len(set(anchors)), total_anchor_count=len(anchors),
            options=options,
            review=_question_review_view(question_review),
        ))

    return RoutingQuestionListResponse(
        questions=questions,
        question_review_revision=_file_revision(question_path),
        option_review_revision=_file_revision(option_path),
    )


def build_anchor_preview(context_id: str, anchor_id: str) -> AnchorPreviewResponse:
    """2.5.1단계 §11 — Routing 질문에서 Anchor 하나를 고르면 실제로 나오는 첫 후속
    질문을 그대로 보여준다. `seed_question_as_finalized()`를 직접 호출한다 — 실제
    Runtime(`src/api/main.py`)이 Seed를 낼 때 쓰는 바로 그 함수이고, UI 전용 가짜
    질문을 별도로 만들지 않는다(§11 요구사항)."""

    presentation = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY.get((context_id, anchor_id))
    if presentation is None:
        raise UnknownAnchorError(f"({context_id}, {anchor_id})가 Anchor Presentation 레지스트리에 없다")
    if context_id not in VERTICAL_SLICE_SEED_QUESTIONS:
        raise UnknownAnchorError(f"{context_id}: Seed Question이 없어 Preview를 만들 수 없다")

    seed = VERTICAL_SLICE_SEED_QUESTIONS[context_id]
    finalized = seed_question_as_finalized(seed, anchor_id=anchor_id)

    return AnchorPreviewResponse(
        context_id=context_id, anchor_id=anchor_id, anchor_label=presentation.label,
        preferred_scenarios=presentation.preferred_scenarios,
        forbidden_assumptions=presentation.forbidden_assumptions,
        preview_question_text=finalized.question_text,
        preview_options=[
            AnchorPreviewOptionView(role_id=o.role_id, text=o.text, primary_trait_delta=o.primary_trait_delta)
            for o in finalized.options
        ],
    )


def build_seed_anchor_question_list(
    *,
    question_path: Path = SEED_ANCHOR_QUESTION_REVIEW_PATH,
    option_path: Path = SEED_ANCHOR_OPTION_REVIEW_PATH,
) -> SeedAnchorQuestionListResponse:
    """2.5.2단계 §12 — Seed Anchor Variant 질문 15개 × 선택지 5개를 조합한다. Trait
    Mapping은 원본 Seed Question(`VERTICAL_SLICE_SEED_QUESTIONS`)이 그대로 소유하고
    있으므로, 여기서는 role_id로 그 원본을 찾아 trait_id/primary_trait_delta/중립
    문구(neutral_text)를 그대로 옮겨 붙이기만 한다 — 새로 계산하지 않는다."""

    question_reviews = {
        (e.context_id, e.anchor_id): e for e in load_seed_anchor_question_review_entries(question_path)
    }
    option_reviews = {
        (e.context_id, e.anchor_id, e.role_id): e for e in load_seed_anchor_option_review_entries(option_path)
    }

    questions: list[SeedAnchorQuestionItem] = []
    for variant in SEED_ANCHOR_VARIANTS:
        seed = VERTICAL_SLICE_SEED_QUESTIONS[variant.context_id]
        neutral_option_by_role = {o.role_id: o for o in seed.options}
        presentation = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY[(variant.context_id, variant.anchor_id)]

        options: list[SeedAnchorOptionItem] = []
        for role_id, text in variant.option_text_by_role_id.items():
            neutral_option = neutral_option_by_role[role_id]
            trait_id = next(iter(neutral_option.primary_trait_delta))
            trait = _TRAIT_ONTOLOGY_BY_ID.get(trait_id)
            option_review = option_reviews.get((variant.context_id, variant.anchor_id, role_id))
            if option_review is None:
                raise UnknownRoleError(
                    f"{variant.context_id}/{variant.anchor_id}/{role_id}: Seed Anchor 검수 상태 파일에 항목이 없다 — "
                    "data/reviews/v2_seed_anchor_option_review_status.json을 확인하라"
                )
            options.append(SeedAnchorOptionItem(
                role_id=role_id, text=text, neutral_text=neutral_option.text,
                primary_trait_delta=neutral_option.primary_trait_delta, trait_id=trait_id,
                trait_label=trait.label if trait else trait_id,
                trait_definition=trait.definition if trait else "",
                mapping_rationale_draft=variant.option_mapping_rationale_draft[role_id],
                review=_option_review_view(option_review),
            ))

        question_review = question_reviews.get((variant.context_id, variant.anchor_id))
        if question_review is None:
            raise UnknownBlueprintError(
                f"{variant.context_id}/{variant.anchor_id}: Seed Anchor 검수 상태 파일에 항목이 없다 — "
                "data/reviews/v2_seed_anchor_question_review_status.json을 확인하라"
            )

        questions.append(SeedAnchorQuestionItem(
            context_id=variant.context_id, context_label=_CONTEXT_LABELS.get(variant.context_id, variant.context_id),
            anchor_id=variant.anchor_id, anchor_label=presentation.label,
            question_text=variant.question_text, neutral_question_text=seed.question_text,
            options=options,
            review=_question_review_view(question_review),
        ))

    return SeedAnchorQuestionListResponse(
        questions=questions,
        question_review_revision=_file_revision(question_path),
        option_review_revision=_file_revision(option_path),
    )


def build_backup_question_list(
    *,
    question_path: Path = BACKUP_QUESTION_REVIEW_PATH,
    option_path: Path = BACKUP_OPTION_REVIEW_PATH,
) -> BackupQuestionListResponse:
    """2.5.3단계 §11 — Backup 질문 6개 × 선택지 5개를 조합한다. `anchor_gate_results`는
    `check_backup_candidate()`(실제 `_use_backup()`이 쓰는 바로 그 함수)를 이 Backup이
    속한 Context의 모든 Anchor + "neutral"(Anchor 없음)에 대해 실제로 호출한 결과다."""

    question_reviews = {e.blueprint_id: e for e in load_backup_question_review_entries(question_path)}
    option_reviews = {(e.blueprint_id, e.role_id): e for e in load_backup_option_review_entries(option_path)}

    questions: list[BackupQuestionItem] = []
    for context_id, backups in VERTICAL_SLICE_BACKUP_QUESTIONS.items():
        context_anchors = [p for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id]
        for backup in backups:
            applicability = BACKUP_APPLICABILITY_BY_QUESTION_ID.get(backup.question_id)

            options: list[BackupOptionItem] = []
            for option in backup.options:
                trait_id = next(iter(option.primary_trait_delta))
                trait = _TRAIT_ONTOLOGY_BY_ID.get(trait_id)
                rationale = BACKUP_MAPPING_RATIONALE_BY_KEY.get((backup.question_id, option.role_id))
                option_review = option_reviews.get((backup.question_id, option.role_id))
                if option_review is None:
                    raise UnknownRoleError(
                        f"{backup.question_id}/{option.role_id}: Backup 검수 상태 파일에 항목이 없다 — "
                        "data/reviews/v2_backup_option_review_status.json을 확인하라"
                    )
                options.append(BackupOptionItem(
                    role_id=option.role_id, text=option.text, primary_trait_delta=option.primary_trait_delta,
                    trait_id=trait_id, trait_label=trait.label if trait else trait_id,
                    trait_definition=trait.definition if trait else "",
                    mapping_rationale_draft=rationale.mapping_rationale_draft if rationale else "",
                    review=_option_review_view(option_review),
                ))

            anchor_gate_results: dict[str, bool] = {
                "neutral": check_backup_candidate(backup, anchor=None, applicability=applicability).passed,
            }
            for anchor in context_anchors:
                anchor_gate_results[anchor.anchor_id] = check_backup_candidate(
                    backup, anchor=anchor, applicability=applicability,
                ).passed

            question_review = question_reviews.get(backup.question_id)
            if question_review is None:
                raise UnknownBlueprintError(
                    f"{backup.question_id}: Backup 검수 상태 파일에 항목이 없다 — "
                    "data/reviews/v2_backup_question_review_status.json을 확인하라"
                )

            questions.append(BackupQuestionItem(
                question_id=backup.question_id, context_id=context_id,
                context_label=_CONTEXT_LABELS.get(context_id, context_id),
                question_text=backup.question_text, options=options,
                allowed_anchor_ids=(
                    sorted(applicability.allowed_anchor_ids) if applicability and applicability.allowed_anchor_ids
                    else None
                ),
                excluded_anchor_ids=sorted(applicability.excluded_anchor_ids) if applicability else [],
                applicability_reason_draft=applicability.applicability_reason_draft if applicability else "",
                anchor_gate_results=anchor_gate_results,
                review=_question_review_view(question_review),
            ))

    return BackupQuestionListResponse(
        questions=questions,
        question_review_revision=_file_revision(question_path),
        option_review_revision=_file_revision(option_path),
    )


def build_backup_anchor_preview(question_id: str, context_id: str, anchor_id: str | None) -> BackupAnchorPreviewResponse:
    """2.5.3단계 §11/§14 — 검수 UI가 부르는 Preview. `check_backup_candidate()`를 그대로
    호출한다 — Runtime의 `_use_backup()`과 동일한 판정 로직이다."""

    backups = VERTICAL_SLICE_BACKUP_QUESTIONS.get(context_id, [])
    backup = next((b for b in backups if b.question_id == question_id), None)
    if backup is None:
        raise UnknownBlueprintError(f"{context_id}/{question_id}: 실제 Backup Question 목록에 없다")

    anchor = None
    if anchor_id is not None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY.get((context_id, anchor_id))
        if anchor is None:
            raise UnknownAnchorError(f"({context_id}, {anchor_id})가 Anchor Presentation 레지스트리에 없다")

    applicability = BACKUP_APPLICABILITY_BY_QUESTION_ID.get(question_id)
    gate = check_backup_candidate(backup, anchor=anchor, applicability=applicability)
    return BackupAnchorPreviewResponse(
        question_id=question_id, anchor_id=anchor_id, passed=gate.passed, failures=gate.failures,
    )


def build_anchor_backup_question_list(
    *,
    question_path: Path = ANCHOR_BACKUP_QUESTION_REVIEW_PATH,
    option_path: Path = ANCHOR_BACKUP_OPTION_REVIEW_PATH,
) -> BackupQuestionListResponse:
    """2.5.4단계 §7 — Anchor Backup 질문 15개 × 선택지 5개를 조합한다. 기존(2.5.3단계)
    6개 Backup과 같은 View 모델(`BackupQuestionItem`)을 재사용하지만, 완전히 별도의
    검토 상태 파일을 읽는다 — 사용자가 이미 REVISE 판정한 기존 파일은 절대 건드리지
    않는다. `superseded_question_ids`는 이 Anchor Backup이 대체하는(그리고 v2 Anchor
    Runtime 후보에서 제외된) 그 Context의 기존 REVISE Backup question_id 목록이다."""

    question_reviews = {e.blueprint_id: e for e in load_anchor_backup_question_review_entries(question_path)}
    option_reviews = {
        (e.blueprint_id, e.role_id): e for e in load_anchor_backup_option_review_entries(option_path)
    }

    questions: list[BackupQuestionItem] = []
    for question in ANCHOR_BACKUP_QUESTIONS:
        context_id = question.context
        context_anchors = [p for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id]
        applicability = ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID.get(question.question_id)
        superseded_ids = [q.question_id for q in VERTICAL_SLICE_BACKUP_QUESTIONS.get(context_id, [])]

        options: list[BackupOptionItem] = []
        for option in question.options:
            trait_id = next(iter(option.primary_trait_delta), None)
            trait = _TRAIT_ONTOLOGY_BY_ID.get(trait_id) if trait_id else None
            rationale = ANCHOR_BACKUP_MAPPING_RATIONALE_BY_KEY.get((question.question_id, option.role_id))
            option_review = option_reviews.get((question.question_id, option.role_id))
            if option_review is None:
                raise UnknownRoleError(
                    f"{question.question_id}/{option.role_id}: Anchor Backup 검수 상태 파일에 항목이 없다 — "
                    "data/reviews/v2_anchor_backup_option_review_status.json을 확인하라"
                )
            options.append(BackupOptionItem(
                role_id=option.role_id, text=option.text, primary_trait_delta=option.primary_trait_delta,
                trait_id=trait_id, trait_label=(trait.label if trait else "NO_SIGNAL"),
                trait_definition=trait.definition if trait else "",
                mapping_rationale_draft=rationale.mapping_rationale_draft if rationale else "",
                review=_option_review_view(option_review),
            ))

        anchor_gate_results: dict[str, bool] = {
            "neutral": check_backup_candidate(question, anchor=None, applicability=applicability).passed,
        }
        for anchor in context_anchors:
            anchor_gate_results[anchor.anchor_id] = check_backup_candidate(
                question, anchor=anchor, applicability=applicability,
            ).passed

        question_review = question_reviews.get(question.question_id)
        if question_review is None:
            raise UnknownBlueprintError(
                f"{question.question_id}: Anchor Backup 검수 상태 파일에 항목이 없다 — "
                "data/reviews/v2_anchor_backup_question_review_status.json을 확인하라"
            )

        questions.append(BackupQuestionItem(
            question_id=question.question_id, context_id=context_id,
            context_label=_CONTEXT_LABELS.get(context_id, context_id),
            question_text=question.question_text, options=options,
            allowed_anchor_ids=(
                sorted(applicability.allowed_anchor_ids) if applicability and applicability.allowed_anchor_ids
                else None
            ),
            excluded_anchor_ids=sorted(applicability.excluded_anchor_ids) if applicability else [],
            applicability_reason_draft=applicability.applicability_reason_draft if applicability else "",
            anchor_gate_results=anchor_gate_results,
            review=_question_review_view(question_review),
            superseded_question_ids=superseded_ids,
        ))

    return BackupQuestionListResponse(
        questions=questions,
        question_review_revision=_file_revision(question_path),
        option_review_revision=_file_revision(option_path),
    )


def build_anchor_backup_anchor_preview(
    question_id: str, context_id: str, anchor_id: str | None,
) -> BackupAnchorPreviewResponse:
    question = ANCHOR_BACKUP_QUESTIONS_BY_ID.get(question_id)
    if question is None or question.context != context_id:
        raise UnknownBlueprintError(f"{context_id}/{question_id}: 실제 Anchor Backup Question 목록에 없다")

    anchor = None
    if anchor_id is not None:
        anchor = CONTEXT_ANCHOR_PRESENTATIONS_BY_KEY.get((context_id, anchor_id))
        if anchor is None:
            raise UnknownAnchorError(f"({context_id}, {anchor_id})가 Anchor Presentation 레지스트리에 없다")

    applicability = ANCHOR_BACKUP_APPLICABILITY_BY_QUESTION_ID.get(question_id)
    gate = check_backup_candidate(question, anchor=anchor, applicability=applicability)
    return BackupAnchorPreviewResponse(
        question_id=question_id, anchor_id=anchor_id, passed=gate.passed, failures=gate.failures,
    )


def build_summary(
    *, question_path: Path = QUESTION_REVIEW_PATH, option_path: Path = OPTION_REVIEW_PATH,
) -> SummaryResponse:
    questions, q_rev, o_rev = build_question_list(question_path=question_path, option_path=option_path)

    q_status_counts: dict[str, int] = {"APPROVE": 0, "REVISE": 0, "HOLD": 0, "TBD": 0}
    o_status_counts: dict[str, int] = {"APPROVE": 0, "REVISE": 0, "HOLD": 0, "TBD": 0}
    approved_eligible: list[str] = []
    question_reviewed_final = 0
    option_reviewed_final = 0
    option_total = 0

    for q in questions:
        # reviewer_1/reviewer_2 각각 집계(질문 하나가 두 표에 반영됨 — "슬롯별 분포").
        # 2.5.5단계: 이 집계 자체는 참고용 분포이며, final_status 계산에는 reviewer_1만
        # 쓰인다(reviewer_2 집계는 과거 데이터 호환을 위한 참고 표시일 뿐이다).
        for status in (q.review.reviewer_1_status, q.review.reviewer_2_status):
            q_status_counts[status] = q_status_counts.get(status, 0) + 1
        if q.review.final_status != "DRAFT":
            question_reviewed_final += 1

        all_options_approved = True
        for opt in q.options:
            option_total += 1
            for status in (opt.review.reviewer_1_status, opt.review.reviewer_2_status):
                o_status_counts[status] = o_status_counts.get(status, 0) + 1
            if opt.review.final_status != "DRAFT":
                option_reviewed_final += 1
            if opt.review.final_status != "APPROVED":
                all_options_approved = False

        if q.review.final_status == "APPROVED" and all_options_approved:
            approved_eligible.append(q.blueprint_id)

    return SummaryResponse(
        question_total=len(questions), question_reviewed_final=question_reviewed_final,
        question_status_counts=q_status_counts,
        option_total=option_total, option_reviewed_final=option_reviewed_final,
        option_status_counts=o_status_counts,
        approved_eligible_blueprint_ids=approved_eligible,
        question_review_revision=q_rev, option_review_revision=o_rev,
    )


_VALID_STATUSES = {"APPROVE", "REVISE", "HOLD", "TBD"}
_KNOWN_BLUEPRINT_IDS = {b.blueprint_id for b in V2_DIRECT_PROBE_BLUEPRINTS}
_KNOWN_OPTION_KEYS = {(b.blueprint_id, m.role_id) for b in V2_DIRECT_PROBE_BLUEPRINTS for m in b.option_mappings}


def _atomic_write_json(path: Path, payload: list[dict]) -> None:
    """§9 저장 순서의 마지막 두 단계 — 임시 파일에 기록한 뒤 성공 시 os.replace로
    원자적으로 교체한다. 중간에 실패해도 원본 파일은 그대로 남는다."""

    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)
        raise


def update_question_review(
    *, blueprint_id: str, reviewer: str, status: str, comment: str, resolution_note: str | None,
    expected_revision: str, question_path: Path = QUESTION_REVIEW_PATH,
) -> tuple[str, str]:
    """§9 저장 순서를 그대로 따른다: Schema 검증(호출자가 이미 Pydantic으로 했다는
    전제) → blueprint_id 존재 확인 → 선택한 reviewer 슬롯의 필드만 변경 → 전체 Review
    JSON 재검증 → 임시 파일 기록 → 원자적 교체. 반환값은 (계산된 final_status, 새
    revision)이다. `final_status`는 저장하지 않는다 — 매번 다시 계산할 뿐이다."""

    if blueprint_id not in _KNOWN_BLUEPRINT_IDS:
        raise UnknownBlueprintError(f"blueprint_id {blueprint_id!r}가 실제 Blueprint 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(question_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "질문 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_question_review_entries(question_path)
    updated: list[QuestionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == blueprint_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownBlueprintError(f"blueprint_id {blueprint_id!r}가 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    # 전체 Review JSON 재검증(§9) — Pydantic으로 다시 한번 왕복시켜 구조가 깨지지
    # 않았는지 확인한다.
    from pydantic import TypeAdapter

    TypeAdapter(list[QuestionReviewEntry]).validate_python(payload)
    _atomic_write_json(question_path, payload)
    return final_status, _file_revision(question_path)


def update_option_review(
    *, blueprint_id: str, role_id: str, reviewer: str, status: str, comment: str,
    resolution_note: str | None, expected_revision: str, option_path: Path = OPTION_REVIEW_PATH,
) -> tuple[str, str]:
    if (blueprint_id, role_id) not in _KNOWN_OPTION_KEYS:
        raise UnknownRoleError(f"{blueprint_id}/{role_id}가 실제 Option 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(option_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "선택지 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_option_review_entries(option_path)
    updated: list[OptionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == blueprint_id and entry.role_id == role_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownRoleError(f"{blueprint_id}/{role_id}가 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[OptionReviewEntry]).validate_python(payload)
    _atomic_write_json(option_path, payload)
    return final_status, _file_revision(option_path)


_KNOWN_ROUTING_BLUEPRINT_IDS = {b.blueprint_id for b in CONTEXT_ROUTING_BLUEPRINTS}
_KNOWN_ROUTING_OPTION_KEYS = {
    (b.blueprint_id, m.role_id) for b in CONTEXT_ROUTING_BLUEPRINTS for m in b.option_mappings
}


def update_routing_question_review(
    *, blueprint_id: str, reviewer: str, status: str, comment: str, resolution_note: str | None,
    expected_revision: str, question_path: Path = ROUTING_QUESTION_REVIEW_PATH,
) -> tuple[str, str]:
    """§10 — v2 Direct Probe의 `update_question_review()`와 완전히 같은 저장 순서를
    Context Routing 질문에 대해 그대로 반복한다."""

    if blueprint_id not in _KNOWN_ROUTING_BLUEPRINT_IDS:
        raise UnknownBlueprintError(f"blueprint_id {blueprint_id!r}가 실제 Routing Blueprint 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(question_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Routing 질문 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_routing_question_review_entries(question_path)
    updated: list[QuestionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == blueprint_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownBlueprintError(f"blueprint_id {blueprint_id!r}가 Routing 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[QuestionReviewEntry]).validate_python(payload)
    _atomic_write_json(question_path, payload)
    return final_status, _file_revision(question_path)


def update_routing_option_review(
    *, blueprint_id: str, role_id: str, reviewer: str, status: str, comment: str,
    resolution_note: str | None, expected_revision: str, option_path: Path = ROUTING_OPTION_REVIEW_PATH,
) -> tuple[str, str]:
    if (blueprint_id, role_id) not in _KNOWN_ROUTING_OPTION_KEYS:
        raise UnknownRoleError(f"{blueprint_id}/{role_id}가 실제 Routing Option 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(option_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Routing 선택지 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_routing_option_review_entries(option_path)
    updated: list[OptionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == blueprint_id and entry.role_id == role_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownRoleError(f"{blueprint_id}/{role_id}가 Routing 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[OptionReviewEntry]).validate_python(payload)
    _atomic_write_json(option_path, payload)
    return final_status, _file_revision(option_path)


_KNOWN_SEED_ANCHOR_QUESTION_KEYS = {(v.context_id, v.anchor_id) for v in SEED_ANCHOR_VARIANTS}
_KNOWN_SEED_ANCHOR_OPTION_KEYS = {
    (v.context_id, v.anchor_id, role_id) for v in SEED_ANCHOR_VARIANTS for role_id in v.option_text_by_role_id
}


def update_seed_anchor_question_review(
    *, context_id: str, anchor_id: str, reviewer: str, status: str, comment: str, resolution_note: str | None,
    expected_revision: str, question_path: Path = SEED_ANCHOR_QUESTION_REVIEW_PATH,
) -> tuple[str, str]:
    """§11/§12 — v2 Direct Probe·Routing과 완전히 같은 저장 순서를 Seed Anchor Variant
    질문에 대해 반복한다."""

    from src.schemas.seed_anchor_review import SeedAnchorQuestionReviewEntry

    if (context_id, anchor_id) not in _KNOWN_SEED_ANCHOR_QUESTION_KEYS:
        raise UnknownBlueprintError(f"({context_id}, {anchor_id})가 실제 Seed Anchor Variant 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(question_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Seed Anchor 질문 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_seed_anchor_question_review_entries(question_path)
    updated: list[SeedAnchorQuestionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.context_id == context_id and entry.anchor_id == anchor_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownBlueprintError(f"({context_id}, {anchor_id})가 Seed Anchor 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[SeedAnchorQuestionReviewEntry]).validate_python(payload)
    _atomic_write_json(question_path, payload)
    return final_status, _file_revision(question_path)


def update_seed_anchor_option_review(
    *, context_id: str, anchor_id: str, role_id: str, reviewer: str, status: str, comment: str,
    resolution_note: str | None, expected_revision: str, option_path: Path = SEED_ANCHOR_OPTION_REVIEW_PATH,
) -> tuple[str, str]:
    from src.schemas.seed_anchor_review import SeedAnchorOptionReviewEntry

    if (context_id, anchor_id, role_id) not in _KNOWN_SEED_ANCHOR_OPTION_KEYS:
        raise UnknownRoleError(f"{context_id}/{anchor_id}/{role_id}가 실제 Seed Anchor Option 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(option_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Seed Anchor 선택지 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_seed_anchor_option_review_entries(option_path)
    updated: list[SeedAnchorOptionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.context_id == context_id and entry.anchor_id == anchor_id and entry.role_id == role_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownRoleError(f"{context_id}/{anchor_id}/{role_id}가 Seed Anchor 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[SeedAnchorOptionReviewEntry]).validate_python(payload)
    _atomic_write_json(option_path, payload)
    return final_status, _file_revision(option_path)


_KNOWN_BACKUP_QUESTION_IDS = {q.question_id for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups}
_KNOWN_BACKUP_OPTION_KEYS = {
    (q.question_id, o.role_id)
    for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values() for q in backups for o in q.options
}


def update_backup_question_review(
    *, question_id: str, reviewer: str, status: str, comment: str, resolution_note: str | None,
    expected_revision: str, question_path: Path = BACKUP_QUESTION_REVIEW_PATH,
) -> tuple[str, str]:
    """§10/§11 — v2 Direct Probe·Routing·Seed Anchor와 완전히 같은 저장 순서를 Backup
    질문에 대해 반복한다."""

    if question_id not in _KNOWN_BACKUP_QUESTION_IDS:
        raise UnknownBlueprintError(f"question_id {question_id!r}가 실제 Backup Question 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(question_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Backup 질문 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_backup_question_review_entries(question_path)
    updated: list[QuestionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == question_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownBlueprintError(f"question_id {question_id!r}가 Backup 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[QuestionReviewEntry]).validate_python(payload)
    _atomic_write_json(question_path, payload)
    return final_status, _file_revision(question_path)


def update_backup_option_review(
    *, question_id: str, role_id: str, reviewer: str, status: str, comment: str,
    resolution_note: str | None, expected_revision: str, option_path: Path = BACKUP_OPTION_REVIEW_PATH,
) -> tuple[str, str]:
    if (question_id, role_id) not in _KNOWN_BACKUP_OPTION_KEYS:
        raise UnknownRoleError(f"{question_id}/{role_id}가 실제 Backup Option 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(option_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Backup 선택지 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_backup_option_review_entries(option_path)
    updated: list[OptionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == question_id and entry.role_id == role_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownRoleError(f"{question_id}/{role_id}가 Backup 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[OptionReviewEntry]).validate_python(payload)
    _atomic_write_json(option_path, payload)
    return final_status, _file_revision(option_path)


_KNOWN_ANCHOR_BACKUP_QUESTION_IDS = {q.question_id for q in ANCHOR_BACKUP_QUESTIONS}
_KNOWN_ANCHOR_BACKUP_OPTION_KEYS = {
    (q.question_id, o.role_id) for q in ANCHOR_BACKUP_QUESTIONS for o in q.options
}


def update_anchor_backup_question_review(
    *, question_id: str, reviewer: str, status: str, comment: str, resolution_note: str | None,
    expected_revision: str, question_path: Path = ANCHOR_BACKUP_QUESTION_REVIEW_PATH,
) -> tuple[str, str]:
    """§7/§10 — 기존 Backup·v2 Direct Probe·Routing·Seed Anchor와 완전히 같은 저장
    순서를 Anchor Backup 질문에 대해 반복한다."""

    if question_id not in _KNOWN_ANCHOR_BACKUP_QUESTION_IDS:
        raise UnknownBlueprintError(f"question_id {question_id!r}가 실제 Anchor Backup Question 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(question_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Anchor Backup 질문 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_anchor_backup_question_review_entries(question_path)
    updated: list[QuestionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == question_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownBlueprintError(f"question_id {question_id!r}가 Anchor Backup 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[QuestionReviewEntry]).validate_python(payload)
    _atomic_write_json(question_path, payload)
    return final_status, _file_revision(question_path)


def update_anchor_backup_option_review(
    *, question_id: str, role_id: str, reviewer: str, status: str, comment: str,
    resolution_note: str | None, expected_revision: str, option_path: Path = ANCHOR_BACKUP_OPTION_REVIEW_PATH,
) -> tuple[str, str]:
    if (question_id, role_id) not in _KNOWN_ANCHOR_BACKUP_OPTION_KEYS:
        raise UnknownRoleError(f"{question_id}/{role_id}가 실제 Anchor Backup Option 목록에 없다")
    if status not in _VALID_STATUSES:
        raise InvalidReviewStatusError(f"status {status!r}는 APPROVE/REVISE/HOLD/TBD 중 하나여야 한다")
    if reviewer not in ("reviewer_1", "reviewer_2"):
        raise InvalidReviewStatusError(f"reviewer {reviewer!r}는 reviewer_1/reviewer_2 중 하나여야 한다")

    current_revision = _file_revision(option_path)
    if current_revision != expected_revision:
        raise StaleRevisionError(
            "Anchor Backup 선택지 검토 상태 파일이 그 사이 다른 곳에서 바뀌었다 — 최신 상태를 다시 불러온 뒤 다시 시도하라"
        )

    entries = load_anchor_backup_option_review_entries(option_path)
    updated: list[OptionReviewEntry] = []
    found = False
    final_status = "DRAFT"
    for entry in entries:
        if entry.blueprint_id == question_id and entry.role_id == role_id:
            found = True
            update: dict[str, object] = {f"{reviewer}_status": status, f"{reviewer}_comment": comment}
            if resolution_note is not None:
                update["resolution_note"] = resolution_note
            entry = entry.model_copy(update=update)
            final_status = entry.final_status
        updated.append(entry)
    if not found:
        raise UnknownRoleError(f"{question_id}/{role_id}가 Anchor Backup 검수 상태 파일에 없다")

    payload = [json.loads(e.model_dump_json()) for e in updated]
    from pydantic import TypeAdapter

    TypeAdapter(list[OptionReviewEntry]).validate_python(payload)
    _atomic_write_json(option_path, payload)
    return final_status, _file_revision(option_path)
