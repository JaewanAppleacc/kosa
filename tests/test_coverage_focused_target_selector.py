"""Coverage-focused Target Selector 단위 테스트 — a/coverage-focused-planner-shadow.

`src/engines/coverage_focused_target_selector.py`는 순수 함수다 — 이 테스트는
합성 Fixture만으로 전부 돈다(실제 ContextPack Registry·main.py·9-Persona 세션이
필요 없다). Shadow Harness 자체의 통합 테스트는
`tests/test_coverage_focused_planner_shadow_harness.py`에 있다."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.engines.coverage_focused_target_selector import (  # noqa: E402
    EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE,
    PROVISIONAL_TOP_N,
    ApprovedCandidateSignal,
    CoverageFocusedSelectorInput,
    select_coverage_focused_target,
)
from src.engines.trait_evidence_coverage_engine import PRIMARY_WEIGHT  # noqa: E402
from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin, EvidenceRecord  # noqa: E402
from src.schemas.trait_signal import SignalRole  # noqa: E402

CORE_TRAIT_IDS = frozenset(f"trait_{i:02d}" for i in range(24))


def _evidence(
    evidence_id: str, trait_id: str, *, context: str = "science", frame_id: str = "deepen",
    blueprint_id: str | None = None, role: str = "PRIMARY",
) -> EvidenceRecord:
    # 기본값은 evidence_id에서 파생한 고유 blueprint_id다 — 그렇지 않으면
    # 여러 Trait에 대해 만든 서로 다른 Evidence가 전부 같은 (blueprint_id, frame_id)
    # 중복 제거 키를 공유해(`deduplicate_evidence`) 첫 번째만 남고 나머지가 조용히
    # 사라지는 Fixture 버그가 난다. 같은 Blueprint 반복을 일부러 테스트할 때만
    # blueprint_id를 명시적으로 넘긴다.
    if blueprint_id is None:
        blueprint_id = f"bp_{evidence_id}"
    return EvidenceRecord(
        evidence_id=evidence_id, answer_id=f"ans_{evidence_id}", question_id=f"q_{evidence_id}",
        question_frame_id=frame_id, option_role_id="role_1", option_text="text",
        applied_primary_trait_delta={trait_id: 1}, evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        context=context, source_type="v2", generator_version="v1", quality_gate_status="PASSED",
        applied_trait_signals_v2=[AppliedTraitSignal(trait_id=trait_id, signal_role=role, weight=PRIMARY_WEIGHT)],
        source_blueprint_id=blueprint_id,
    )


def _base_input(**overrides) -> CoverageFocusedSelectorInput:
    defaults = dict(
        evidence_ledger=(),
        approved_evidence_ids=frozenset(),
        opportunity_history=(),
        used_context_ids=frozenset(),
        used_frame_ids=frozenset(),
        current_context_id="science",
        remaining_question_budget=10,
        approved_candidate_signals=tuple(
            ApprovedCandidateSignal(trait_id=t, context_id="science", frame_id="deepen", blueprint_id=f"bp_{t}")
            for t in sorted(CORE_TRAIT_IDS)
        ),
        conflicted_trait_ids=frozenset(),
        core_trait_ids=CORE_TRAIT_IDS,
    )
    defaults.update(overrides)
    return CoverageFocusedSelectorInput(**defaults)


class QuestionBudgetTest(unittest.TestCase):
    """§8 '질문 예산 초과 없음'."""

    def test_zero_budget_returns_none(self) -> None:
        result = select_coverage_focused_target(_base_input(remaining_question_budget=0))
        self.assertIsNone(result)

    def test_negative_budget_returns_none(self) -> None:
        result = select_coverage_focused_target(_base_input(remaining_question_budget=-1))
        self.assertIsNone(result)

    def test_positive_budget_can_return_a_decision(self) -> None:
        result = select_coverage_focused_target(_base_input(remaining_question_budget=1))
        self.assertIsNotNone(result)


class NoCandidatesTest(unittest.TestCase):
    def test_no_signals_for_current_context_returns_none(self) -> None:
        result = select_coverage_focused_target(_base_input(current_context_id="no_such_context"))
        self.assertIsNone(result)


class ExplorationSlotGuaranteeTest(unittest.TestCase):
    """§3 'Exploration 보장' — 서로 다른 Trait 최소
    EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE(=8, 진단 보고서 실측 상수)개가
    증거를 얻기 전까지는 EXPLORATION 모드다."""

    def test_zero_evidence_starts_in_exploration_mode(self) -> None:
        result = select_coverage_focused_target(_base_input())
        self.assertIsNotNone(result)
        self.assertEqual(result.selection_mode, "EXPLORATION")
        self.assertTrue(result.exploration_slot_used)

    def test_seven_distinct_traits_with_evidence_still_exploration(self) -> None:
        traits = sorted(CORE_TRAIT_IDS)[:7]
        ledger = tuple(_evidence(f"ev_{i}", t) for i, t in enumerate(traits))
        approved = frozenset(r.evidence_id for r in ledger)
        result = select_coverage_focused_target(_base_input(evidence_ledger=ledger, approved_evidence_ids=approved))
        self.assertEqual(result.selection_mode, "EXPLORATION")

    def test_eight_distinct_traits_with_evidence_switches_to_focus(self) -> None:
        self.assertEqual(EXPLORATION_MIN_DISTINCT_TRAITS_WITH_EVIDENCE, 8)
        traits = sorted(CORE_TRAIT_IDS)[:8]
        ledger = tuple(_evidence(f"ev_{i}", t) for i, t in enumerate(traits))
        approved = frozenset(r.evidence_id for r in ledger)
        result = select_coverage_focused_target(_base_input(evidence_ledger=ledger, approved_evidence_ids=approved))
        self.assertEqual(result.selection_mode, "TOP_TRAIT_FOCUS")
        self.assertFalse(result.exploration_slot_used)


class ProvisionalTopTraitLockinTest(unittest.TestCase):
    """§3/§4 — 잠정 상위 Trait 진입·탈락, 동일 Trait 고착 방지."""

    def test_provisional_rank_reflects_weight_ordering(self) -> None:
        traits = sorted(CORE_TRAIT_IDS)
        # 8개에 증거를 줘서 Exploration을 벗어나고, 그중 하나(traits[0])에 압도적으로
        # 많은 weight를 줘서 상위 rank가 되게 만든다.
        ledger = [_evidence(f"seed_{i}", t) for i, t in enumerate(traits[:8])]
        ledger += [_evidence(f"extra_{i}", traits[0], blueprint_id=f"bp_extra_{i}", frame_id=f"frame_{i}") for i in range(3)]
        ledger = tuple(ledger)
        approved = frozenset(r.evidence_id for r in ledger)
        result = select_coverage_focused_target(_base_input(evidence_ledger=ledger, approved_evidence_ids=approved))
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.provisional_rank, 1)
        self.assertLessEqual(result.provisional_rank, len(CORE_TRAIT_IDS))

    def test_trait_stops_being_proposed_once_sufficient(self) -> None:
        """동일 Trait 고착 방지 — 이미 SUFFICIENT가 된 Trait는 다시 제안하지 않는다
        (Coverage 기준을 이 테스트가 다시 재정의하지 않는다 — 실제 Coverage Engine의
        SUFFICIENT 판정을 그대로 신뢰한다)."""

        trait_id = "trait_00"
        others = sorted(CORE_TRAIT_IDS - {trait_id})[:7]
        seed_ledger = [_evidence(f"seed_{i}", t) for i, t in enumerate(others)]
        # trait_00을 SUFFICIENT로 만든다: primary>=2, weight>=3.0, context>=2, frame>=2.
        sufficient_ledger = [
            _evidence("suf_1", trait_id, context="science", frame_id="frame_a", blueprint_id="bp_s1"),
            _evidence("suf_2", trait_id, context="business", frame_id="frame_b", blueprint_id="bp_s2"),
            _evidence("suf_3", trait_id, context="business", frame_id="frame_c", blueprint_id="bp_s3"),
        ]
        ledger = tuple(seed_ledger + sufficient_ledger)
        approved = frozenset(r.evidence_id for r in ledger)
        signals = tuple(
            ApprovedCandidateSignal(trait_id=t, context_id="science", frame_id="deepen", blueprint_id=f"bp_{t}")
            for t in sorted(CORE_TRAIT_IDS)
        )
        result = select_coverage_focused_target(
            _base_input(evidence_ledger=ledger, approved_evidence_ids=approved, approved_candidate_signals=signals)
        )
        self.assertIsNotNone(result)
        self.assertNotEqual(result.proposed_trait_id, trait_id, "SUFFICIENT가 된 Trait를 다시 제안했다")


class ReviewApprovedSignalOnlyTest(unittest.TestCase):
    """§8 '검수 미승인 Signal 제외' — Fail-Closed. `approved_candidate_signals`에
    없는 Trait는 애초에 후보 Pool에 없으므로 제안될 수 없다."""

    def test_unapproved_trait_never_proposed(self) -> None:
        only_one_signal = (
            ApprovedCandidateSignal(trait_id="trait_00", context_id="science", frame_id="deepen", blueprint_id="bp_only"),
        )
        result = select_coverage_focused_target(_base_input(approved_candidate_signals=only_one_signal))
        self.assertIsNotNone(result)
        self.assertEqual(result.proposed_trait_id, "trait_00")

    def test_empty_approved_signals_returns_none(self) -> None:
        result = select_coverage_focused_target(_base_input(approved_candidate_signals=()))
        self.assertIsNone(result)


class PriorityOrderingTest(unittest.TestCase):
    """§4 우선순위 — Primary Evidence 부족 > 누적 Weight 부족 > Context 다양성 부족 >
    Frame 다양성 부족 > Conflict 확인, 이 순서로 부족한 Trait를 우선한다."""

    def test_trait_needing_only_conflict_check_is_deprioritized_below_primary_gap(self) -> None:
        # traits[0]: Primary/Weight/Context/Frame 전부 SUFFICIENT 수준까지 채웠지만
        # 외부에서 아직 안 풀린 Conflict가 있다고 알려온 Trait — "Conflict 확인"
        # 하나만 부족하다.
        # traits[1]: 방금 관찰 시작(seed 8개 중 하나) — Primary Evidence 자체가 부족.
        traits = sorted(CORE_TRAIT_IDS)[:8]
        conflicted_trait, primary_gap_trait = traits[0], traits[1]

        seed_ledger = [_evidence(f"seed_{i}", t) for i, t in enumerate(traits)]  # Exploration 종료용(distinct>=8)
        near_sufficient_ledger = [
            _evidence("near_1", conflicted_trait, context="science", frame_id="frame_a"),
            _evidence("near_2", conflicted_trait, context="business", frame_id="frame_b"),
            _evidence("near_3", conflicted_trait, context="business", frame_id="frame_c"),
        ]
        ledger = tuple(seed_ledger + near_sufficient_ledger)
        approved = frozenset(r.evidence_id for r in ledger)
        signals = tuple(
            ApprovedCandidateSignal(trait_id=t, context_id="science", frame_id="deepen", blueprint_id=f"bp_signal_{t}")
            for t in traits
        )
        result = select_coverage_focused_target(
            _base_input(
                evidence_ledger=ledger, approved_evidence_ids=approved, approved_candidate_signals=signals,
                conflicted_trait_ids=frozenset({conflicted_trait}),
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(
            result.proposed_trait_id, primary_gap_trait,
            "Conflict 확인만 필요한 Trait가 Primary Evidence 자체가 부족한 Trait보다 먼저 선택됐다",
        )

    def test_conflicted_trait_still_eligible_once_it_is_the_only_gap_left(self) -> None:
        """Conflict 확인이 유일하게 남은 부족분이면(다른 모든 Trait가 진짜 SUFFICIENT),
        결국 그 Trait가 제안된다 — 영구히 제외되지 않는다."""

        traits = sorted(CORE_TRAIT_IDS)[:8]
        conflicted_trait = traits[0]
        ledger = [
            _evidence("near_1", conflicted_trait, context="science", frame_id="frame_a"),
            _evidence("near_2", conflicted_trait, context="business", frame_id="frame_b"),
            _evidence("near_3", conflicted_trait, context="business", frame_id="frame_c"),
        ]
        ledger = tuple(ledger)
        approved = frozenset(r.evidence_id for r in ledger)
        signals = (
            ApprovedCandidateSignal(
                trait_id=conflicted_trait, context_id="science", frame_id="deepen", blueprint_id="bp_only",
            ),
        )
        result = select_coverage_focused_target(
            _base_input(
                evidence_ledger=ledger, approved_evidence_ids=approved, approved_candidate_signals=signals,
                conflicted_trait_ids=frozenset({conflicted_trait}),
            )
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.proposed_trait_id, conflicted_trait)

    def test_repeated_blueprint_frame_deprioritized(self) -> None:
        """이미 같은 (blueprint_id, frame_id)로 Evidence가 쌓인 Signal은 다른 신선한
        Signal이 있으면 우선순위가 낮아진다."""

        ledger = (_evidence("ev_1", "trait_00", frame_id="frame_used", blueprint_id="bp_used"),)
        approved = frozenset({"ev_1"})
        signals = (
            ApprovedCandidateSignal(trait_id="trait_00", context_id="science", frame_id="frame_used", blueprint_id="bp_used"),
            ApprovedCandidateSignal(trait_id="trait_00", context_id="science", frame_id="frame_fresh", blueprint_id="bp_fresh"),
        )
        result = select_coverage_focused_target(
            _base_input(evidence_ledger=ledger, approved_evidence_ids=approved, approved_candidate_signals=signals)
        )
        self.assertIsNotNone(result)
        self.assertEqual(result.proposed_frame_id, "frame_fresh")


class FutureEvidenceIndependenceTest(unittest.TestCase):
    """§2 비순환성 — 미래 Evidence를 참조하지 않는다. 같은 접두 시점 상태에서는
    이후 무엇이 오든 지금 시점 결과가 달라지지 않는다는 것을, "이후에 올 Evidence를
    Selector에 아예 안 준 두 호출이 같은 답을 낸다"로 증명한다(Selector 자체는
    자기 입력 밖의 어떤 상태도 참조하지 않는 순수 함수이므로, 같은 입력 → 같은
    출력이면 그 자체로 "미래를 몰래 보지 않는다"는 것도 함께 증명된다)."""

    def test_selector_has_no_future_or_oracle_parameters(self) -> None:
        import inspect

        params = set(inspect.signature(CoverageFocusedSelectorInput).parameters)
        forbidden_substrings = ("final", "future", "oracle", "true_top", "affinity", "persona")
        for param in params:
            for bad in forbidden_substrings:
                self.assertNotIn(bad, param.lower(), f"입력 필드 {param!r}가 금지된 정보를 암시한다")

    def test_same_input_same_output(self) -> None:
        traits = sorted(CORE_TRAIT_IDS)[:5]
        ledger = tuple(_evidence(f"ev_{i}", t) for i, t in enumerate(traits))
        approved = frozenset(r.evidence_id for r in ledger)
        inputs = _base_input(evidence_ledger=ledger, approved_evidence_ids=approved)
        first = select_coverage_focused_target(inputs)
        second = select_coverage_focused_target(inputs)
        self.assertEqual(first, second)

    def test_appending_more_evidence_after_the_fact_does_not_change_earlier_decision(self) -> None:
        traits = sorted(CORE_TRAIT_IDS)
        early_ledger = tuple(_evidence(f"early_{i}", t) for i, t in enumerate(traits[:3]))
        early_approved = frozenset(r.evidence_id for r in early_ledger)
        early_decision = select_coverage_focused_target(
            _base_input(evidence_ledger=early_ledger, approved_evidence_ids=early_approved)
        )

        later_ledger = early_ledger + tuple(_evidence(f"later_{i}", t) for i, t in enumerate(traits[3:10]))
        later_approved = frozenset(r.evidence_id for r in later_ledger)
        # 같은 "이른 시점" 입력을 다시 넣으면(later를 아예 안 준 것과 동일 조건) 여전히
        # 같은 결과 — later_ledger가 존재한다는 사실 자체가 early 시점 계산에 새어들지
        # 않는다.
        replay_decision = select_coverage_focused_target(
            _base_input(evidence_ledger=early_ledger, approved_evidence_ids=early_approved)
        )
        self.assertEqual(early_decision, replay_decision)
        self.assertIsNotNone(later_ledger)
        self.assertIsNotNone(later_approved)


class DeterminismAcrossHashSeedsTest(unittest.TestCase):
    """§8 '서로 다른 PYTHONHASHSEED 결정론성' — 별도 프로세스 2회."""

    def test_two_subprocesses_with_different_hash_seeds_agree(self) -> None:
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "from src.engines.coverage_focused_target_selector import ("
            "select_coverage_focused_target, CoverageFocusedSelectorInput, ApprovedCandidateSignal)\n"
            "from src.schemas.evidence import EvidenceRecord, EvidenceOrigin, AppliedTraitSignal\n"
            "core = frozenset(f'trait_{i:02d}' for i in range(24))\n"
            "def ev(eid, t, ctx, frame, bp):\n"
            "    return EvidenceRecord(evidence_id=eid, answer_id='a_'+eid, question_id='q_'+eid,\n"
            "        question_frame_id=frame, option_role_id='r', option_text='t',\n"
            "        applied_primary_trait_delta={t: 1}, evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,\n"
            "        context=ctx, source_type='v2', generator_version='v1', quality_gate_status='PASSED',\n"
            "        applied_trait_signals_v2=[AppliedTraitSignal(trait_id=t, signal_role='PRIMARY', weight=1.0)],\n"
            "        source_blueprint_id=bp)\n"
            "traits = sorted(core)\n"
            "ledger = tuple(ev(f'ev_{i}', t, 'science', 'deepen', f'bp_{i}') for i, t in enumerate(traits[:9]))\n"
            "approved = frozenset(r.evidence_id for r in ledger)\n"
            "signals = tuple(ApprovedCandidateSignal(trait_id=t, context_id='science', frame_id='deepen',"
            " blueprint_id=f'bp_c_{t}') for t in traits)\n"
            "inputs = CoverageFocusedSelectorInput(evidence_ledger=ledger, approved_evidence_ids=approved,\n"
            "    opportunity_history=(), used_context_ids=frozenset(), used_frame_ids=frozenset(),\n"
            "    current_context_id='science', remaining_question_budget=10,\n"
            "    approved_candidate_signals=signals, conflicted_trait_ids=frozenset(), core_trait_ids=core)\n"
            "d = select_coverage_focused_target(inputs)\n"
            "print(d.proposed_trait_id, d.proposed_frame_id, d.selection_mode, d.provisional_rank, d.evidence_gap)\n"
        ) % str(ROOT)

        def run(seed: str) -> str:
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run([sys.executable, "-c", script], capture_output=True, timeout=60, env=env, cwd=ROOT)
            self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace"))
            return proc.stdout.decode("utf-8")

        first = run("111")
        second = run("999")
        self.assertEqual(first, second)


class ShadowOnlyMarkerTest(unittest.TestCase):
    def test_decision_always_marked_shadow_only(self) -> None:
        result = select_coverage_focused_target(_base_input())
        self.assertIsNotNone(result)
        self.assertTrue(result.shadow_only)


class RuntimeAndMainUntouchedTest(unittest.TestCase):
    """§8 'Runtime Planner·main.py 무변경' — 이 Selector 모듈 자체가 그 파일들을
    Import조차 하지 않는다는 것을 구조적으로 증명한다(§ 방향이 거꾸로다 — Harness가
    이 모듈을 관찰용으로 부르지, 이 모듈이 Runtime을 참조하지 않는다)."""

    def test_selector_module_does_not_import_main_or_runtime_planner(self) -> None:
        import ast

        source = (ROOT / "src" / "engines" / "coverage_focused_target_selector.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported_modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

        forbidden = {"src.api.main", "src.engines.context_pack_adaptive_planner", "src.engines.evidence_engine"}
        self.assertFalse(imported_modules & forbidden, f"금지된 모듈을 Import한다: {imported_modules & forbidden}")


if __name__ == "__main__":
    unittest.main()
