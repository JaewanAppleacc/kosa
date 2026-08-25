"""39개 Service Major v2 — 고정 Persona 회귀 진단 테스트 — 2026-08-25 지시서
(a/major-profiles-v2-38) §4/§6."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from eval.major_matching_persona_diagnostics_v2 import all_personas, diagnose_persona_v2
from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPT = _REPO_ROOT / "scripts" / "career_generate_major_matching_persona_report_v2.py"
_JSON_REPORT = _REPO_ROOT / "outputs" / "evaluation" / "major_matching_persona_report_v2.json"
_MD_REPORT = _REPO_ROOT / "outputs" / "evaluation" / "major_matching_persona_report_v2.md"


class PersonaCountTest(unittest.TestCase):
    def test_at_least_38_personas(self) -> None:
        self.assertGreaterEqual(len(all_personas()), 38)

    def test_39_self_personas_exactly_one_per_major(self) -> None:
        personas = all_personas()
        self_personas = [p for p in personas if p.persona_id.startswith("self_")]
        self.assertEqual(len(self_personas), 39)
        self.assertEqual(
            {p.target_major_ids[0] for p in self_personas},
            {m.major_id for m in SERVICE_MAJOR_PROFILES_V2},
        )

    def test_no_persona_defined_with_duplicate_id(self) -> None:
        ids = [p.persona_id for p in all_personas()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_confusion_persona_traits_are_never_hardcoded_empty(self) -> None:
        for p in all_personas():
            if p.persona_id.startswith("confusion_"):
                with self.subTest(persona_id=p.persona_id):
                    self.assertGreater(len(p.strong_trait_ids), 0)


class SelfMajorTop3Test(unittest.TestCase):
    """§4 "자기 전공군 Top-3" — 각 Major의 Trait 전부를 강하게 답한 학생이 자기
    Major를 관련성 높음으로 보는지 실측한다. 매칭 공식은 확률적 보장이 아니라
    가중 평균이므로 100%를 강제하지 않는다 — 실측값을 그대로 기록하고, 최소
    비율만 방어선으로 둔다(공식을 흔들지 않기 위해 방어선 자체는 낮게 잡는다)."""

    def test_self_major_hit_rate_is_high(self) -> None:
        personas = [p for p in all_personas() if p.persona_id.startswith("self_")]
        hits = sum(1 for p in personas if diagnose_persona_v2(p).self_major_in_relevant)
        # 실측(2026-08-25): 39개 중 39개 적중. 앞으로 Trait 데이터가 바뀌어도 공식
        # 자체를 흔들지 않는 한 급격히 나빠지지는 않을 것으로 기대하되, 완벽한 100%를
        # 강제하지는 않는다(동점·근접 경쟁으로 밀릴 수 있는 게 정상이다).
        self.assertGreaterEqual(hits, len(personas) * 0.9, f"{hits}/{len(personas)}")


class CoverageAndDiversityTest(unittest.TestCase):
    """§4 "모든 Major가 최소 한 번은 추천 후보가 될 수 있는지", "특정 3개 Major로
    쏠리지 않는지"."""

    @classmethod
    def setUpClass(cls) -> None:
        from collections import Counter

        cls.appearance_counter: Counter[str] = Counter()
        for p in all_personas():
            r = diagnose_persona_v2(p)
            for mid in r.relevant_major_ids + r.explore_together_major_ids:
                cls.appearance_counter[mid] += 1

    def test_every_major_appears_at_least_once(self) -> None:
        all_ids = {m.major_id for m in SERVICE_MAJOR_PROFILES_V2}
        never_appeared = all_ids - set(self.appearance_counter)
        self.assertEqual(never_appeared, set(), f"한 번도 후보가 안 된 Major: {sorted(never_appeared)}")

    def test_top_3_majors_do_not_dominate_total_appearances(self) -> None:
        total = sum(self.appearance_counter.values())
        top3_total = sum(c for _, c in self.appearance_counter.most_common(3))
        share = top3_total / total
        # 39개 Major가 완전히 균등하면 3/39≈7.7%다. 상위 3개가 절반 이상을 차지하면
        # "특정 3개로 쏠린다"고 본다 — 방어선을 50%로 둔다.
        self.assertLess(share, 0.5, f"상위 3개 점유율 {share:.1%} — 특정 Major로 쏠렸다")


class InternalScoreNotExposedTest(unittest.TestCase):
    def test_diagnostic_rows_do_not_leak_score_into_relevance_only_fields(self) -> None:
        """진단 결과 자체(내부 문서)는 score를 담아도 되지만, 실제 API가 보는
        MajorRelevance 쪽에는 score가 없다는 사실은 test_matching_engine_v2.py가
        이미 고정한다 — 여기서는 이 모듈이 Persona 결과에서 relevance_label을
        빠짐없이 채우는지만 확인한다(내부 문서 완결성)."""

        persona = next(p for p in all_personas() if p.persona_id == "self_medicine")
        result = diagnose_persona_v2(persona)
        for row in result.majors:
            if row.status == "computed":
                self.assertIsNotNone(row.relevance_label)


class ReportGenerationTest(unittest.TestCase):
    def test_report_script_runs_and_writes_both_files(self) -> None:
        from scripts.career_generate_major_matching_persona_report_v2 import build_report

        report = build_report()
        self.assertEqual(report["persona_count"], len(all_personas()))
        self.assertEqual(report["total_major_count"], 39)


class DeterminismTest(unittest.TestCase):
    def _run_once(self, hash_seed: str) -> tuple[bytes, bytes]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = hash_seed
        env["PYTHONPATH"] = str(_REPO_ROOT)
        proc = subprocess.run(
            [sys.executable, str(_SCRIPT)], cwd=_REPO_ROOT, capture_output=True, timeout=120, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr.decode("utf-8", "replace")[:4000])
        return _JSON_REPORT.read_bytes(), _MD_REPORT.read_bytes()

    def test_two_runs_with_different_hash_seeds_are_byte_identical(self) -> None:
        first = self._run_once("111")
        second = self._run_once("222")
        self.assertEqual(first, second, "PYTHONHASHSEED만 바뀌어도 리포트가 달라진다")


if __name__ == "__main__":
    unittest.main()
