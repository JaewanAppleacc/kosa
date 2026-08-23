"""Sparse Trait Signal 테스트 — 1단계 지시서 §15 "Sparse Signal" + 1.5단계 §14 "Registry"."""

from __future__ import annotations

import unittest

from src.schemas.trait_signal import TraitSignal, TraitSignalRegistryKey
from src.services.related_concept_registry import load_related_concepts_v2
from src.services.trait_ontology_v2 import load_trait_ontology_v2
from src.services.trait_signal_registry import (
    _NO_SIGNAL_KEYS,
    _REGISTRY,
    _register,
    TraitSignalRegistryError,
    all_registrations,
    resolve_trait_signals,
    validate_full_registry,
    validate_role_signals,
)

_KNOWN_TRAIT_IDS = {t.trait_id for t in load_trait_ontology_v2()}
_KNOWN_CONCEPT_IDS = {c.concept_id for c in load_related_concepts_v2()}


class TraitSignalWeightValidationTest(unittest.TestCase):
    def test_primary_must_be_1_0(self) -> None:
        with self.assertRaises(ValueError):
            TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=0.9)

    def test_related_must_be_033_or_067(self) -> None:
        with self.assertRaises(ValueError):
            TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.5)
        TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.33)
        TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.67)

    def test_related_rejects_arbitrary_precision(self) -> None:
        """LLM이나 임의 계산이 만들 법한 가짜 정밀도 값(예: 0.4123)을 거부한다."""

        with self.assertRaises(ValueError):
            TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.4123)

    def test_trait_signal_is_frozen(self) -> None:
        """1.5단계 §6: Registry가 반환한 Signal을 호출자가 고쳐도 정본이 오염되지 않도록
        TraitSignal 자체를 frozen으로 고정한다."""

        signal = TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)
        with self.assertRaises(Exception):
            signal.weight = 0.5  # type: ignore[misc]

    def test_related_concept_ids_default_is_not_shared_between_instances(self) -> None:
        """1.5단계 §6: mutable default([]) 대신 default_factory를 쓰는지 확인 — 한
        인스턴스의 리스트를 건드려도 다른 인스턴스에 안 새게 하는 회귀 테스트."""

        a = TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)
        b = TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0)
        self.assertIsNot(a.related_concept_ids, b.related_concept_ids)


class RegistryStructureTest(unittest.TestCase):
    def test_registry_is_not_empty(self) -> None:
        self.assertTrue(_REGISTRY)

    def test_registry_has_seed_tail_backup_and_v2_direct_probe_entries(self) -> None:
        """1.5단계 §2/§4: Backup Question도 Registry에 등록돼 있어야 한다(1단계에서는
        전혀 등록돼 있지 않았다 — §1 감사에서 발견한 원인 중 하나). 2단계 §5/§8: 신규
        Trait Direct Probe Blueprint도 별도 계열("v2_direct_probe")로 등록돼 있어야
        한다.

        2026-08-23 2.9단계 §6: `unittest discover`가 같은 프로세스에서 `main.py`를
        import하면 `ContextPackRegistry`가 실제 Context Pack(business 등)과 공용
        Adaptive Probe를 "seed"/"pack_backup"/"pack_direct_probe" family로 동적
        등록한다 — 이 4개 Legacy family가 최소한 전부 있는지만 확인한다(초과는 정상)."""

        families = {key.question_family_id for key in _REGISTRY}
        self.assertTrue({"seed", "tail_blueprint", "backup", "v2_direct_probe"} <= families)

    def test_registry_has_exactly_205_composite_keys(self) -> None:
        # (Seed 3 + Tail Blueprint 3 + Backup 6(2.5.3단계 REVISE, Runtime 제외) +
        # Anchor Backup 15(2.5.4단계) + V2 Direct Probe 14) × Role 5개 = 205.
        # V2 Direct Probe의 NO_SIGNAL Role, Anchor Backup의 NO_SIGNAL Role은
        # `_REGISTRY`가 아니라 `_NO_SIGNAL_KEYS`에 등록된다 — 둘을 합쳐야 전체 205개다.
        #
        # 2026-08-23 2.9단계 §6: ContextPackRegistry가 동적으로 등록하는 신규
        # Context Pack Seed/Anchor Backup·공용 Adaptive Probe Signal이 이 값을
        # 늘린다(같은 프로세스에서 main.py가 먼저 import되면). 205는 이제 "최소
        # 하한"이다 — 정적 Legacy 등록이 실수로 줄어드는 회귀만 잡는다.
        self.assertGreaterEqual(len(_REGISTRY) + len(_NO_SIGNAL_KEYS), 205)

    def test_no_signal_keys_are_v2_direct_probe_or_backup_and_have_no_overlap_with_registry(self) -> None:
        # 2.5단계 §7: detail_orientation_media_v1의 do_visual_check가 미디어 재정의
        # (제작 → 감상)로 "화면 구도·연출을 인상 깊게 떠올린다"는 visual_expression
        # 근거를 갖는다고 보고 NO_SIGNAL에서 TRAIT_SIGNAL로 바꿨었다(14 → 13).
        #
        # 2.5.1단계 §10-A: 다시 살펴보니 그 근거는 "관심·감상"이지 학생이 직접
        # "표현"했다는 증거가 아니었다(사용자 지적) — do_visual_check를 NO_SIGNAL로
        # 되돌렸다(13 → 14). 같은 라운드 §10-C에서 independent_judgment_school_life_v1의
        # ij_adapt_role도 change_adaptation(TRAIT_SIGNAL)에서 "다수 추종" NO_SIGNAL로
        # 바꿨다(14 → 15).
        #
        # 2.5.4단계 §5: Anchor Backup 15개 중 26개 Option이 "행동만으로는 특정 성향을
        # 단정할 근거가 약하다"는 정직한 이유로 NO_SIGNAL이다(v2 Direct Probe와 별개로
        # "backup" 계열도 처음으로 NO_SIGNAL을 갖는다, 15 → 41).
        # 2026-08-23 2.9단계 §6: 신규 Context Pack Seed/Anchor Backup·공용 Adaptive
        # Probe도 NO_SIGNAL Option을 가질 수 있어("seed"/"pack_backup"/
        # "pack_direct_probe" family 추가) 41은 이제 하한이다 — 핵심 불변식은 그대로
        # "_REGISTRY와 _NO_SIGNAL_KEYS는 절대 겹치지 않는다"다.
        self.assertGreaterEqual(len(_NO_SIGNAL_KEYS), 41)
        for key in _NO_SIGNAL_KEYS:
            self.assertIn(
                key.question_family_id,
                ("v2_direct_probe", "backup", "seed", "pack_backup", "pack_direct_probe"),
            )
        self.assertEqual(set(_REGISTRY) & _NO_SIGNAL_KEYS, set())

    def test_full_registry_passes_validation(self) -> None:
        validate_full_registry(_KNOWN_TRAIT_IDS, _KNOWN_CONCEPT_IDS)  # 예외 없으면 통과

    def test_primary_count_between_1_and_2(self) -> None:
        for key, signals in _REGISTRY.items():
            with self.subTest(key=key):
                primary_count = sum(1 for s in signals if s.signal_role == "PRIMARY")
                self.assertGreaterEqual(primary_count, 1)
                self.assertLessEqual(primary_count, 2)

    def test_related_count_at_most_3(self) -> None:
        for key, signals in _REGISTRY.items():
            with self.subTest(key=key):
                related_count = sum(1 for s in signals if s.signal_role == "RELATED")
                self.assertLessEqual(related_count, 3)

    def test_total_signals_at_most_5(self) -> None:
        for key, signals in _REGISTRY.items():
            with self.subTest(key=key):
                self.assertLessEqual(len(signals), 5)

    def test_no_duplicate_trait_id_within_a_role(self) -> None:
        for key, signals in _REGISTRY.items():
            with self.subTest(key=key):
                trait_ids = [s.trait_id for s in signals]
                self.assertEqual(len(trait_ids), len(set(trait_ids)))

    def test_same_role_id_in_different_blueprints_is_no_longer_a_collision(self) -> None:
        """1단계는 role_id="team_coordination"이 Tail Blueprint와 game Seed 양쪽에
        등장하는 걸 "값이 우연히 같은 하나의 등록"으로 취급했다 — 1.5단계는 복합 Key라
        구조적으로 다른 두 등록이다. 둘 다 존재하고, 둘 다 같은 판단(collaboration_
        preference PRIMARY)을 내리지만 그건 우연이 아니라 각자 독립적으로 검토된 값이다."""

        tail_key = TraitSignalRegistryKey(
            question_family_id="tail_blueprint", blueprint_id="planning_and_execution_v1",
            role_id="team_coordination",
        )
        seed_key = TraitSignalRegistryKey(
            question_family_id="seed", blueprint_id="game_seed_01_blueprint",
            role_id="team_coordination",
        )
        self.assertIn(tail_key, _REGISTRY)
        self.assertIn(seed_key, _REGISTRY)
        self.assertNotEqual(tail_key, seed_key)


class DuplicateKeyFailFastTest(unittest.TestCase):
    def test_duplicate_composite_key_registration_raises(self) -> None:
        """(tail_blueprint, problem_response_v1, cause_analysis)는 모듈 로드 시점에 이미
        등록돼 있다 — 같은 복합 Key로 다시 등록을 시도하면 그 자리에서 막혀야 한다(여러
        dict를 `**`로 병합해 나중 값이 조용히 앞 값을 덮어쓰는 1단계 방식으로 되돌아가지
        않는다)."""

        with self.assertRaises(TraitSignalRegistryError):
            _register(
                "tail_blueprint", "problem_response_v1",
                {"cause_analysis": [TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)]},
                known_role_ids={"cause_analysis"},
            )

    def test_registering_unknown_role_id_raises(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            _register(
                "tail_blueprint", "problem_response_v1",
                {"not_a_real_role": [TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)]},
                known_role_ids={"cause_analysis"},
            )


class DefensiveCopyTest(unittest.TestCase):
    def test_all_registrations_mutation_does_not_affect_canonical_registry(self) -> None:
        registrations = all_registrations()
        key = next(iter(registrations))
        signals = registrations[key]
        signals[0].related_concept_ids.append("intruder")
        self.assertNotIn("intruder", all_registrations()[key][0].related_concept_ids)

    def test_resolve_trait_signals_mutation_does_not_affect_registry(self) -> None:
        resolution = resolve_trait_signals(
            question_family_id="tail_blueprint", blueprint_id="problem_response_v1",
            role_id="cause_analysis", legacy_primary_trait_delta={"causal_analysis": 1},
            is_resolution_question=False,
        )
        related = next(s for s in resolution.signals if s.signal_role == "RELATED")
        related.related_concept_ids.append("intruder")
        second = resolve_trait_signals(
            question_family_id="tail_blueprint", blueprint_id="problem_response_v1",
            role_id="cause_analysis", legacy_primary_trait_delta={"causal_analysis": 1},
            is_resolution_question=False,
        )
        second_related = next(s for s in second.signals if s.signal_role == "RELATED")
        self.assertNotIn("intruder", second_related.related_concept_ids)


class ResolveTraitSignalsTest(unittest.TestCase):
    def test_conflict_resolution_always_returns_none_mapping(self) -> None:
        resolution = resolve_trait_signals(
            question_family_id="seed", blueprint_id="whatever", role_id="whatever",
            legacy_primary_trait_delta={"causal_analysis": 1}, is_resolution_question=True,
        )
        self.assertEqual(resolution.signals, [])
        self.assertEqual(resolution.mapping_source, "NONE_CONFLICT_RESOLUTION")

    def test_exact_blueprint_match_returns_registered_signals(self) -> None:
        resolution = resolve_trait_signals(
            question_family_id="tail_blueprint", blueprint_id="problem_response_v1",
            role_id="cause_analysis", legacy_primary_trait_delta={"causal_analysis": 1},
            is_resolution_question=False,
        )
        self.assertEqual(resolution.mapping_source, "EXACT_BLUEPRINT")
        primary = [s for s in resolution.signals if s.signal_role == "PRIMARY"]
        self.assertEqual(len(primary), 1)
        self.assertEqual(primary[0].trait_id, "causal_analysis")

    def test_unregistered_combination_falls_back_to_legacy_adapter(self) -> None:
        """정상 질문인데 signals=[]로 조용히 끝나는 경로가 없어야 한다(1.5단계 §2/§4) —
        role_id/blueprint_id가 Registry에 전혀 없어도(예: LLM-off Mock 자리표시자 질문)
        legacy primary_trait_delta로부터 PRIMARY Signal이 최소 1개는 나온다."""

        resolution = resolve_trait_signals(
            question_family_id="mock_placeholder", blueprint_id="game_tail_02",
            role_id="role_causal_analysis", legacy_primary_trait_delta={"causal_analysis": 1},
            is_resolution_question=False,
        )
        self.assertEqual(resolution.mapping_source, "LEGACY_PRIMARY_ADAPTER")
        self.assertEqual(len(resolution.signals), 1)
        self.assertEqual(resolution.signals[0].trait_id, "causal_analysis")
        self.assertEqual(resolution.signals[0].signal_role, "PRIMARY")
        self.assertEqual(resolution.signals[0].weight, 1.0)

    def test_legacy_adapter_never_invents_related_signals(self) -> None:
        resolution = resolve_trait_signals(
            question_family_id="mock_placeholder", blueprint_id="x", role_id="y",
            legacy_primary_trait_delta={"causal_analysis": 1}, is_resolution_question=False,
        )
        self.assertFalse(any(s.signal_role == "RELATED" for s in resolution.signals))

    def test_same_role_id_different_blueprint_resolves_independently(self) -> None:
        tail = resolve_trait_signals(
            question_family_id="tail_blueprint", blueprint_id="planning_and_execution_v1",
            role_id="team_coordination", legacy_primary_trait_delta={"collaboration_preference": 1},
            is_resolution_question=False,
        )
        seed = resolve_trait_signals(
            question_family_id="seed", blueprint_id="game_seed_01_blueprint",
            role_id="team_coordination", legacy_primary_trait_delta={"collaboration_preference": 1},
            is_resolution_question=False,
        )
        self.assertEqual(tail.mapping_source, "EXACT_BLUEPRINT")
        self.assertEqual(seed.mapping_source, "EXACT_BLUEPRINT")


class ValidateRoleSignalsRejectionTest(unittest.TestCase):
    def test_rejects_zero_primary(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.33)],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_more_than_2_primary(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r",
                [
                    TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id="pattern_finding", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id="planning", signal_role="PRIMARY", weight=1.0),
                ],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_more_than_3_related(self) -> None:
        primary = TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0)
        related = [
            TraitSignal(trait_id=t, signal_role="RELATED", weight=0.33)
            for t in ("pattern_finding", "planning", "tool_utilization", "visual_expression")
        ]
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [primary, *related],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_more_than_5_total(self) -> None:
        primary = [
            TraitSignal(trait_id=t, signal_role="PRIMARY", weight=1.0)
            for t in ("causal_analysis", "pattern_finding")
        ]
        related = [
            TraitSignal(trait_id=t, signal_role="RELATED", weight=0.33)
            for t in ("planning", "tool_utilization", "visual_expression", "collaboration_preference")
        ]
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [*primary, *related],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_duplicate_trait_id_across_signals(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r",
                [
                    TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(trait_id="causal_analysis", signal_role="RELATED", weight=0.33),
                ],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_unknown_trait_id(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", [TraitSignal(trait_id="not_a_real_trait", signal_role="PRIMARY", weight=1.0)],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_rejects_unknown_concept_id(self) -> None:
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r",
                [
                    TraitSignal(trait_id="causal_analysis", signal_role="PRIMARY", weight=1.0),
                    TraitSignal(
                        trait_id="systems_thinking", signal_role="RELATED", weight=0.33,
                        related_concept_ids=["not_a_real_concept"],
                    ),
                ],
                known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )

    def test_dense_24_dimension_signal_list_is_rejected(self) -> None:
        """§4 "Dense 24차원 Signal 생성 차단" — 억지로 24개 Trait 전부에 Signal을 만들면
        전체 5개 상한에서 이미 걸린다."""

        all_traits = sorted(_KNOWN_TRAIT_IDS)[:24]
        signals = [TraitSignal(trait_id=all_traits[0], signal_role="PRIMARY", weight=1.0)] + [
            TraitSignal(trait_id=t, signal_role="RELATED", weight=0.33) for t in all_traits[1:]
        ]
        with self.assertRaises(TraitSignalRegistryError):
            validate_role_signals(
                "r", signals, known_trait_ids=_KNOWN_TRAIT_IDS, known_concept_ids=_KNOWN_CONCEPT_IDS,
            )


if __name__ == "__main__":
    unittest.main()
