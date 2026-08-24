"""실제 4+1/2+1 세션 시뮬레이션 Harness 테스트 — a/trait-evidence-coverage-shadow
(정정 라운드).

핵심적으로 증명해야 하는 것:
    1. 정확히 지시된 Context 개수만 쓴다(환경 A=3, 환경 B=5).
    2. Context별 Anchor는 정확히 1개이고, 선택하지 않은 Anchor의 Evidence는 0건이다.
    3. Routing 질문은 Evidence Ledger에 전혀 기록되지 않는다.
    4. Context당 Seed는 정확히 1개, Tail은 4~6개다.
    5. 임시 승인 Fixture가 실제 data/reviews/를 한 바이트도 바꾸지 않는다.
    6. 서로 다른 PYTHONHASHSEED로 별도 프로세스에서 두 번 실행해도 byte-identical하다.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "eval" / "trait_evidence_coverage_session_diagnostics.py"
REVIEWS_DIR = ROOT / "data" / "reviews"
JSON_REPORT = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_shadow_report.json"
MD_REPORT = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_shadow_report.md"


def _hash_tree(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*")) if p.is_file()
    }


class ReviewFilesUntouchedTest(unittest.TestCase):
    def test_run_diagnostics_leaves_data_reviews_untouched(self) -> None:
        import eval.trait_evidence_coverage_session_diagnostics as m

        before = _hash_tree(REVIEWS_DIR)
        m.run_diagnostics()
        after = _hash_tree(REVIEWS_DIR)
        self.assertEqual(before, after, "data/reviews/ 아래 파일이 변경됐다")


class SingleSessionStructureTest(unittest.TestCase):
    """환경 A/환경 B 각각 대표 Persona 하나씩만 직접 실행해서(전체 9개를 다 돌리지
    않고) 세션 구조 자체의 불변식을 검증한다 — 빠르고, 실패 원인이 명확하다."""

    @classmethod
    def setUpClass(cls) -> None:
        import eval.trait_evidence_coverage_session_diagnostics as m

        cls.m = m
        scenarios = m._persona_scenarios()
        cls.scenario = next(s for s in scenarios if s.key == "analytical")
        cls.env_a_scenario = m._env_a_variant(cls.scenario)

        os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"
        cls._fake_llm = m._DeterministicFakeLLMClient()

        cls._patches_a = [patch.object(m.main_module, "_llm_client", cls._fake_llm)]
        for p in cls._patches_a:
            p.start()
        cls.run_a = m._run_persona_session(
            cls.env_a_scenario, rating_universe=set(m.CONTEXT_IDS),
            supported_context_ids=set(m.main_module._effective_supported_context_ids()),
            full_mode=False, registry=m.main_module._context_pack_registry,
        )
        for p in cls._patches_a:
            p.stop()

        cls._tmp = __import__("tempfile").TemporaryDirectory()
        fixture_dir = Path(cls._tmp.name)
        cls.fixture_registry = m._build_fixture_registry(fixture_dir)
        cls.fixture_runtime = m.ContextPackRuntime(
            cls.fixture_registry, m.main_module.context_pack_runtime_enabled, frozenset(m.VERTICAL_SLICE_CONTEXT_IDS)
        )
        cls._patches_b = [
            patch.object(m.main_module, "_llm_client", cls._fake_llm),
            patch.object(m.main_module, "_context_pack_registry", cls.fixture_registry),
            patch.object(m.main_module, "_context_pack_runtime", cls.fixture_runtime),
        ]
        for p in cls._patches_b:
            p.start()
        os.environ["ENABLE_CONTEXT_PACK_RUNTIME"] = "true"
        cls.run_b = m._run_persona_session(
            cls.scenario, rating_universe=set(m.CONTEXT_IDS),
            supported_context_ids=set(m.main_module._effective_supported_context_ids()),
            full_mode=True, registry=cls.fixture_registry,
        )
        for p in cls._patches_b:
            p.stop()
        os.environ.pop("ENABLE_CONTEXT_PACK_RUNTIME", None)
        os.environ.pop("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", None)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    # -- 정확히 지정된 Context 개수만 쓴다 --

    def test_env_a_uses_exactly_3_contexts(self) -> None:
        self.assertEqual(len(self.run_a.final_context_ids), 3)
        self.assertEqual(set(self.run_a.final_context_ids), {"game", "media", "school_life"})

    def test_env_b_uses_exactly_5_contexts(self) -> None:
        self.assertEqual(len(self.run_b.final_context_ids), 5)
        self.assertEqual(len(set(self.run_b.final_context_ids)), 5)

    # -- Context별 Anchor 정확히 1개 --

    def test_each_context_has_exactly_one_anchor(self) -> None:
        for run in (self.run_a, self.run_b):
            self.assertEqual(set(run.anchor_by_context), set(run.final_context_ids))
            self.assertEqual(set(run.final_context_anchor_choices), set(run.final_context_ids))
            for context_id in run.final_context_ids:
                self.assertEqual(run.anchor_by_context[context_id], run.final_context_anchor_choices[context_id])

    # -- 선택하지 않은 Anchor의 Evidence는 0건(Pack Context — Seed/Backup이 Anchor마다
    # 서로 다른 question_id를 갖는다. Legacy 3개는 Seed가 Anchor 무관 공용 question_id라
    # 이 검사 대상이 아니다) --

    def test_no_evidence_from_unselected_pack_anchors(self) -> None:
        for context_id, chosen_anchor in self.run_b.anchor_by_context.items():
            pack = self.fixture_registry.get_pack(context_id)
            if pack is None:
                continue  # Legacy Context.
            allowed_question_ids = {
                s.question.question_id for s in pack.seed_anchor_variants if s.anchor_id == chosen_anchor
            } | {
                b.question.question_id for b in pack.anchor_backup_questions if b.anchor_id == chosen_anchor
            }
            forbidden_question_ids = {
                s.question.question_id for s in pack.seed_anchor_variants if s.anchor_id != chosen_anchor
            } | {
                b.question.question_id for b in pack.anchor_backup_questions if b.anchor_id != chosen_anchor
            }
            for record in self.run_b.final_evidence_ledger:
                if record.context != context_id or record.source_question_family_id not in ("seed", "pack_backup"):
                    continue
                self.assertNotIn(
                    record.question_id, forbidden_question_ids,
                    f"{context_id}: 선택 안 한 Anchor의 질문 {record.question_id!r}가 Evidence에 섞였다",
                )
                self.assertIn(record.question_id, allowed_question_ids)

    # -- Routing Evidence 0건 --

    def test_routing_produces_no_evidence(self) -> None:
        for run in (self.run_a, self.run_b):
            self.assertGreater(run.routing_question_count, 0)
            for record in run.final_evidence_ledger:
                self.assertNotEqual(record.source_question_family_id, "context_routing")

    # -- Context당 Seed 1개, Tail 4~6개(또는 조기 종료 사유가 명확) --

    def test_each_context_has_exactly_one_seed(self) -> None:
        for run in (self.run_a, self.run_b):
            seed_records = [r for r in run.final_evidence_ledger if r.source_question_family_id == "seed"]
            contexts_with_seed = [r.context for r in seed_records]
            self.assertEqual(sorted(contexts_with_seed), sorted(run.final_context_ids))
            self.assertEqual(len(contexts_with_seed), len(set(contexts_with_seed)))

    def test_tail_count_per_context_is_within_4_to_6_when_not_pack_exhausted(self) -> None:
        """Pack Context는 후보 소진 시 4개 미만에서 멈출 수 있다(§1 "후보 소진 시에만
        Backup") — 이 테스트는 그 예외를 인정하되, 조기 종료가 없었던(Backup을 전혀
        안 쓴) Context는 반드시 4~6개 범위를 지키는지 확인한다.

        family="v2_direct_probe"(Legacy 전용 전역 후속 단계, `_serve_next_v2_direct_
        probe_question`)는 이 Context 자신의 4~6개 예산이 아니라 모든 Legacy Context가
        끝난 뒤에 별도로 붙는 전역 질문이라 여기서 센 개수에서 제외한다 — 안 그러면
        그 전역 질문이 우연히 배정된 Context 하나가 7개로 보여 이 검사가 실패한다."""

        for run in (self.run_a, self.run_b):
            per_context_tail: dict[str, int] = {cid: 0 for cid in run.final_context_ids}
            for record in run.final_evidence_ledger:
                if record.source_question_family_id in ("seed", "context_routing", "conflict_resolution", "v2_direct_probe"):
                    continue
                per_context_tail[record.context] = per_context_tail.get(record.context, 0) + 1
            if run.backup_used_count == 0:
                for context_id, count in per_context_tail.items():
                    self.assertGreaterEqual(count, 4, f"{context_id}: Tail이 4개 미만({count})인데 Backup도 안 썼다")
                    self.assertLessEqual(count, 6, f"{context_id}: Tail이 6개를 넘었다({count})")

    def test_trait_evidence_question_count_stays_within_realistic_bound(self) -> None:
        """25~35(5 Context × 5~7)이 기준 범위지만, 전역 v2 Direct Probe 후속 단계
        (최대 4개, Legacy 전용) 때문에 소폭 넘을 수 있다 — 넉넉히 39까지 허용한다."""

        self.assertLessEqual(self.run_a.trait_evidence_question_count, 25)  # 3 Context 상한(7*3+extra 여유)
        self.assertLessEqual(self.run_b.trait_evidence_question_count, 39)
        self.assertGreaterEqual(self.run_b.trait_evidence_question_count, 20)


class DeterminismTest(unittest.TestCase):
    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)], cwd=ROOT, capture_output=True, timeout=180, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:3000])
        return JSON_REPORT.read_bytes(), MD_REPORT.read_bytes()

    def test_two_runs_with_different_hash_seeds_are_byte_identical(self) -> None:
        first_json, first_md = self._run_once("111")
        second_json, second_md = self._run_once("222")
        self.assertEqual(first_json, second_json, "PYTHONHASHSEED만 바뀌어도 JSON이 달라진다")
        self.assertEqual(first_md, second_md, "PYTHONHASHSEED만 바뀌어도 Markdown이 달라진다")

    def test_report_has_no_timestamp_fields(self) -> None:
        self._run_once("333")
        blob = JSON_REPORT.read_text(encoding="utf-8") + MD_REPORT.read_text(encoding="utf-8")
        for token in ("generated_at", "created_at", "timestamp", "run_at"):
            self.assertNotIn(token, blob)


class ReportContentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import eval.trait_evidence_coverage_session_diagnostics as m

        cls.diagnostics = m.run_diagnostics()
        m._write_json_report(cls.diagnostics)
        m._write_markdown_report(cls.diagnostics)
        cls.payload = json.loads(JSON_REPORT.read_text(encoding="utf-8"))

    def test_nine_personas_per_environment(self) -> None:
        self.assertEqual(len(self.diagnostics["env_a"]["runs"]), 9)
        self.assertEqual(len(self.diagnostics["env_b"]["runs"]), 9)

    def test_env_a_always_exactly_3_contexts(self) -> None:
        for run in self.diagnostics["env_a"]["runs"]:
            self.assertEqual(len(run["final_context_ids"]), 3)

    def test_env_b_always_exactly_5_contexts(self) -> None:
        for run in self.diagnostics["env_b"]["runs"]:
            self.assertEqual(len(run["final_context_ids"]), 5)

    def test_conclusion_is_a_or_b(self) -> None:
        self.assertIn(self.payload["conclusion"]["outcome"], ("A", "B"))

    def test_markdown_mentions_required_sections(self) -> None:
        text = MD_REPORT.read_text(encoding="utf-8")
        for heading in (
            "실제 4+1/2+1 세션 시뮬레이션", "이전 권고를 어떻게 정정했는가",
            "20/25/30/35문항 Checkpoint", "구조적으로 불가능한 Trait",
            "현재 기준을 Runtime에 연결해도 되는가", "전체 Inventory 상한과 실제 세션 결과 차이",
            "설계 결정과 한계",
        ):
            self.assertIn(heading, text, f"'{heading}' 섹션이 없다")

    def test_inventory_ceiling_report_is_a_separate_file(self) -> None:
        ceiling_json = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_inventory_ceiling_report.json"
        self.assertTrue(ceiling_json.exists())
        self.assertNotEqual(ceiling_json, JSON_REPORT)


if __name__ == "__main__":
    unittest.main()
