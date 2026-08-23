"""ContextPack 동적 Trait Signal 등록 테스트 — 2026-08-23 Trait Ontology v2(2.9단계) §6/§13.

`trait_signal_registry.py`의 `_REGISTRY`는 모듈 전역(Process 전체 공유)이라, 여기서
등록하는 합성 Pack/Blueprint는 실제 Pack의 question_id와 절대 겹치지 않는 접두사를
써서 다른 테스트 파일과 충돌하지 않게 한다."""

from __future__ import annotations

import unittest

from src.data.context_packs._example_pack_builder import build_example_context_pack
from src.schemas.question import FinalizedOption, FinalizedQuestion
from src.schemas.trait_signal import TraitSignal
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint, V2ProbeOptionMapping
from src.services.trait_signal_registry import (
    TraitSignalRegistryError,
    register_context_pack_signals,
    register_shared_probe_blueprint_signals,
    resolve_trait_signals,
)


class RegisterContextPackSignalsTest(unittest.TestCase):
    def setUp(self) -> None:
        # zz_ 접두사 context_id — 실제 Pack과 겹치지 않는 합성 Fixture.
        self.pack = build_example_context_pack("zz_signal_registry_fixture")
        register_context_pack_signals(self.pack)

    def test_seed_resolves_to_exact_blueprint_not_legacy_adapter(self) -> None:
        seed = self.pack.seed_anchor_variants[0]
        blueprint_id = f"{seed.question.question_id}_blueprint"
        option = seed.question.options[0]  # PRIMARY delta가 있는 Role(빌더 관례상 role_1).
        result = resolve_trait_signals(
            question_family_id="seed", blueprint_id=blueprint_id, role_id=option.role_id,
            legacy_primary_trait_delta=option.primary_trait_delta, is_resolution_question=False,
        )
        self.assertEqual(result.mapping_source, "EXACT_BLUEPRINT")
        self.assertEqual([s.trait_id for s in result.signals], list(option.primary_trait_delta))

    def test_no_signal_seed_option_resolves_to_exact_blueprint_no_signal(self) -> None:
        seed = self.pack.seed_anchor_variants[0]
        blueprint_id = f"{seed.question.question_id}_blueprint"
        no_signal_option = seed.question.options[1]  # 빌더 관례상 role_2가 NO_SIGNAL.
        self.assertEqual(no_signal_option.primary_trait_delta, {})
        result = resolve_trait_signals(
            question_family_id="seed", blueprint_id=blueprint_id, role_id=no_signal_option.role_id,
            legacy_primary_trait_delta={}, is_resolution_question=False,
        )
        self.assertEqual(result.mapping_source, "EXACT_BLUEPRINT_NO_SIGNAL")
        self.assertEqual(result.signals, [])

    def test_anchor_backup_resolves_to_exact_blueprint(self) -> None:
        backup = self.pack.anchor_backup_questions[0]
        option = backup.question.options[0]
        result = resolve_trait_signals(
            question_family_id="pack_backup", blueprint_id=backup.question.question_id, role_id=option.role_id,
            legacy_primary_trait_delta=option.primary_trait_delta, is_resolution_question=False,
        )
        self.assertEqual(result.mapping_source, "EXACT_BLUEPRINT")

    def test_reregistering_same_pack_is_idempotent(self) -> None:
        register_context_pack_signals(self.pack)  # 두 번째 호출 — 예외 없이 통과해야 한다.

    def test_conflicting_reregistration_raises(self) -> None:
        seed = self.pack.seed_anchor_variants[0]
        blueprint_id = f"{seed.question.question_id}_blueprint"
        option = seed.question.options[0]
        conflicting_option = FinalizedOption(
            option_id=option.option_id, role_id=option.role_id, text=option.text,
            primary_trait_delta={"pattern_finding": 1} if "causal_analysis" in option.primary_trait_delta else {"causal_analysis": 1},
        )
        # blueprint_id가 원래 seed의 것과 같도록 question_id를 그대로 맞추고, Option
        # 하나의 primary_trait_delta만 바꿔서 "같은 Key, 다른 값" 충돌을 재현한다.
        conflicting_question2 = FinalizedQuestion(
            question_id=seed.question.question_id, context="zz_signal_registry_fixture", target_traits=[],
            frame_id="seed_frame", question_text="충돌 테스트",
            options=[conflicting_option] + list(seed.question.options[1:]),
        )
        from src.schemas.context_pack import ContextPackSeedAnchorQuestion

        conflicting_pack2 = self.pack.model_copy(
            update={
                "seed_anchor_variants": [
                    ContextPackSeedAnchorQuestion(anchor_id=seed.anchor_id, question=conflicting_question2)
                ]
                + list(self.pack.seed_anchor_variants[1:])
            }
        )
        with self.assertRaises(TraitSignalRegistryError):
            register_context_pack_signals(conflicting_pack2)


def _probe_blueprint(blueprint_id: str, trait_id: str) -> V2DirectProbeBlueprint:
    role_ids = [f"{blueprint_id}_r{i}" for i in range(1, 6)]
    options = []
    mappings = []
    for i, role_id in enumerate(role_ids, start=1):
        if i == 1:
            options.append(FinalizedOption(option_id=f"{blueprint_id}_o{i}", role_id=role_id, text="옵션", primary_trait_delta={trait_id: 1}))
            mappings.append(V2ProbeOptionMapping(role_id=role_id, mapping_type="TRAIT_SIGNAL", trait_signals=[TraitSignal(trait_id=trait_id, signal_role="PRIMARY", weight=1.0)]))
        else:
            options.append(FinalizedOption(option_id=f"{blueprint_id}_o{i}", role_id=role_id, text="옵션", primary_trait_delta={}))
            mappings.append(V2ProbeOptionMapping(role_id=role_id, mapping_type="NO_SIGNAL", no_signal_reason="예제"))
    base_question = FinalizedQuestion(
        question_id=f"{blueprint_id}_base", context="zz_probe_fixture_ctx", target_traits=[],
        frame_id="direct_probe", question_text="예제", options=options,
    )
    return V2DirectProbeBlueprint(
        trait_id=trait_id, blueprint_id=blueprint_id, option_mappings=mappings,
        allowed_context_ids=["zz_probe_fixture_ctx"], question_frame_id="direct_probe", purpose="예제",
        base_question=base_question,
    )


class RegisterSharedProbeSignalsTest(unittest.TestCase):
    def test_registers_and_resolves_exact_blueprint(self) -> None:
        bp = _probe_blueprint("zz_shared_probe_fixture", "planning")
        register_shared_probe_blueprint_signals([bp])
        target_role = bp.option_mappings[0].role_id
        result = resolve_trait_signals(
            question_family_id="pack_direct_probe", blueprint_id=bp.blueprint_id, role_id=target_role,
            legacy_primary_trait_delta={"planning": 1}, is_resolution_question=False,
        )
        self.assertEqual(result.mapping_source, "EXACT_BLUEPRINT")
        self.assertEqual([s.trait_id for s in result.signals], ["planning"])

    def test_idempotent_reregistration(self) -> None:
        bp = _probe_blueprint("zz_shared_probe_fixture_2", "causal_analysis")
        register_shared_probe_blueprint_signals([bp])
        register_shared_probe_blueprint_signals([bp])  # 예외 없어야 한다.


if __name__ == "__main__":
    unittest.main()
