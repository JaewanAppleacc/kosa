"""ContextPack 검수 UI 서비스 계층 — 2026-08-23 Trait Ontology v2(2.8단계) §9. A 소유.

T·S·L이 `src/data/context_packs/`에 새 Pack 파일을 추가하기만 하면 이 모듈이 자동으로
찾아서(`ContextPackRegistry`) 검수 목록에 반영한다 — Context마다 이 파일을 고칠 필요가
없다. 실제 Runtime 변환 함수(`ContextPackRegistry`/`compute_context_trait_coverage`)를
그대로 재사용한다 — 가짜 Preview 데이터를 따로 만들지 않는다(§9 마지막 규칙).

이 모듈은 어떤 항목도 스스로 APPROVE/REVISE/HOLD로 바꾸지 않는다 — 오직 사람이 보낸
요청을 그대로 저장할 뿐이다(다른 검수 Store와 동일한 원칙)."""

from __future__ import annotations

from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.schemas.context_pack import ContextPack
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.trait import TraitDefinition
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint
from src.schemas.v2_direct_probe_review import QuestionReviewEntry
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_review_store import (
    load_context_pack_review_entries,
    save_context_pack_review_entries,
)
from src.services.context_pack_shared_probe_review_store import (
    load_shared_probe_review_entries,
    save_shared_probe_review_entries,
)
from src.services.context_trait_coverage import compute_context_trait_coverage
from src.review_ui.schemas import (
    ContextPackAnchorView,
    ContextPackCoverageView,
    ContextPackListResponse,
    ContextPackReviewItem,
    ContextPackReviewOptionView,
    ContextPackReviewQuestionView,
    QuestionReviewView,
    ReviewerStatus,
    SharedProbeListResponse,
    SharedProbeOptionView,
    SharedProbeReviewItem,
    UpdateReviewResponse,
)

_CONTEXT_LABEL_BY_ID = {c.context_id: c.label for c in CONTEXT_DEFINITIONS}
_CONTEXT_DESCRIPTION_BY_ID = {c.context_id: c.description for c in CONTEXT_DEFINITIONS}


class UnknownContextPackError(ValueError):
    pass


class UnknownReviewKeyError(ValueError):
    pass


def _review_view(entry: QuestionReviewEntry | None) -> QuestionReviewView:
    entry = entry or QuestionReviewEntry(blueprint_id="")
    return QuestionReviewView(
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        final_status=entry.final_status, resolution_note=entry.resolution_note,
    )


def _rationale_lookup(pack: ContextPack) -> dict[tuple[str, str], tuple[str | None, str]]:
    return {
        (r.question_id, r.role_id): (r.trait_id, r.mapping_rationale_draft)
        for r in pack.option_mapping_rationales
    }


def _finalized_option_view(
    option: FinalizedOption, question_id: str, rationale_lookup: dict, trait_labels: dict[str, str],
) -> ContextPackReviewOptionView:
    trait_id = next(iter(option.primary_trait_delta), None)
    _rationale_trait_id, rationale = rationale_lookup.get((question_id, option.role_id), (None, None))
    return ContextPackReviewOptionView(
        role_id=option.role_id, text=option.text,
        mapping_type="TRAIT_SIGNAL" if trait_id else "NO_SIGNAL",
        trait_id=trait_id, trait_label=trait_labels.get(trait_id) if trait_id else None,
        mapping_rationale_draft=rationale,
    )


def _direct_probe_option_views(
    probe: V2DirectProbeBlueprint, rationale_lookup: dict, trait_labels: dict[str, str],
) -> list[ContextPackReviewOptionView]:
    views = []
    for mapping in probe.option_mappings:
        text = next(
            (o.text for o in probe.base_question.options if o.role_id == mapping.role_id), "",
        )
        _rationale_trait_id, rationale = rationale_lookup.get(
            (probe.base_question.question_id, mapping.role_id), (None, None)
        )
        views.append(
            ContextPackReviewOptionView(
                role_id=mapping.role_id, text=text, mapping_type=mapping.mapping_type,
                trait_id=mapping.primary_trait_id,
                trait_label=trait_labels.get(mapping.primary_trait_id) if mapping.primary_trait_id else None,
                mapping_rationale_draft=rationale,
            )
        )
    return views


def _question_view(
    *, key: str, kind: str, anchor_id: str | None, question: FinalizedQuestion, trait_signal_free: bool,
    options: list[ContextPackReviewOptionView], review_entries_by_key: dict[str, QuestionReviewEntry],
) -> ContextPackReviewQuestionView:
    return ContextPackReviewQuestionView(
        key=key, kind=kind, anchor_id=anchor_id, question_text=question.question_text,
        trait_signal_free=trait_signal_free, options=options,
        review=_review_view(review_entries_by_key.get(key)),
    )


def build_context_pack_list(
    registry: ContextPackRegistry, trait_definitions: dict[str, TraitDefinition],
) -> ContextPackListResponse:
    trait_labels = {t.trait_id: t.label for t in trait_definitions.values()}
    items: list[ContextPackReviewItem] = []
    for pack in registry.all_packs():
        review_entries = {e.blueprint_id: e for e in load_context_pack_review_entries(pack.context_id)}
        rationale_lookup = _rationale_lookup(pack)

        questions: list[ContextPackReviewQuestionView] = []
        routing_key = f"{pack.context_id}::routing::{pack.routing_blueprint.blueprint_id}"
        questions.append(
            _question_view(
                key=routing_key, kind="routing", anchor_id=None, question=pack.routing_blueprint.base_question,
                trait_signal_free=True,
                options=[
                    ContextPackReviewOptionView(
                        role_id=o.role_id, text=o.text, mapping_type="NO_SIGNAL", trait_id=None, trait_label=None,
                        mapping_rationale_draft=None,
                    )
                    for o in pack.routing_blueprint.base_question.options
                ],
                review_entries_by_key=review_entries,
            )
        )
        for seed in pack.seed_anchor_variants:
            key = f"{pack.context_id}::seed::{seed.anchor_id}"
            questions.append(
                _question_view(
                    key=key, kind="seed", anchor_id=seed.anchor_id, question=seed.question,
                    trait_signal_free=False,
                    options=[
                        _finalized_option_view(o, seed.question.question_id, rationale_lookup, trait_labels)
                        for o in seed.question.options
                    ],
                    review_entries_by_key=review_entries,
                )
            )
        for backup in pack.anchor_backup_questions:
            key = f"{pack.context_id}::anchor_backup::{backup.anchor_id}"
            questions.append(
                _question_view(
                    key=key, kind="anchor_backup", anchor_id=backup.anchor_id, question=backup.question,
                    trait_signal_free=False,
                    options=[
                        _finalized_option_view(o, backup.question.question_id, rationale_lookup, trait_labels)
                        for o in backup.question.options
                    ],
                    review_entries_by_key=review_entries,
                )
            )
        for probe in pack.direct_probe_candidates:
            key = f"{pack.context_id}::direct_probe::{probe.blueprint_id}"
            questions.append(
                _question_view(
                    key=key, kind="direct_probe", anchor_id=None, question=probe.base_question,
                    trait_signal_free=False,
                    options=_direct_probe_option_views(probe, rationale_lookup, trait_labels),
                    review_entries_by_key=review_entries,
                )
            )

        coverage = compute_context_trait_coverage(pack, set(trait_definitions))
        items.append(
            ContextPackReviewItem(
                context_id=pack.context_id,
                label=_CONTEXT_LABEL_BY_ID.get(pack.context_id, pack.context_id),
                description=_CONTEXT_DESCRIPTION_BY_ID.get(pack.context_id, ""),
                pack_version=pack.pack_version,
                forbidden_assumptions=pack.forbidden_assumptions,
                review_artifact_paths=pack.review_artifact_paths,
                anchors=[
                    ContextPackAnchorView(
                        anchor_id=a.anchor_id, label=a.label, situation_terms=a.situation_terms,
                        preferred_scenarios=a.preferred_scenarios, forbidden_assumptions=a.forbidden_assumptions,
                    )
                    for a in pack.anchor_presentations
                ],
                questions=questions,
                coverage=ContextPackCoverageView(
                    primary_trait_ids=sorted(coverage.primary_trait_ids),
                    related_trait_ids=sorted(coverage.related_trait_ids),
                    direct_probe_trait_ids=sorted(coverage.direct_probe_trait_ids),
                    anchor_count=coverage.anchor_count, seed_question_count=coverage.seed_question_count,
                    backup_question_count=coverage.backup_question_count,
                    uncovered_trait_ids=sorted(coverage.uncovered_trait_ids),
                ),
                is_active=registry.is_pack_review_approved(pack.context_id),
                registry_errors=[],
            )
        )

    return ContextPackListResponse(
        packs=sorted(items, key=lambda i: i.context_id),
        discovery_errors=registry.discovery_errors(), ontology_errors=registry.ontology_errors(),
    )


def build_shared_probe_list(
    shared_pool: list[V2DirectProbeBlueprint], trait_definitions: dict[str, TraitDefinition],
) -> SharedProbeListResponse:
    """2026-08-23 Trait Ontology v2(2.9단계) §11 — ContextPack 공용 Adaptive Probe
    Blueprint(`context_pack_shared_probe_blueprints.py`)를 그대로 보여준다. 원본 14개
    Legacy Blueprint의 role_id·Trait Signal을 그대로 복사한 것이라 실제 Runtime
    변환과 다른 가짜 Preview가 아니다."""

    trait_labels = {t.trait_id: t.label for t in trait_definitions.values()}
    trait_defs = {t.trait_id: t.definition for t in trait_definitions.values()}
    review_entries = {e.blueprint_id: e for e in load_shared_probe_review_entries()}

    items: list[SharedProbeReviewItem] = []
    for bp in shared_pool:
        options = []
        for mapping in bp.option_mappings:
            text = next((o.text for o in bp.base_question.options if o.role_id == mapping.role_id), "")
            trait_id = mapping.primary_trait_id
            options.append(
                SharedProbeOptionView(
                    role_id=mapping.role_id, text=text, mapping_type=mapping.mapping_type,
                    trait_id=trait_id, trait_label=trait_labels.get(trait_id) if trait_id else None,
                    weight=1.0 if mapping.mapping_type == "TRAIT_SIGNAL" else None,
                )
            )
        entry = review_entries.get(bp.blueprint_id)
        items.append(
            SharedProbeReviewItem(
                blueprint_id=bp.blueprint_id, trait_id=bp.trait_id,
                trait_label=trait_labels.get(bp.trait_id, bp.trait_id),
                trait_definition=trait_defs.get(bp.trait_id, ""), purpose=bp.purpose,
                allowed_context_ids=list(bp.allowed_context_ids), question_text=bp.base_question.question_text,
                options=options, review=_review_view(entry),
                is_active=entry is not None and entry.final_status == "APPROVED",
            )
        )
    return SharedProbeListResponse(probes=sorted(items, key=lambda i: i.blueprint_id))


class UnknownSharedProbeError(ValueError):
    pass


def update_shared_probe_review(
    shared_pool: list[V2DirectProbeBlueprint], blueprint_id: str, *, status: ReviewerStatus,
    comment: str, resolution_note: str | None,
) -> UpdateReviewResponse:
    if blueprint_id not in {bp.blueprint_id for bp in shared_pool}:
        raise UnknownSharedProbeError(f"blueprint_id {blueprint_id!r}가 공용 Adaptive Probe 목록에 없다")

    entries = load_shared_probe_review_entries()
    by_id = {e.blueprint_id: e for e in entries}
    existing = by_id.get(blueprint_id) or QuestionReviewEntry(blueprint_id=blueprint_id)
    updated = existing.model_copy(
        update={
            "reviewer_1_status": status, "reviewer_1_comment": comment,
            **({"resolution_note": resolution_note} if resolution_note is not None else {}),
        }
    )
    by_id[blueprint_id] = updated
    save_shared_probe_review_entries([by_id[k] for k in sorted(by_id)])
    return UpdateReviewResponse(ok=True, final_status=updated.final_status, new_revision="")


def update_context_pack_review(
    registry: ContextPackRegistry, context_id: str, key: str, *, status: ReviewerStatus,
    comment: str, resolution_note: str | None,
) -> UpdateReviewResponse:
    pack = registry.get_pack(context_id)
    if pack is None:
        raise UnknownContextPackError(f"context_id {context_id!r}가 존재하지 않는다")
    required_keys = registry.required_review_keys(pack)
    if key not in required_keys:
        raise UnknownReviewKeyError(f"key {key!r}가 {context_id!r}의 검수 대상이 아니다")

    entries = load_context_pack_review_entries(context_id)
    by_key = {e.blueprint_id: e for e in entries}
    existing = by_key.get(key) or QuestionReviewEntry(blueprint_id=key)
    updated = existing.model_copy(
        update={
            "reviewer_1_status": status, "reviewer_1_comment": comment,
            **({"resolution_note": resolution_note} if resolution_note is not None else {}),
        }
    )
    by_key[key] = updated
    # required_review_keys 순서와 무관하게 항상 결정론적으로 정렬해서 저장한다.
    save_context_pack_review_entries(context_id, [by_key[k] for k in sorted(by_key)])
    return UpdateReviewResponse(ok=True, final_status=updated.final_status, new_revision="")
