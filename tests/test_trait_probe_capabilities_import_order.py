"""Import 순서 무관 KeyError 회귀 테스트 — 2026-08-24.

`src.api.main`을 `src.review_ui.app` 뒤에 깨끗한 Python 프로세스에서 Import하면
`trait_probe_capabilities_v2.py`가 `KeyError: 'art_design_seed_visual_appreciation_
blueprint'`로 죽던 결함의 회귀 테스트다. 원인: ContextPack Seed가 Legacy Seed와 같은
`question_family_id="seed"`를 쓰는데, `trait_probe_capabilities_v2.py`는 Legacy Seed
전용 정적 표(`_SEED_BLUEPRINT_CONTEXT`)로만 조회했다 — 그 표에 없는 blueprint_id가
먼저 등록돼 있으면(review_ui.app이 먼저 ContextPackRegistry를 만든 경우) KeyError.

이 파일의 모든 테스트는 `subprocess`로 별도 Python 프로세스를 띄운다 — 현재 테스트
러너 프로세스는 이미 `unittest discover`가 다른 테스트 파일들을 통해 여러 모듈을
Import해 놓은 상태라 `sys.modules` 캐시가 오염돼 있으므로, 그 상태를 재사용하면 이
버그가 애초에 재현되지 않는다(그래서 원래 이 결함이 기존 테스트 스위트에서 걸러지지
않았다)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

_SNAPSHOT_SCRIPT = """
import importlib
import json
import sys

order = {order!r}
for mod in order:
    importlib.import_module(mod)

from src.services.trait_signal_registry import all_registrations
from src.data.trait_ontology.trait_probe_capabilities_v2 import (
    DIRECTLY_MEASURABLE_TRAIT_IDS,
    NOT_PROBED_TRAIT_IDS,
    OBSERVABLE_TRAIT_IDS,
    TRAIT_PROBE_CAPABILITIES,
)

regs = all_registrations()
total_signals = sum(len(v) for v in regs.values())

capabilities = {{
    trait_id: {{
        "blueprint_ids": sorted(cap.blueprint_ids),
        "context_ids": sorted(cap.context_ids),
        "frame_ids": sorted(cap.frame_ids),
        "primary_probe_count": cap.primary_probe_count,
        "related_probe_count": cap.related_probe_count,
    }}
    for trait_id, cap in TRAIT_PROBE_CAPABILITIES.items()
}}

pack_counts = {{}}
if "src.api.main" in sys.modules:
    pack_counts["main"] = len(sys.modules["src.api.main"]._context_pack_registry.all_packs())
if "src.review_ui.app" in sys.modules:
    pack_counts["review_ui"] = len(sys.modules["src.review_ui.app"]._context_pack_registry.all_packs())

print(json.dumps({{
    "registry_key_count": len(regs),
    "registry_signal_count": total_signals,
    "pack_counts": pack_counts,
    "directly_measurable": sorted(DIRECTLY_MEASURABLE_TRAIT_IDS),
    "observable_count": len(OBSERVABLE_TRAIT_IDS),
    "not_probed_count": len(NOT_PROBED_TRAIT_IDS),
    "capabilities": capabilities,
}}, ensure_ascii=False, sort_keys=True))
"""

_ORDERS: dict[str, list[str]] = {
    "main_alone": ["src.api.main"],
    "review_ui_alone": ["src.review_ui.app"],
    "review_ui_then_main": ["src.review_ui.app", "src.api.main"],
    "main_then_review_ui": ["src.api.main", "src.review_ui.app"],
}


def _run_clean_subprocess(code: str) -> subprocess.CompletedProcess[str]:
    """`sys.modules`를 절대 재사용하지 않는 완전히 새 프로세스에서 코드를 실행한다."""

    env = dict(os.environ)
    env["PYTHONPATH"] = str(_REPO_ROOT)
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _snapshot(order: list[str]) -> dict:
    result = _run_clean_subprocess(_SNAPSHOT_SCRIPT.format(order=order))
    if result.returncode != 0:
        raise AssertionError(
            f"Import 순서 {order!r} 스냅샷 실패 (exit={result.returncode}):\n{result.stderr}"
        )
    return json.loads(result.stdout)


class CleanImportSucceedsTest(unittest.TestCase):
    """§1 재현 — 4가지 조합 전부 깨끗한 프로세스에서 성공해야 한다(이전에는
    review_ui_then_main만 KeyError로 실패했다)."""

    def test_api_main_alone_succeeds(self) -> None:
        result = _run_clean_subprocess("import src.api.main")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_review_ui_app_alone_succeeds(self) -> None:
        result = _run_clean_subprocess("import src.review_ui.app")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_review_ui_then_api_main_succeeds(self) -> None:
        """수정 전 KeyError가 재현되던 정확한 순서."""

        result = _run_clean_subprocess("import src.review_ui.app\nimport src.api.main")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("KeyError", result.stderr)
        self.assertNotIn("art_design_seed_visual_appreciation_blueprint", result.stderr)

    def test_api_main_then_review_ui_app_succeeds(self) -> None:
        result = _run_clean_subprocess("import src.api.main\nimport src.review_ui.app")
        self.assertEqual(result.returncode, 0, result.stderr)


class DeterministicAcrossImportOrderTest(unittest.TestCase):
    """§4 "ContextPack 발견 개수(12) 동일"·"Registry Signal 개수 동일"·"중복 등록 없음" —
    네 조합 모두 최종 수렴 상태(Registry·TRAIT_PROBE_CAPABILITIES)가 완전히 같아야 한다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshots = {name: _snapshot(order) for name, order in _ORDERS.items()}

    def test_context_pack_discovery_count_is_12_everywhere(self) -> None:
        for name, snap in self.snapshots.items():
            for entrypoint, count in snap["pack_counts"].items():
                self.assertEqual(count, 12, f"{name}/{entrypoint}: Pack 발견 개수가 12가 아님 ({count})")

    def test_registry_signal_counts_identical_across_orders(self) -> None:
        key_counts = {name: snap["registry_key_count"] for name, snap in self.snapshots.items()}
        signal_counts = {name: snap["registry_signal_count"] for name, snap in self.snapshots.items()}
        self.assertEqual(len(set(key_counts.values())), 1, key_counts)
        self.assertEqual(len(set(signal_counts.values())), 1, signal_counts)

    def test_trait_probe_capabilities_byte_identical_across_orders(self) -> None:
        """이번 수정의 핵심 — 이전에는 review_ui_then_main만 죽었고, 만약 죽지 않게만
        고치고 계산값 자체가 순서에 따라 달라지면 "순서 무관" 요구를 만족하지 못한다."""

        serialized = {
            name: json.dumps(snap["capabilities"], ensure_ascii=False, sort_keys=True)
            for name, snap in self.snapshots.items()
        }
        distinct = set(serialized.values())
        self.assertEqual(len(distinct), 1, f"조합별로 TRAIT_PROBE_CAPABILITIES 값이 다름: {serialized.keys()}")

    def test_directly_measurable_and_observable_identical_across_orders(self) -> None:
        dm = {name: snap["directly_measurable"] for name, snap in self.snapshots.items()}
        observable = {name: snap["observable_count"] for name, snap in self.snapshots.items()}
        not_probed = {name: snap["not_probed_count"] for name, snap in self.snapshots.items()}
        first = next(iter(dm.values()))
        for name, value in dm.items():
            self.assertEqual(value, first, f"{name}: DIRECTLY_MEASURABLE_TRAIT_IDS가 다름")
        self.assertEqual(len(set(observable.values())), 1, observable)
        self.assertEqual(len(set(not_probed.values())), 1, not_probed)

    def test_no_duplicate_registration_inflates_signal_count(self) -> None:
        """review_ui_then_main/main_then_review_ui는 ContextPackRegistry를 프로세스
        하나에서 두 번(review_ui 것 + main 것) 만든다 — 멱등적으로 등록됐다면 그
        Signal 총량이 한 번만 만든 조합(main_alone/review_ui_alone)과 같아야 한다."""

        one_registry = self.snapshots["main_alone"]["registry_signal_count"]
        two_registries = self.snapshots["review_ui_then_main"]["registry_signal_count"]
        self.assertEqual(one_registry, two_registries)


class UnapprovedSignalGateUnaffectedTest(unittest.TestCase):
    """§3 "기존 Human Review Gate와 Fail-Closed 정책 유지" — 이번 수정은
    `trait_probe_capabilities_v2.py`(진단 전용, Shadow Mode)만 건드렸고
    `trait_signal_review_gate.py`(실제 Evidence 반영 여부를 결정하는 게이트)는 전혀
    손대지 않았다. 어떤 Import 순서에서도 그 경계가 그대로인지 확인한다."""

    def test_seed_family_still_requires_review_gate_regardless_of_import_order(self) -> None:
        script = """
import src.review_ui.app
import src.api.main
from src.services.trait_signal_review_gate import _ALWAYS_APPROVED_FAMILIES
assert "seed" not in _ALWAYS_APPROVED_FAMILIES, "seed가 무조건 승인 대상이 되면 안 된다"
assert "pack_backup" not in _ALWAYS_APPROVED_FAMILIES
assert "pack_direct_probe" not in _ALWAYS_APPROVED_FAMILIES
print("OK")
"""
        result = _run_clean_subprocess(script)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
