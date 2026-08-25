"""42개 대표 전공군 초안(`data/canonical_major_groups.draft.jsonl`) Loader·Audit
테스트 — A-2 지시서(integration/academyinfo-pipeline, 2026-08-24) §1/§4.

**이 42개는 "검증된 추천 전공"이 아니라 "분류 후보 Ontology"다.** 이 테스트는 그
경계가 실제로 지켜지는지(예체능 전공군이 분류에는 있지만 추천 정본에는 아직 없는지,
기존 10개/3개 정본이 이 라운드에서 전혀 바뀌지 않았는지)까지 확인한다."""

from __future__ import annotations

import gzip
import json
import subprocess
from pathlib import Path

from pydantic import ValidationError
import unittest

from src.data_sources.academyinfo_codes import UNCLASSIFIED_MIDDLE_SERIES, UNCLASSIFIED_SMALL_SERIES
from src.schemas.canonical_major_group import CanonicalMajorGroupDraft
from src.services.canonical_major_group_draft_loader import (
    DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH,
    load_canonical_major_groups_draft,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_ARTS_SPORTS_CANONICAL_MAJOR_IDS = frozenset(
    {"fine_arts_design", "music", "performing_media_arts", "sports_dance"}
)


def _load_official_small_series_codes(survey_year: int = 2025) -> set[str]:
    path = _REPO_ROOT / "data" / "academyinfo_raw" / str(survey_year) / "codes" / "getCodeBySmallSeries.jsonl.gz"
    codes: set[str] = set()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            codes.add(json.loads(line)["cdid"])
    return codes


class LoaderTest(unittest.TestCase):
    def test_default_path_exists_and_loads(self) -> None:
        self.assertTrue(DEFAULT_CANONICAL_MAJOR_GROUPS_DRAFT_PATH.exists())
        groups = load_canonical_major_groups_draft()
        self.assertEqual(len(groups), 42)
        for g in groups:
            self.assertIsInstance(g, CanonicalMajorGroupDraft)

    def test_missing_file_returns_empty_list_not_error(self) -> None:
        self.assertEqual(load_canonical_major_groups_draft(Path("/no/such/file.jsonl")), [])


class ExactlyFortyTwoGroupsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = load_canonical_major_groups_draft()

    def test_exactly_42(self) -> None:
        self.assertEqual(len(self.groups), 42)

    def test_no_duplicate_canonical_major_id(self) -> None:
        ids = [g.canonical_major_id for g in self.groups]
        self.assertEqual(len(ids), len(set(ids)), f"중복 canonical_major_id: {[i for i in ids if ids.count(i) > 1]}")

    def test_no_duplicate_label(self) -> None:
        labels = [g.label for g in self.groups]
        self.assertEqual(len(labels), len(set(labels)), f"중복 label: {[l for l in labels if labels.count(l) > 1]}")

    def test_no_small_series_code_assigned_to_two_groups(self) -> None:
        owner: dict[str, str] = {}
        conflicts: list[tuple[str, str, str]] = []
        for g in self.groups:
            for code in g.included_official_small_series_codes:
                if code in owner and owner[code] != g.canonical_major_id:
                    conflicts.append((code, owner[code], g.canonical_major_id))
                owner[code] = g.canonical_major_id
        self.assertEqual(conflicts, [], f"소계열 코드가 두 전공군에 배정됨: {conflicts}")

    def test_only_official_small_series_codes_used(self) -> None:
        official = _load_official_small_series_codes()
        used: set[str] = set()
        for g in self.groups:
            used.update(g.included_official_small_series_codes)
            used.update(g.excluded_series_codes)
        unknown = used - official
        self.assertEqual(unknown, set(), f"공식 코드표에 없는 소계열 코드 사용: {unknown}")

    def test_nce_small_series_999_never_included_as_a_real_group_member(self) -> None:
        self.assertEqual(UNCLASSIFIED_SMALL_SERIES, "999")
        for g in self.groups:
            self.assertNotIn(
                UNCLASSIFIED_SMALL_SERIES, g.included_official_small_series_codes,
                f"{g.canonical_major_id}가 N.C.E(999)를 일반 전공군 코드로 포함함",
            )

    def test_nce_middle_series_99_never_used_as_a_hint(self) -> None:
        self.assertEqual(UNCLASSIFIED_MIDDLE_SERIES, "99")
        for g in self.groups:
            self.assertNotIn(
                UNCLASSIFIED_MIDDLE_SERIES, g.middle_series_hint,
                f"{g.canonical_major_id}가 N.C.E(99)를 중계열 힌트로 사용함",
            )

    def test_description_not_blank(self) -> None:
        for g in self.groups:
            self.assertTrue(g.description.strip(), f"{g.canonical_major_id}의 description이 비어 있음")

    def test_official_source_urls_present(self) -> None:
        for g in self.groups:
            self.assertGreater(len(g.official_source_urls), 0, f"{g.canonical_major_id}에 official_source_urls 없음")

    def test_all_review_status_are_draft(self) -> None:
        for g in self.groups:
            self.assertEqual(g.review_status, "draft", f"{g.canonical_major_id}가 draft가 아님: {g.review_status}")


class ArtsAndSportsGroupsTest(unittest.TestCase):
    """A 결정사항 §1 "예체능 전공군도 분류 Ontology에는 보존" + "추천 노출 대상에서는
    제외"를 동시에 확인한다 — 두 요구가 서로 모순돼 보이지만 실제로는 "분류에는 있고
    추천 정본에는 없다"는 하나의 상태를 가리킨다."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.groups = load_canonical_major_groups_draft()
        cls.groups_by_id = {g.canonical_major_id: g for g in cls.groups}

    def test_arts_and_sports_groups_exist_in_classification_ontology(self) -> None:
        missing = _ARTS_SPORTS_CANONICAL_MAJOR_IDS - set(self.groups_by_id)
        self.assertEqual(missing, set(), f"예체능 전공군이 분류 초안에서 빠짐: {missing}")
        for major_id in _ARTS_SPORTS_CANONICAL_MAJOR_IDS:
            self.assertEqual(self.groups_by_id[major_id].review_status, "draft")

    def test_arts_and_sports_groups_not_in_recommendation_canonical_majors(self) -> None:
        """`data/master/canonical_majors.jsonl`(실제 추천에 쓰이는 10개 정본)에 예체능
        전공군 canonical_major_id가 아직 자동으로 들어가지 않았는지 확인한다."""

        promoted_ids: set[str] = set()
        path = _REPO_ROOT / "data" / "master" / "canonical_majors.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            promoted_ids.add(row.get("major_id") or row.get("canonical_major_id"))
        leaked = _ARTS_SPORTS_CANONICAL_MAJOR_IDS & promoted_ids
        self.assertEqual(leaked, set(), f"예체능 전공군이 추천 정본에 이미 들어감: {leaked}")

    def test_arts_and_sports_groups_not_in_vertical_slice_major_profiles(self) -> None:
        """`data/master/major_profiles_v2.jsonl`(실제 매칭 엔진이 계산하는 정본 —
        2026-08-25 a/major-profiles-v2-38 이후 39개)에도 예체능 전공군이 없는지
        확인한다."""

        promoted_ids: set[str] = set()
        path = _REPO_ROOT / "data" / "master" / "major_profiles_v2.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            promoted_ids.add(row.get("major_id"))
        leaked = _ARTS_SPORTS_CANONICAL_MAJOR_IDS & promoted_ids
        self.assertEqual(leaked, set(), f"예체능 전공군이 major_profiles_v2에 이미 들어감: {leaked}")


class ExistingMasterFilesUnchangedTest(unittest.TestCase):
    """기존 `data/master/canonical_majors.jsonl`(10개)이 이 브랜치(Canonical Major
    Group Draft 라운드)에서 조금도 바뀌지 않았는지 이 Repo의 기준 커밋(HEAD)과
    직접 `git diff`로 비교해 확인한다 — 줄 개수만 세는 것보다 엄격하다(내용이
    바뀌고 줄 수만 같은 경우도 잡는다).

    2026-08-25 갱신(a/major-profiles-v2-38 병합) — `major_profiles_v2.jsonl`
    (당시 3개)은 그 후속 작업이 39개 Service Catalog 전체로 정당하게 확장하는
    파일이다(§2 "3개 고정 구조를 제거하고 39개 Profile을 자동 로드"). 그래서 이
    파일의 "무변경" 검사는 더 이상 여기 두지 않는다 — 대신
    `tests/test_service_major_profiles_v2.py`가 39개·Catalog 1:1 일치라는 그
    라운드의 실제 새 불변식을 고정한다."""

    def _assert_unchanged_since_head(self, relative_path: str) -> None:
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", relative_path],
            cwd=_REPO_ROOT, capture_output=True, text=True,
        )
        self.assertEqual(
            result.returncode, 0,
            f"{relative_path}가 HEAD 대비 변경됨(이 라운드에서는 무변경이어야 한다):\n{result.stdout}",
        )

    def test_canonical_majors_jsonl_unchanged(self) -> None:
        path = _REPO_ROOT / "data" / "master" / "canonical_majors.jsonl"
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 10)
        self._assert_unchanged_since_head("data/master/canonical_majors.jsonl")

    def test_departments_jsonl_unchanged(self) -> None:
        """A 결정사항 §1 "현재 시연 Master 35개 유지" — 이 Canonical Major Group
        Draft 라운드 자체가 그 원칙을 지켰는지 확인하던 테스트였다. 2026-08-25
        전국 학과 1,072건 Production Master 전환(a/national-master-promotion-
        final-wiring)이 별도로, 의도적으로 Master를 교체했다 — 옛 35건은
        data/archive/departments_legacy_demo_35.jsonl로 보존됐다. git diff
        무변경 확인은 더 이상 의미가 없어 제거하고, 행 수만 실제 전국 기준값으로
        갱신한다."""

        path = _REPO_ROOT / "data" / "master" / "departments.jsonl"
        lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(lines), 1072)


class SchemaValidationRejectsBadRowsTest(unittest.TestCase):
    """Schema 자체가 실제로 뭔가를 거부하는지(항상 통과만 시키는 껍데기가 아닌지)
    확인한다."""

    _base = {
        "canonical_major_id": "x", "label": "x", "description": "x",
        "included_official_small_series_codes": ["001"], "middle_series_hint": ["01"],
        "boundary_cases": [], "excluded_series_codes": [], "official_source_urls": ["https://example.go.kr"],
        "classification_basis": "x", "review_status": "draft",
    }

    def test_empty_description_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorGroupDraft.model_validate({**self._base, "description": "   "})

    def test_empty_official_source_urls_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorGroupDraft.model_validate({**self._base, "official_source_urls": []})

    def test_empty_included_codes_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorGroupDraft.model_validate({**self._base, "included_official_small_series_codes": []})

    def test_invalid_review_status_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            CanonicalMajorGroupDraft.model_validate({**self._base, "review_status": "APPROVED_BY_MISTAKE"})


if __name__ == "__main__":
    unittest.main()
