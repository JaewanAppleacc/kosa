"""ContextPack 검수 UI 서비스 계층 — 2026-08-23 Trait Ontology v2(2.8단계) §9. A 소유.

T·S·L이 `src/data/context_packs/`에 새 Pack 파일을 추가하기만 하면 이 모듈이 자동으로
찾아서(`ContextPackRegistry`) 검수 목록에 반영한다 — Context마다 이 파일을 고칠 필요가
없다. 실제 Runtime 변환 함수(`ContextPackRegistry`/`compute_context_trait_coverage`)를
그대로 재사용한다 — 가짜 Preview 데이터를 따로 만들지 않는다(§9 마지막 규칙).

이 모듈은 어떤 항목도 스스로 APPROVE/REVISE/HOLD로 바꾸지 않는다 — 오직 사람이 보낸
요청을 그대로 저장할 뿐이다(다른 검수 Store와 동일한 원칙)."""

from __future__ import annotations

from pydantic import ValidationError as PydanticValidationError

from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS
from src.engines.question_quality_gate import run_quality_gate
from src.schemas.context_pack import ContextPack
from src.schemas.context_pack_shared_probe_review import SharedProbeContextReview
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
    SharedProbeAnchorPreviewView,
    SharedProbeContextRow,
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


def _shared_probe_review_view(entry: SharedProbeContextReview | None) -> QuestionReviewView:
    entry = entry or SharedProbeContextReview(blueprint_id="", context_id="")
    return QuestionReviewView(
        reviewer_1_status=entry.reviewer_1_status, reviewer_1_comment=entry.reviewer_1_comment,
        reviewer_2_status=entry.reviewer_2_status, reviewer_2_comment=entry.reviewer_2_comment,
        final_status=entry.final_status, resolution_note=entry.resolution_note,
    )


def build_shared_probe_list(
    registry: ContextPackRegistry, shared_pool: list[V2DirectProbeBlueprint],
    trait_definitions: dict[str, TraitDefinition],
) -> SharedProbeListResponse:
    """2026-08-23 Trait Ontology v2(2.9/2.9.1단계) §5/§11 — ContextPack 공용 Adaptive
    Probe Blueprint(`context_pack_shared_probe_blueprints.py`)를 Blueprint → Context
    → Anchor 3단으로 보여준다(2.9.1단계 §3 — Context+Anchor 단위 검수로 세분화됐으므로
    화면도 그 단위를 그대로 반영해야 한다). Anchor Preview는 실제 그 Context Pack의
    `anchor_presentations`(Registry가 실제로 발견한 Pack)를 그대로 쓰고,
    forbidden_assumption 검사는 실제 `run_quality_gate()`를 호출한 결과다 — 둘 다
    UI 전용 가짜 데이터가 아니다. `is_approved`는 실제 Runtime이 쓰는 바로 그 함수
    (`registry.is_shared_probe_approved_for_anchor`)를 그대로 호출한다."""

    trait_labels = {t.trait_id: t.label for t in trait_definitions.values()}
    trait_defs = {t.trait_id: t.definition for t in trait_definitions.values()}

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

        context_rows: list[SharedProbeContextRow] = []
        for context_id in sorted(bp.allowed_context_ids):
            pack = registry.get_pack(context_id)
            if pack is None:
                continue  # 아직 그 Context Pack 자체가 발견되지 않았다 — 가짜 행을 만들지 않는다.
            entry = registry.get_shared_probe_context_review(bp.blueprint_id, context_id)
            anchor_views = []
            any_usable = False
            for anchor in pack.anchor_presentations:
                gate = run_quality_gate(
                    bp.base_question, forbidden_anchor_assumption_phrases=tuple(anchor.forbidden_assumptions),
                )
                is_approved = registry.is_shared_probe_approved_for_anchor(bp.blueprint_id, context_id, anchor.anchor_id)
                is_excluded = entry is not None and anchor.anchor_id in entry.excluded_anchor_ids
                any_usable = any_usable or is_approved
                anchor_views.append(
                    SharedProbeAnchorPreviewView(
                        anchor_id=anchor.anchor_id, label=anchor.label, situation_terms=anchor.situation_terms,
                        preferred_scenarios=anchor.preferred_scenarios, forbidden_assumptions=anchor.forbidden_assumptions,
                        forbidden_assumption_failures=gate.failures, is_approved=is_approved, is_excluded=is_excluded,
                    )
                )
            context_rows.append(
                SharedProbeContextRow(
                    context_id=context_id, context_label=_CONTEXT_LABEL_BY_ID.get(context_id, context_id),
                    review=_shared_probe_review_view(entry), anchors=anchor_views, is_runtime_usable=any_usable,
                )
            )

        items.append(
            SharedProbeReviewItem(
                blueprint_id=bp.blueprint_id, trait_id=bp.trait_id,
                trait_label=trait_labels.get(bp.trait_id, bp.trait_id),
                trait_definition=trait_defs.get(bp.trait_id, ""), purpose=bp.purpose,
                question_text=bp.base_question.question_text, options=options, contexts=context_rows,
            )
        )
    return SharedProbeListResponse(probes=sorted(items, key=lambda i: i.blueprint_id))


class UnknownSharedProbeError(ValueError):
    pass


class UnknownSharedProbeContextError(ValueError):
    pass


class UnknownAnchorIdError(ValueError):
    """2026-08-23 Trait Ontology v2(2.9.1단계) §1-2 — approved_anchor_ids/
    excluded_anchor_ids에 그 ContextPack에 실제로 존재하지 않는 Anchor ID가 있을 때.
    오류 메시지에는 anchor_id/context_id/blueprint_id 같은 내부 식별자만 담는다 —
    질문 원문이나 학생 답변은 이 경로에 애초에 등장하지 않는다."""


class SharedProbeAnchorListValidationError(ValueError):
    """2026-08-23 Trait Ontology v2(2.9.1단계) §1-2 — `SharedProbeContextReview`
    Schema의 구조 검증(중복 Anchor ID, 공백 ID, 승인·제외 교집합)이 실패했을 때.
    `SharedProbeContextReview.model_validate()`가 던지는 `pydantic.ValidationError`를
    이 도메인 예외로 감싼다 — 내용은 Schema 쪽 오류 메시지 그대로이고(anchor_id 등
    내부 식별자만 포함, 질문 원문·학생 답변 없음), 형식만 이 모듈의 다른 오류들과
    통일한다(엔드포인트가 항상 이 모듈의 예외 타입만 잡으면 되게)."""


def update_shared_probe_review(
    registry: ContextPackRegistry, shared_pool: list[V2DirectProbeBlueprint], blueprint_id: str, context_id: str, *,
    status: ReviewerStatus | None, comment: str | None, approved_anchor_ids: list[str] | None,
    excluded_anchor_ids: list[str] | None, resolution_note: str | None,
) -> UpdateReviewResponse:
    """2026-08-23 Trait Ontology v2(2.9.1단계) §3/§11/§1-2/§1-3 — 최소 승인 Key
    `(blueprint_id, context_id)` 하나만 갱신한다(나머지 11개 Context 행은 전혀
    건드리지 않는다 — 이게 바로 2.9단계 버그의 수정 지점이다).

    각 인자는 전부 "None이면 기존 값을 그대로 두고, 값이 오면 그 값으로 완전히
    교체한다"는 같은 규칙을 따른다 — `approved_anchor_ids`/`excluded_anchor_ids`뿐
    아니라 `status`/`comment`도 2.9.1단계 §1-3부터 이 규칙에 포함된다. Review UI의
    "이 Anchor 판정 저장" 버튼은 `status`/`comment`를 아예 보내지 않는다(None) —
    Anchor 목록만 바뀌어야 하고, Context의 reviewer_1_status는 "Context 상태 저장"
    버튼으로 사용자가 명시적으로 상태를 고를 때만 바뀐다. 이전에는 화면이 TBD를
    암묵적으로 APPROVE로 승격시켜 보냈다 — 그 버그를 여기서(계약을 Optional로 열어
    "보내지 않을 수 있게" 만들고) 근본적으로 막는다."""

    bp = next((b for b in shared_pool if b.blueprint_id == blueprint_id), None)
    if bp is None:
        raise UnknownSharedProbeError(f"blueprint_id {blueprint_id!r}가 공용 Adaptive Probe 목록에 없다")
    if context_id not in bp.allowed_context_ids:
        raise UnknownSharedProbeContextError(f"{blueprint_id!r}는 context_id {context_id!r}에 노출되지 않는다")

    # §1-2: 실제 Pack 정본과 대조해야 하는 검증(미등록 Anchor ID)은 여기(Service
    # 계층)에서 한다 — Schema(SharedProbeContextReview)는 Pack을 몰라서 이 검증을
    # 할 수 없다.
    pack = registry.get_pack(context_id)
    valid_anchor_ids = {a.anchor_id for a in pack.anchor_presentations} if pack is not None else set()

    review_path = registry.shared_probe_review_status_path()
    entries = load_shared_probe_review_entries(review_path)
    by_key = {e.key: e for e in entries}
    key = f"{blueprint_id}::{context_id}"
    existing = by_key.get(key) or SharedProbeContextReview(blueprint_id=blueprint_id, context_id=context_id)

    merged = existing.model_dump()
    if status is not None:
        merged["reviewer_1_status"] = status
    if comment is not None:
        merged["reviewer_1_comment"] = comment
    if approved_anchor_ids is not None:
        merged["approved_anchor_ids"] = approved_anchor_ids
    if excluded_anchor_ids is not None:
        merged["excluded_anchor_ids"] = excluded_anchor_ids
    if resolution_note is not None:
        merged["resolution_note"] = resolution_note
    merged["revision"] = str(int(existing.revision) + 1 if existing.revision.isdigit() else 1)

    final_anchor_ids = set(merged["approved_anchor_ids"]) | set(merged["excluded_anchor_ids"])
    unknown_anchor_ids = final_anchor_ids - valid_anchor_ids
    if unknown_anchor_ids:
        raise UnknownAnchorIdError(
            f"context_id={context_id!r}의 ContextPack에 없는 Anchor ID: {sorted(unknown_anchor_ids)}"
        )

    # model_copy(update=...)는 Pydantic 재검증을 건너뛴다 — 구조 검증(중복/공백/
    # 교집합, §1-2)이 실제로 강제되도록 항상 model_validate로 새로 만든다.
    try:
        updated = SharedProbeContextReview.model_validate(merged)
    except PydanticValidationError as exc:
        raise SharedProbeAnchorListValidationError(str(exc)) from exc
    by_key[key] = updated
    save_shared_probe_review_entries([by_key[k] for k in sorted(by_key)], review_path)
    return UpdateReviewResponse(ok=True, final_status=updated.final_status, new_revision=updated.revision)


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
