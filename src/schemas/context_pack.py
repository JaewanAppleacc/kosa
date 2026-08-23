"""ContextPack Schema — 2026-08-23 Trait Ontology v2(2.7단계) §1.

Context 확장 에이전트가 새 Context(business/science/sports 등) 하나를 완결된 단위로
제작할 수 있게 하는 계약이다. `ContextPack` 하나가 그 Context의 Routing·Anchor 상황
표현·Seed Anchor Variant·Anchor Backup·Direct Probe 후보·Mapping Rationale을 전부
담는다 — 기존 3개 Vertical Slice Context(game/media/school_life)가 여러 파일에 흩어져
있던 것과 달리, 새 Context는 이 Pack 하나로 완결된다.

계층 원칙(CLAUDE.md, `trait_v2_direct_probe_blueprints.py`와 동일): 이 파일은 **Pack
내부의 자기 완결적 구조**만 검증한다(Context ID 일치·Anchor 5개·Seed/Backup이 Anchor당
1개·question_id/option_id 전역 중복·Mapping Rationale 존재). 24개 Trait Ontology
존재 여부·검수 상태(DRAFT/APPROVED)처럼 **Pack 밖의 정본과 비교해야 하는 검증**은
Schema 계층이 서비스 계층을 참조하지 않기 위해 `src/services/context_pack_registry.py`
(서비스 계층)가 담당한다.

Claude는 이 Schema/Registry를 만들 뿐, 실제 Context 질문 문구를 대량으로 작성하지
않는다 — 그건 Context 제작 에이전트의 몫이다."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.context_routing import ContextRoutingBlueprint
from src.schemas.question import FinalizedQuestion
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint


class ContextPackValidationError(ValueError):
    """ContextPack 자체의 Cross-field 정합성이 깨졌을 때(§1 Fail-Fast)."""


OptionMappingRationaleSource = Literal["seed_anchor", "anchor_backup", "direct_probe"]


class OptionMappingRationale(BaseModel):
    """§1 "Mapping Rationale 필수" — seed_anchor_variants/anchor_backup_questions/
    direct_probe_candidates에 등장하는 (question_id, role_id) 쌍마다 정확히 1개씩
    있어야 한다. `trait_id=None`이면 그 Option이 NO_SIGNAL이라는 뜻이다(§1 "NO_SIGNAL
    허용" — 억지로 Trait를 붙이지 않는다)."""

    source: OptionMappingRationaleSource
    question_id: str
    role_id: str
    trait_id: str | None = None
    mapping_rationale_draft: str

    @model_validator(mode="after")
    def _rationale_not_blank(self) -> "OptionMappingRationale":
        if not self.mapping_rationale_draft.strip():
            raise ContextPackValidationError(
                f"{self.question_id}/{self.role_id}: mapping_rationale_draft가 비어 있다"
            )
        return self


class ContextPackSeedAnchorQuestion(BaseModel):
    """Anchor 하나의 Seed 질문. 기존 3개 Context의 `SeedAnchorVariant`(문구만 담고
    Trait Delta는 외부 Legacy Seed Question이 소유)와 달리, 새 Context Pack은 완전히
    자기 완결적이다 — `question.options[i].primary_trait_delta`가 이 Anchor의 실제
    Trait Mapping을 직접 담는다(빈 dict={}면 NO_SIGNAL, `anchor_backup_questions.py`와
    같은 관례)."""

    anchor_id: str
    question: FinalizedQuestion


class ContextPackAnchorBackupQuestion(BaseModel):
    """Anchor 하나 전용 Backup 질문 — `anchor_backup_questions.py`와 같은 구조를
    Pack 안에 그대로 담는다. 이 질문은 그 anchor_id 하나에서만 쓰인다."""

    anchor_id: str
    question: FinalizedQuestion


class ContextPack(BaseModel):
    context_id: str
    routing_blueprint: ContextRoutingBlueprint
    anchor_presentations: list[ContextAnchorPresentation]
    seed_anchor_variants: list[ContextPackSeedAnchorQuestion]
    anchor_backup_questions: list[ContextPackAnchorBackupQuestion]
    option_mapping_rationales: list[OptionMappingRationale]
    # 2.7단계 §1: direct_probe_candidates는 신규 Trait를 이 Context에서 직접 관찰하기
    # 위한 후보다 — 0개여도 Pack 자체는 유효하다(모든 Context가 신규 Trait Direct Probe
    # 후보를 반드시 가져야 하는 건 아니다).
    direct_probe_candidates: list[V2DirectProbeBlueprint] = Field(default_factory=list)
    # Context 전체에 적용되는 일반 금지 전제(Anchor별 forbidden_assumptions와는 별개
    # 범위 — 예: "이 Context는 특정 동아리 가입을 전제하지 않는다"처럼 Anchor 무관하게
    # 지켜야 하는 것).
    forbidden_assumptions: list[str] = Field(default_factory=list)
    review_artifact_paths: list[str] = Field(default_factory=list)
    pack_version: str

    @model_validator(mode="after")
    def _context_id_consistency(self) -> "ContextPack":
        if self.routing_blueprint.context_id != self.context_id:
            raise ContextPackValidationError(
                f"{self.context_id}: routing_blueprint.context_id "
                f"{self.routing_blueprint.context_id!r}가 Pack context_id와 다르다"
            )
        for presentation in self.anchor_presentations:
            if presentation.context_id != self.context_id:
                raise ContextPackValidationError(
                    f"{self.context_id}: anchor_presentations의 context_id "
                    f"{presentation.context_id!r}가 Pack context_id와 다르다"
                )
        for seed in self.seed_anchor_variants:
            if seed.question.context != self.context_id:
                raise ContextPackValidationError(
                    f"{self.context_id}/{seed.anchor_id}: seed 질문의 context "
                    f"{seed.question.context!r}가 Pack context_id와 다르다"
                )
        for backup in self.anchor_backup_questions:
            if backup.question.context != self.context_id:
                raise ContextPackValidationError(
                    f"{self.context_id}/{backup.anchor_id}: backup 질문의 context "
                    f"{backup.question.context!r}가 Pack context_id와 다르다"
                )
        for probe in self.direct_probe_candidates:
            if self.context_id not in probe.allowed_context_ids:
                raise ContextPackValidationError(
                    f"{self.context_id}: direct_probe_candidates {probe.blueprint_id!r}의 "
                    f"allowed_context_ids {probe.allowed_context_ids}에 Pack context_id가 없다"
                )
        return self

    @model_validator(mode="after")
    def _exactly_5_anchors(self) -> "ContextPack":
        if len(self.anchor_presentations) != 5:
            raise ContextPackValidationError(
                f"{self.context_id}: anchor_presentations는 정확히 5개여야 한다"
                f"(got {len(self.anchor_presentations)})"
            )
        anchor_ids = [a.anchor_id for a in self.anchor_presentations]
        if len(set(anchor_ids)) != 5:
            raise ContextPackValidationError(f"{self.context_id}: anchor_id가 중복됐다: {anchor_ids}")
        return self

    @model_validator(mode="after")
    def _routing_anchor_ids_match_presentation_set(self) -> "ContextPack":
        presentation_anchor_ids = {a.anchor_id for a in self.anchor_presentations}
        routing_anchor_ids = {m.context_anchor for m in self.routing_blueprint.option_mappings}
        if routing_anchor_ids != presentation_anchor_ids:
            raise ContextPackValidationError(
                f"{self.context_id}: routing_blueprint의 Anchor 집합 {sorted(routing_anchor_ids)}가 "
                f"anchor_presentations의 Anchor 집합 {sorted(presentation_anchor_ids)}와 다르다"
                "(미등록 Anchor 참조 차단)"
            )
        return self

    @model_validator(mode="after")
    def _seed_and_backup_exactly_one_per_anchor(self) -> "ContextPack":
        presentation_anchor_ids = {a.anchor_id for a in self.anchor_presentations}

        seed_anchor_ids = [s.anchor_id for s in self.seed_anchor_variants]
        if len(seed_anchor_ids) != len(set(seed_anchor_ids)):
            raise ContextPackValidationError(f"{self.context_id}: seed_anchor_variants의 anchor_id가 중복됐다")
        if set(seed_anchor_ids) != presentation_anchor_ids:
            raise ContextPackValidationError(
                f"{self.context_id}: seed_anchor_variants의 Anchor 집합이 anchor_presentations와 "
                f"다르다(Anchor마다 정확히 1개여야 함) — {sorted(seed_anchor_ids)} != "
                f"{sorted(presentation_anchor_ids)}"
            )

        backup_anchor_ids = [b.anchor_id for b in self.anchor_backup_questions]
        if len(backup_anchor_ids) != len(set(backup_anchor_ids)):
            raise ContextPackValidationError(f"{self.context_id}: anchor_backup_questions의 anchor_id가 중복됐다")
        if set(backup_anchor_ids) != presentation_anchor_ids:
            raise ContextPackValidationError(
                f"{self.context_id}: anchor_backup_questions의 Anchor 집합이 anchor_presentations와 "
                f"다르다(Anchor마다 정확히 1개여야 함) — {sorted(backup_anchor_ids)} != "
                f"{sorted(presentation_anchor_ids)}"
            )
        return self

    @model_validator(mode="after")
    def _global_question_and_option_id_uniqueness(self) -> "ContextPack":
        all_questions: list[FinalizedQuestion] = [self.routing_blueprint.base_question]
        all_questions.extend(s.question for s in self.seed_anchor_variants)
        all_questions.extend(b.question for b in self.anchor_backup_questions)
        all_questions.extend(p.base_question for p in self.direct_probe_candidates)

        question_ids = [q.question_id for q in all_questions]
        if len(question_ids) != len(set(question_ids)):
            raise ContextPackValidationError(
                f"{self.context_id}: question_id가 Pack 안에서 중복됐다: {question_ids}"
            )

        option_ids: list[str] = []
        for question in all_questions:
            role_ids = [o.role_id for o in question.options]
            if len(role_ids) != len(set(role_ids)):
                raise ContextPackValidationError(
                    f"{self.context_id}/{question.question_id}: role_id가 같은 질문 안에서 중복됐다"
                )
            option_ids.extend(o.option_id for o in question.options)
        if len(option_ids) != len(set(option_ids)):
            raise ContextPackValidationError(
                f"{self.context_id}: option_id가 Pack 안에서 중복됐다"
            )
        return self

    @model_validator(mode="after")
    def _mapping_rationale_required_for_every_option(self) -> "ContextPack":
        expected: set[tuple[str, str]] = set()
        for seed in self.seed_anchor_variants:
            expected.update((seed.question.question_id, o.role_id) for o in seed.question.options)
        for backup in self.anchor_backup_questions:
            expected.update((backup.question.question_id, o.role_id) for o in backup.question.options)
        for probe in self.direct_probe_candidates:
            expected.update((probe.base_question.question_id, o.role_id) for o in probe.base_question.options)

        provided = {(r.question_id, r.role_id) for r in self.option_mapping_rationales}
        if len(provided) != len(self.option_mapping_rationales):
            raise ContextPackValidationError(f"{self.context_id}: option_mapping_rationales에 중복 Key가 있다")
        if provided != expected:
            missing = expected - provided
            extra = provided - expected
            raise ContextPackValidationError(
                f"{self.context_id}: option_mapping_rationales가 실제 Option 목록과 일치하지 않는다"
                f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
            )
        return self

    @model_validator(mode="after")
    def _rationale_trait_id_matches_option_delta(self) -> "ContextPack":
        """Rationale의 trait_id는 실제 Option의 primary_trait_delta와 일치해야 한다
        (검토자가 서로 다른 값을 볼 위험을 구조적으로 막는다)."""

        rationale_by_key = {(r.question_id, r.role_id): r for r in self.option_mapping_rationales}
        all_questions: list[FinalizedQuestion] = [s.question for s in self.seed_anchor_variants]
        all_questions.extend(b.question for b in self.anchor_backup_questions)
        all_questions.extend(p.base_question for p in self.direct_probe_candidates)
        for question in all_questions:
            for option in question.options:
                rationale = rationale_by_key.get((question.question_id, option.role_id))
                if rationale is None:
                    continue  # 앞선 validator가 이미 잡는다.
                delta_trait_ids = set(option.primary_trait_delta)
                if rationale.trait_id is None:
                    if delta_trait_ids:
                        raise ContextPackValidationError(
                            f"{self.context_id}/{question.question_id}/{option.role_id}: "
                            f"Rationale은 NO_SIGNAL(trait_id=None)인데 실제 primary_trait_delta는 "
                            f"{option.primary_trait_delta}다"
                        )
                elif delta_trait_ids != {rationale.trait_id}:
                    raise ContextPackValidationError(
                        f"{self.context_id}/{question.question_id}/{option.role_id}: "
                        f"Rationale trait_id {rationale.trait_id!r}가 실제 primary_trait_delta "
                        f"{option.primary_trait_delta}와 일치하지 않는다"
                    )
        return self
