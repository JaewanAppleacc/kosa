"""Context Selection "선호 4개 + Contrast 1개" 정책 — 2026-08-24 지시서
(a/context-selection-4-plus-1).

`ENABLE_CONTEXT_SELECTION_4_PLUS_1` Feature Flag(기본값 false)로 전환하는 4+1 정책을
검증한다. Flag OFF에서는 기존 2+1 흐름이 완전히 그대로여야 하고(§9 회귀), Flag ON은
활성 Context가 최소 5개일 때만 쓸 수 있으며 부족하면 조용히 2+1로 축소하지 않고
Fail-Fast해야 한다(§2). 어떤 테스트도 실제 ContextPack 승인 상태(`data/reviews/`)를
건드리지 않는다 — Flag ON 시나리오는 `_effective_supported_context_ids()`를 순수
함수로 monkeypatch해서 만든다(12개 ContextPack을 실제로 활성화하지 않는다)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

import src.api.main as main_module
from src.api.main import app
from src.engines.contrast_context_selector import (
    CONTRAST_CONTEXT_COUNT_FULL_MODE,
    CONTRAST_CONTEXT_COUNT_VERTICAL_SLICE,
    COVERAGE_REPLACEMENT_ENABLED_FULL_MODE,
    COVERAGE_REPLACEMENT_ENABLED_VERTICAL_SLICE,
    MAXIMUM_FINAL_CONTEXT_COUNT_FULL_MODE,
    MAXIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE,
    MAXIMUM_PREFERRED_CONTEXT_COUNT_FULL_MODE,
    MAXIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE,
    MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1,
    MINIMUM_FINAL_CONTEXT_COUNT_FULL_MODE,
    MINIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE,
    MINIMUM_PREFERRED_CONTEXT_COUNT_FULL_MODE,
    MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE,
    ContextSelectionConfigError,
    compute_context_selection_policy,
)
from src.services.feature_flags import context_selection_4_plus_1_enabled

ROOT = Path(__file__).resolve().parents[1]
FLAG = "ENABLE_CONTEXT_SELECTION_4_PLUS_1"
client = TestClient(app)

# Flag ON 테스트용 6개 활성 Context — 실제 ContextPack 승인 상태를 전혀 건드리지 않고
# `_effective_supported_context_ids()`만 monkeypatch한다(12개 ContextPack 자동
# 활성화 금지, §"금지"). 6개를 쓰는 이유: "5개 미만이면 Fail-Fast" 경계뿐 아니라
# "6개 이상 거부"(최종 확정 상한 5)도 같은 Fixture로 검증하기 위해서다.
_FIXTURE_SUPPORTED = ["game", "media", "school_life", "sports", "business", "art_design"]


def _fixture_supported_ids() -> list[str]:
    return list(_FIXTURE_SUPPORTED)


class FeatureFlagDefaultTest(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop(FLAG, None)

    def test_default_is_false(self) -> None:
        self.assertFalse(context_selection_4_plus_1_enabled())

    def test_explicit_true_values(self) -> None:
        for value in ("1", "true", "True", "yes"):
            self.assertTrue(context_selection_4_plus_1_enabled({FLAG: value}), value)

    def test_explicit_false_values(self) -> None:
        for value in ("0", "false", "", "no"):
            self.assertFalse(context_selection_4_plus_1_enabled({FLAG: value}), value)


class ComputePolicyPureFunctionTest(unittest.TestCase):
    """§1 — Flag OFF/ON 정책표. Feature Flag와 활성 Context 수만으로 결정론적이다."""

    def test_flag_off_returns_2_plus_1(self) -> None:
        policy = compute_context_selection_policy(flag_enabled=False, effective_supported_context_count=3)
        self.assertEqual(policy.preferred_context_min_count, 2)
        self.assertEqual(policy.preferred_context_max_count, 2)
        self.assertEqual(policy.contrast_context_count, 1)
        self.assertEqual(policy.final_context_min_count, 2)
        self.assertEqual(policy.final_context_max_count, 3)
        self.assertFalse(policy.coverage_replacement_enabled)

    def test_flag_off_ignores_active_context_count(self) -> None:
        """Flag OFF면 활성 Context가 몇 개든(심지어 5개 미만이어도) 절대 실패하지 않는다."""

        policy = compute_context_selection_policy(flag_enabled=False, effective_supported_context_count=0)
        self.assertEqual(policy.preferred_context_min_count, 2)

    def test_flag_on_with_5_active_returns_4_plus_1(self) -> None:
        policy = compute_context_selection_policy(flag_enabled=True, effective_supported_context_count=5)
        self.assertEqual(policy.preferred_context_min_count, 4)
        self.assertEqual(policy.preferred_context_max_count, 4)
        self.assertEqual(policy.contrast_context_count, 1)
        self.assertEqual(policy.final_context_min_count, 4)
        self.assertEqual(policy.final_context_max_count, 5)
        self.assertFalse(policy.coverage_replacement_enabled)

    def test_flag_on_with_more_than_5_active_still_returns_4_plus_1(self) -> None:
        policy = compute_context_selection_policy(flag_enabled=True, effective_supported_context_count=15)
        self.assertEqual(policy.preferred_context_min_count, 4)
        self.assertEqual(policy.final_context_max_count, 5)

    def test_flag_on_with_4_active_fails_closed(self) -> None:
        """§2 — 활성 Context 5개 미만이면 조용히 2+1로 축소하지 않고 Fail-Fast한다."""

        with self.assertRaises(ContextSelectionConfigError):
            compute_context_selection_policy(flag_enabled=True, effective_supported_context_count=4)

    def test_flag_on_with_0_active_fails_closed(self) -> None:
        with self.assertRaises(ContextSelectionConfigError):
            compute_context_selection_policy(flag_enabled=True, effective_supported_context_count=0)

    def test_boundary_constant_is_5(self) -> None:
        self.assertEqual(MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1, 5)

    def test_full_mode_constants_match_policy_table(self) -> None:
        self.assertEqual(MINIMUM_PREFERRED_CONTEXT_COUNT_FULL_MODE, 4)
        self.assertEqual(MAXIMUM_PREFERRED_CONTEXT_COUNT_FULL_MODE, 4)
        self.assertEqual(CONTRAST_CONTEXT_COUNT_FULL_MODE, 1)
        self.assertEqual(MINIMUM_FINAL_CONTEXT_COUNT_FULL_MODE, 4)
        self.assertEqual(MAXIMUM_FINAL_CONTEXT_COUNT_FULL_MODE, 5)
        self.assertFalse(COVERAGE_REPLACEMENT_ENABLED_FULL_MODE)

    def test_vertical_slice_constants_unchanged(self) -> None:
        """이 지시서가 기존 상수를 절대 건드리지 않았다는 증거."""

        self.assertEqual(MINIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE, 2)
        self.assertEqual(MAXIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE, 2)
        self.assertEqual(CONTRAST_CONTEXT_COUNT_VERTICAL_SLICE, 1)
        self.assertEqual(MINIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE, 2)
        self.assertEqual(MAXIMUM_FINAL_CONTEXT_COUNT_VERTICAL_SLICE, 3)
        self.assertFalse(COVERAGE_REPLACEMENT_ENABLED_VERTICAL_SLICE)


class AppStartupFailFastTest(unittest.TestCase):
    """§2 — 앱 시작 시점에 Fail-Fast한다(학생 요청 중간이 아니라). 실제 서브프로세스로
    `import src.api.main`을 실행해 검증한다 — Flag ON + 기본 활성 Context(3개, ==
    VERTICAL_SLICE_CONTEXT_IDS, ENABLE_CONTEXT_PACK_RUNTIME은 건드리지 않아 여전히
    OFF)에서는 반드시 앱 자체가 뜨지 않아야 한다."""

    def _import_in_subprocess(self, env_overrides: dict[str, str]) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        for key in ("ENABLE_CONTEXT_SELECTION_4_PLUS_1", "ENABLE_CONTEXT_PACK_RUNTIME"):
            env.pop(key, None)
        env.update(env_overrides)
        return subprocess.run(
            [sys.executable, "-c", "import src.api.main"],
            cwd=ROOT, capture_output=True, text=True, timeout=60, env=env,
        )

    def test_flag_off_app_starts_normally(self) -> None:
        result = self._import_in_subprocess({})
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])

    def test_flag_on_without_enough_active_contexts_crashes_at_import(self) -> None:
        result = self._import_in_subprocess({"ENABLE_CONTEXT_SELECTION_4_PLUS_1": "true"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ContextSelectionConfigError", result.stderr)
        # 12개 ContextPack을 자동 승인·활성화하지 않는다 — 앱이 죽는 이유가 "그래도 3개뿐"
        # 이라는 사실이 오류 메시지에 그대로 드러나야 한다.
        self.assertIn("3개", result.stderr)


class FlagOffFullRegressionTest(unittest.TestCase):
    """§ 필수 테스트 "Flag OFF 기존 2+1 완전 회귀"."""

    def setUp(self) -> None:
        os.environ.pop(FLAG, None)

    def test_get_contexts_selection_policy_unchanged(self) -> None:
        body = client.get("/contexts").json()
        policy = body["selection_policy"]
        self.assertEqual(policy["preferred_context_min_count"], 2)
        self.assertEqual(policy["preferred_context_max_count"], 2)
        self.assertEqual(policy["contrast_context_count"], 1)
        self.assertEqual(policy["final_context_min_count"], 2)
        self.assertEqual(policy["final_context_max_count"], 3)
        self.assertFalse(policy["coverage_replacement_enabled"])
        # §3 — 새 필드를 임의로 추가하지 않는다.
        self.assertEqual(
            set(policy.keys()),
            {
                "preferred_context_min_count", "preferred_context_max_count", "contrast_context_count",
                "final_context_min_count", "final_context_max_count", "coverage_replacement_enabled",
            },
        )

    def test_full_e2e_2_select_1_contrast_2_or_3_confirm(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 3}},
        )
        select_body = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        ).json()
        self.assertIn("contrast_context_id", select_body)
        self.assertEqual(select_body["contrast_context_id"], "school_life")

        # 선호 2개만 확정(Contrast 거절) — 기존처럼 허용.
        confirm2 = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media"]},
        )
        self.assertEqual(confirm2.status_code, 200)
        self.assertEqual(len(confirm2.json()["final_context_ids"]), 2)

    def test_full_e2e_3_confirm_with_contrast_accepted(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 3}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        confirm3 = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(confirm3.status_code, 200)
        self.assertEqual(len(confirm3.json()["final_context_ids"]), 3)

    def test_1_context_confirm_still_rejected(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        confirm = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game"]},
        )
        self.assertEqual(confirm.status_code, 422)

    def test_4_context_confirm_still_rejected_when_flag_off(self) -> None:
        """4+1 정책의 5개 확정을 Flag OFF에서는 여전히 거부해야 한다(4는 3 초과)."""

        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 3}},
        )
        client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"]},
        )
        confirm = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life", "game"]},
        )
        # 중복(game 두 번)이라 구조 검증에서도 걸리지만, 개수 상한(3) 자체도 이미 넘는다.
        self.assertEqual(confirm.status_code, 422)

    def test_3_preferred_context_select_still_rejected(self) -> None:
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5, "school_life": 3}},
        )
        select = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(select.status_code, 422)


class _FlagOnTestBase(unittest.TestCase):
    """Flag ON + 6개 활성 Context Fixture(실제 ContextPack 승인 상태 무변경)."""

    def setUp(self) -> None:
        os.environ[FLAG] = "true"
        self.addCleanup(os.environ.pop, FLAG, None)
        patcher = patch.object(main_module, "_effective_supported_context_ids", _fixture_supported_ids)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _new_session_with_ratings(self, ratings: dict[str, int]) -> str:
        session_id = client.post("/assessment/session").json()["session_id"]
        r = client.post("/assessment/interest-rating", json={"session_id": session_id, "ratings": ratings})
        self.assertEqual(r.status_code, 200, r.text)
        return session_id

    def _select_4(self, session_id: str, preferred: list[str]) -> dict:
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": preferred},
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()


class FlagOnGetContextsTest(_FlagOnTestBase):
    def test_selection_policy_is_4_plus_1(self) -> None:
        body = client.get("/contexts").json()
        policy = body["selection_policy"]
        self.assertEqual(policy["preferred_context_min_count"], 4)
        self.assertEqual(policy["preferred_context_max_count"], 4)
        self.assertEqual(policy["contrast_context_count"], 1)
        self.assertEqual(policy["final_context_min_count"], 4)
        self.assertEqual(policy["final_context_max_count"], 5)
        self.assertFalse(policy["coverage_replacement_enabled"])
        # 새 필드 추가 금지 — Flag ON에서도 같은 6개 키만 있어야 한다.
        self.assertEqual(
            set(policy.keys()),
            {
                "preferred_context_min_count", "preferred_context_max_count", "contrast_context_count",
                "final_context_min_count", "final_context_max_count", "coverage_replacement_enabled",
            },
        )


class FlagOnSelectExactly4Test(_FlagOnTestBase):
    """§4 — Flag ON: 정확히 4개, 모두 assessment_supported=true, 모두 관심도 입력 완료."""

    def test_exactly_4_accepted(self) -> None:
        session_id = self._new_session_with_ratings({c: 4 for c in _FIXTURE_SUPPORTED})
        body = self._select_4(session_id, ["game", "media", "school_life", "sports"])
        self.assertIn("contrast_context_id", body)

    def test_3_rejected(self) -> None:
        session_id = self._new_session_with_ratings({c: 4 for c in _FIXTURE_SUPPORTED})
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_5_rejected(self) -> None:
        session_id = self._new_session_with_ratings({c: 4 for c in _FIXTURE_SUPPORTED})
        r = client.post(
            "/assessment/context-select",
            json={
                "session_id": session_id,
                "selected_preferred_context_ids": ["game", "media", "school_life", "sports", "business"],
            },
        )
        self.assertEqual(r.status_code, 422)

    def test_unsupported_context_rejected(self) -> None:
        """등록은 됐지만 Fixture 6개(assessment_supported=true) 밖의 Context."""

        session_id = self._new_session_with_ratings({c: 4 for c in _FIXTURE_SUPPORTED} | {"cooking": 4})
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media", "school_life", "cooking"]},
        )
        self.assertEqual(r.status_code, 422)
        self.assertIn("cooking", r.json()["detail"]["message"])

    def test_not_rated_context_rejected(self) -> None:
        # 4개(관심도 최소 개수 통과)를 매기되 "sports"는 빼서, context-select 단계의
        # "관심도 미입력" 검증이 실제로 걸리는지 확인한다.
        session_id = self._new_session_with_ratings({"game": 4, "media": 4, "school_life": 4, "business": 4})
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media", "school_life", "sports"]},
        )
        self.assertEqual(r.status_code, 422)
        self.assertIn("sports", r.json()["detail"]["message"])

    def test_duplicate_context_rejected(self) -> None:
        session_id = self._new_session_with_ratings({c: 4 for c in _FIXTURE_SUPPORTED})
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_interest_rating_below_4_rejected(self) -> None:
        """§ 필수 테스트 "관심도 미입력 Context 거부"의 상위 단계 — 4+1에서는
        관심도 평가 자체도 최소 4개 이상 있어야 한다."""

        session_id = client.post("/assessment/session").json()["session_id"]
        r = client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 4, "media": 4, "school_life": 4}},
        )
        self.assertEqual(r.status_code, 422)


class FlagOnContrastTest(_FlagOnTestBase):
    """§5 — Contrast Context 1개 제안, 결정론적, 하드코딩 없음, 선택한 4개 재등장 금지."""

    def test_exactly_1_contrast_proposed_and_not_among_preferred(self) -> None:
        session_id = self._new_session_with_ratings({c: 3 for c in _FIXTURE_SUPPORTED})
        preferred = ["game", "media", "school_life", "sports"]
        body = self._select_4(session_id, preferred)
        self.assertNotIn(body["contrast_context_id"], preferred)
        self.assertIn(body["contrast_context_id"], _FIXTURE_SUPPORTED)

    def test_deterministic_same_input_same_output(self) -> None:
        ratings = {c: 3 for c in _FIXTURE_SUPPORTED}
        preferred = ["game", "media", "school_life", "sports"]
        session_a = self._new_session_with_ratings(ratings)
        body_a = self._select_4(session_a, preferred)
        session_b = self._new_session_with_ratings(ratings)
        body_b = self._select_4(session_b, preferred)
        self.assertEqual(body_a["contrast_context_id"], body_b["contrast_context_id"])
        self.assertEqual(body_a["contrast_reason"], body_b["contrast_reason"])

    def test_selector_does_not_hardcode_context_names(self) -> None:
        """§5 "Context 이름을 조건문으로 하드코딩하지 않음" — 소스에 개별 Context id를
        분기 조건으로 하드코딩한 흔적이 없는지 정적으로도 확인한다(select_contrast_
        context 자체는 순수 공식 기반이라 기존 §5-1/§6-5 구현을 그대로 재사용했다)."""

        src = (ROOT / "src" / "engines" / "contrast_context_selector.py").read_text(encoding="utf-8")
        for forbidden in ('== "game"', '== "media"', '== "school_life"', '== "sports"', '== "business"'):
            self.assertNotIn(forbidden, src)


class FlagOnConfirmTest(_FlagOnTestBase):
    """§6 — Flag ON: 선호 4개만 또는 4+Contrast 5개만 확정 가능, 3개 이하·6개 이상 거부,
    선호하지 않은 임의의 Context를 다섯 번째로 추가 금지."""

    def _prepared_session(self, preferred=("game", "media", "school_life", "sports")) -> tuple[str, str]:
        session_id = self._new_session_with_ratings({c: 3 for c in _FIXTURE_SUPPORTED})
        body = self._select_4(session_id, list(preferred))
        return session_id, body["contrast_context_id"]

    def test_exactly_4_preferred_confirm_allowed(self) -> None:
        session_id, _ = self._prepared_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life", "sports"]},
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(len(r.json()["final_context_ids"]), 4)

    def test_5_with_accepted_contrast_confirm_allowed(self) -> None:
        session_id, contrast_id = self._prepared_session()
        final = ["game", "media", "school_life", "sports", contrast_id]
        r = client.post("/assessment/context-confirm", json={"session_id": session_id, "final_context_ids": final})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(set(r.json()["final_context_ids"]), set(final))

    def test_3_rejected(self) -> None:
        session_id, _ = self._prepared_session()
        r = client.post(
            "/assessment/context-confirm",
            json={"session_id": session_id, "final_context_ids": ["game", "media", "school_life"]},
        )
        self.assertEqual(r.status_code, 422)

    def test_6_rejected(self) -> None:
        session_id, contrast_id = self._prepared_session()
        remaining = [c for c in _FIXTURE_SUPPORTED if c not in ("game", "media", "school_life", "sports", contrast_id)]
        sixth = remaining[0]
        final = ["game", "media", "school_life", "sports", contrast_id, sixth]
        r = client.post("/assessment/context-confirm", json={"session_id": session_id, "final_context_ids": final})
        self.assertEqual(r.status_code, 422)

    def test_arbitrary_non_preferred_non_contrast_context_rejected_as_fifth(self) -> None:
        """§6 핵심 — 선호하지 않은 임의의(하지만 지원·평가는 된) Context를 다섯 번째로
        끼워 넣을 수 없다. 이 Context는 제안된 Contrast가 아니라는 점이 핵심이다."""

        session_id, contrast_id = self._prepared_session()
        arbitrary = next(c for c in _FIXTURE_SUPPORTED if c not in ("game", "media", "school_life", "sports", contrast_id))
        final = ["game", "media", "school_life", "sports", arbitrary]
        r = client.post("/assessment/context-confirm", json={"session_id": session_id, "final_context_ids": final})
        self.assertEqual(r.status_code, 422)
        self.assertIn("다섯 번째", r.json()["detail"]["message"])

    def test_replacing_one_preferred_context_rejected(self) -> None:
        """선호 4개 중 하나를 다른 Context로 바꿔치기한 4개 조합도 거부돼야 한다
        (Flag ON에서는 "선호 4개 그대로"만 허용)."""

        session_id, _ = self._prepared_session()
        swapped = next(c for c in _FIXTURE_SUPPORTED if c not in ("game", "media", "school_life", "sports"))
        final = ["game", "media", "school_life", swapped]
        r = client.post("/assessment/context-confirm", json={"session_id": session_id, "final_context_ids": final})
        self.assertEqual(r.status_code, 422)


class PolicyMatchesActualValidationTest(unittest.TestCase):
    """§ 필수 테스트 "GET /contexts와 실제 검증 정책 일치" — 응답으로 받은 정책값이
    실제 Endpoint가 강제하는 값과 정확히 같은지, 경계값을 직접 보내서 확인한다."""

    def test_flag_off_max_boundary_matches_get_contexts(self) -> None:
        os.environ.pop(FLAG, None)
        policy = client.get("/contexts").json()["selection_policy"]
        session_id = client.post("/assessment/session").json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {"game": 5, "media": 5}},
        )
        # preferred_context_max_count(2)개는 통과해야 한다.
        r = client.post(
            "/assessment/context-select",
            json={"session_id": session_id, "selected_preferred_context_ids": ["game", "media"][: policy["preferred_context_max_count"]]},
        )
        self.assertEqual(r.status_code, 200)

    def test_flag_on_preferred_max_boundary_matches_get_contexts(self) -> None:
        os.environ[FLAG] = "true"
        self.addCleanup(os.environ.pop, FLAG, None)
        with patch.object(main_module, "_effective_supported_context_ids", _fixture_supported_ids):
            policy = client.get("/contexts").json()["selection_policy"]
            self.assertEqual(policy["preferred_context_max_count"], 4)
            session_id = client.post("/assessment/session").json()["session_id"]
            client.post(
                "/assessment/interest-rating",
                json={"session_id": session_id, "ratings": {c: 3 for c in _FIXTURE_SUPPORTED}},
            )
            r = client.post(
                "/assessment/context-select",
                json={
                    "session_id": session_id,
                    "selected_preferred_context_ids": _FIXTURE_SUPPORTED[: policy["preferred_context_max_count"]],
                },
            )
            self.assertEqual(r.status_code, 200, r.text)


class MockAndOpenApiDeterminismTest(unittest.TestCase):
    """§ 필수 테스트 "Mock/OpenAPI 결정론성 확인" — Flag OFF(기본값)에서는 공개 API/
    Mock을 전혀 바꾸지 않았다."""

    def test_openapi_schema_unchanged_from_head_for_context_endpoints(self) -> None:
        os.environ.pop(FLAG, None)
        schema = client.get("/openapi.json").json()
        policy_schema = schema["components"]["schemas"]["ContextSelectionPolicyResponse"]
        self.assertEqual(
            set(policy_schema["properties"].keys()),
            {
                "preferred_context_min_count", "preferred_context_max_count", "contrast_context_count",
                "final_context_min_count", "final_context_max_count", "coverage_replacement_enabled",
            },
        )

    def test_mock_api_outputs_unchanged_from_head(self) -> None:
        # 2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        # promotion-final-wiring) §7이 scripts/generate_mock_json.py를 다시 실행해
        # departments_normal.json·subgraph_normal.json을 의도적으로 새 Master 기준으로
        # 재생성했다(공개 OpenAPI Schema 자체는 byte-identical로 남아 있음을 별도로
        # 확인했다) — 이 4+1 Context 작업과 무관한 변경이라 diff 대상에서 뺀다.
        result = subprocess.run(
            [
                "git", "diff", "--exit-code", "HEAD", "--", "outputs/mock_api/",
                ":(exclude)outputs/mock_api/departments_normal.json",
                ":(exclude)outputs/mock_api/subgraph_normal.json",
            ],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, f"outputs/mock_api/ changed:\n{result.stdout}")


if __name__ == "__main__":
    unittest.main()
