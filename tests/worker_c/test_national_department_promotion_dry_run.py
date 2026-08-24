"""전국 학과 → Master 승격 Dry Run 계약 테스트 — c/national-master-promotion-dry-run.

`tests/worker_c/test_academyinfo_queue_clean_clone.py`의 패턴(Fail-Closed 입력 부재
검사, 실제 Builder subprocess 실행, byte-determinism)을 따르되, Gate 단위 검증은
`evaluate_department()`를 직접 호출해 빠르고 정확하게 확인한다 — 42개 Group·Bridge·
10개 Major는 지시서 §6이 요구한 실제 그룹 ID(`computer_science`/`media_communication`/
`industrial_engineering`/`business`)를 그대로 쓰는 합성 Fixture이고, 실제
`data/reviews/*` 파일은 어디서도 열거나 쓰지 않는다(전부 `tempfile.TemporaryDirectory()`
안에서만 만든다)."""

from __future__ import annotations

import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.career_build_national_department_promotion_dry_run import (  # noqa: E402
    DryRunInputs,
    MissingRequiredInputError,
    evaluate_department,
    load_inputs,
    read_jsonl,
)

_SCRIPT = ROOT / "scripts" / "career_build_national_department_promotion_dry_run.py"

# 지시서 §6이 요구한 4개 실제 Group. 코드는 실제 42개 Group Draft(2026-08-24)의 값과
# 같다(business=033/035/041/151/152, industrial_engineering=102/103/104) — 실제
# 데이터와 이 합성 Fixture가 같은 세계관을 쓰는지 눈으로 대조할 수 있게 한다.
_GROUP_CODES: dict[str, list[str]] = {
    "computer_science": ["089", "090", "157"],
    "media_communication": ["027", "038"],
    "industrial_engineering": ["102", "103", "104"],
    "business": ["033", "035", "041", "151", "152"],
}
_GROUP_TO_MAJOR: dict[str, str] = {
    "computer_science": "computer_science",
    "media_communication": "media_communication",
    "industrial_engineering": "industrial_engineering",
    "business": "business_administration",
}


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def _write_json_list(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


class _Universe:
    """합성 Fixture 하나(4개 Group·Bridge·Major·공식 소계열 코드표)의 경로 모음."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.group_draft_path = root / "canonical_major_groups.draft.jsonl"
        self.bridge_draft_path = root / "master" / "canonical_major_group_bridge.draft.jsonl"
        self.majors_path = root / "master" / "canonical_majors.jsonl"
        self.code_table_path = root / "academyinfo_raw" / "2025" / "codes" / "getCodeBySmallSeries.jsonl.gz"


def _build_universe(
    root: Path, *, approved_group_ids: frozenset[str] = frozenset(),
    scope_by_group: dict[str, tuple[str, list[str]]] | None = None,
) -> _Universe:
    """4개 Group·Bridge·Major·공식 소계열 코드표를 만든다.

    `scope_by_group`은 `{group_id: (scope_type, included_small_series_codes)}` —
    기본은 실제 데이터와 같은 값(computer_science/media_communication=FULL_GROUP,
    industrial_engineering=INCLUDED_SMALL_SERIES_ONLY[102],
    business=INCLUDED_SMALL_SERIES_ONLY[033])이다."""

    universe = _Universe(root)
    default_scope = {
        "computer_science": ("FULL_GROUP", []),
        "media_communication": ("FULL_GROUP", []),
        "industrial_engineering": ("INCLUDED_SMALL_SERIES_ONLY", ["102"]),
        "business": ("INCLUDED_SMALL_SERIES_ONLY", ["033"]),
    }
    scope_by_group = scope_by_group or default_scope

    groups = [
        {
            "canonical_major_id": group_id, "label": group_id, "description": f"{group_id} 설명",
            "included_official_small_series_codes": codes, "middle_series_hint": [],
            "boundary_cases": [], "excluded_series_codes": [], "official_source_urls": ["https://academyinfo.go.kr"],
            "classification_basis": "테스트 Fixture", "review_status": "approved" if group_id in approved_group_ids else "draft",
        }
        for group_id, codes in _GROUP_CODES.items()
    ]
    _write_jsonl(universe.group_draft_path, groups)

    bridge_rows = []
    for group_id, major_id in _GROUP_TO_MAJOR.items():
        scope_type, included = scope_by_group[group_id]
        bridge_rows.append(
            {
                "canonical_major_group_id": group_id, "canonical_major_id": major_id, "mapping_status": "EVIDENCED",
                "evidence": ["테스트 근거"], "decision_reason": "테스트 사유", "boundary_notes": "",
                "review_status": "draft", "reviewer_id": None, "reviewed_at": None,
                "scope_type": scope_type, "included_small_series_codes": included, "excluded_small_series_codes": [],
                "scope_decision_reason": "테스트 Scope 사유", "scope_review_status": "draft",
            }
        )
    _write_jsonl(universe.bridge_draft_path, bridge_rows)

    majors = [
        {
            "major_id": major_id, "label": major_id, "description": f"{major_id} 학생 설명 문장입니다.",
            "aliases": [], "keywords": [], "source_url": "https://academyinfo.go.kr", "as_of_date": "2025-01-01",
        }
        for major_id in sorted(set(_GROUP_TO_MAJOR.values()))
    ]
    _write_jsonl(universe.majors_path, majors)

    universe.code_table_path.parent.mkdir(parents=True, exist_ok=True)
    all_codes = sorted({code for codes in _GROUP_CODES.values() for code in codes})
    with gzip.open(universe.code_table_path, "wt", encoding="utf-8") as fh:
        for code in all_codes:
            fh.write(json.dumps({"cdid": code, "cdnm": f"소계열 {code}"}, ensure_ascii=False) + "\n")

    return universe


def _dept_row(
    department_id: str, *, department_name: str = "테스트학과", university_name: str = "테스트대학교",
    college_name: str = "테스트단과대학", department_status: str = "EXISTING",
    recommendation_scope: str = "IN_RECOMMENDATION_SCOPE", exclusion_reason: str | None = None,
    duplicate_group_size: int = 1, source_record_id: str | None = "src_test_0001",
    schl_id: str = "schl_test", source_schl_mjr_id: str | None = "mjr_test_0001", source_mjr_id: str | None = None,
) -> dict[str, Any]:
    return {
        "department_id": department_id, "university_name": university_name, "college_name": college_name,
        "department_name": department_name, "region": "서울", "department_status": department_status,
        "recommendation_scope": recommendation_scope, "exclusion_reason": exclusion_reason,
        "duplicate_group_size": duplicate_group_size, "source_record_id": source_record_id, "schl_id": schl_id,
        "source_schl_mjr_id": source_schl_mjr_id, "source_mjr_id": source_mjr_id, "source_svy_year": 2025,
        "source_url": "https://academyinfo.go.kr",
    }


def _cls_row(
    department_id: str, *, official_small_series_code: str, mapping_status: str = "AUTO_CANDIDATE",
    candidate_canonical_major_ids: list[str] | None = None, eligibility_status: str = "APPROVED",
    decision_reason: str = "테스트 사유",
) -> dict[str, Any]:
    return {
        "department_id": department_id, "official_small_series_code": official_small_series_code,
        "mapping_status": mapping_status, "candidate_canonical_major_ids": candidate_canonical_major_ids or [],
        "eligibility_status": eligibility_status, "decision_reason": decision_reason,
    }


def _approval_review_row(group_id: str, major_id: str) -> dict[str, Any]:
    return {
        "canonical_major_group_id": group_id, "canonical_major_id": major_id,
        "reviewer_1_status": "APPROVE", "reviewer_1_comment": "테스트 승인", "resolution_note": "",
    }


class FullyApprovedGateSuccessTest(unittest.TestCase):
    """지시서 §6 — computer_science FULL_GROUP·media_communication·industrial_engineering
    102 소계열만·business 033만, 4개 시나리오가 전부 승인됐을 때만 READY_FOR_PROMOTION이
    되는지 확인한다. 실제 Review JSON은 전혀 건드리지 않는다(전부 tempfile 안)."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.universe = _build_universe(
            root, approved_group_ids=frozenset(_GROUP_CODES),
        )
        reviews_dir = root / "reviews"
        bridge_mapping_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
        _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_mapping_rows)
        _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_mapping_rows)

        work_dir = root / "academyinfo_work" / "2025"
        self.departments = [
            _dept_row("dept_cs", department_name="컴퓨터공학과"),
            _dept_row("dept_media", department_name="미디어커뮤니케이션학과"),
            _dept_row("dept_ie_included", department_name="산업공학과"),
            _dept_row("dept_ie_excluded", department_name="안전공학과"),
            _dept_row("dept_biz_included", department_name="경영학과"),
            _dept_row("dept_biz_excluded", department_name="경영정보학과"),
        ]
        self.classifications = [
            _cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"]),
            _cls_row("dept_media", official_small_series_code="027", candidate_canonical_major_ids=["media_communication"]),
            _cls_row("dept_ie_included", official_small_series_code="102", candidate_canonical_major_ids=["industrial_engineering"]),
            _cls_row("dept_ie_excluded", official_small_series_code="103", candidate_canonical_major_ids=["industrial_engineering"]),
            _cls_row("dept_biz_included", official_small_series_code="033", candidate_canonical_major_ids=["business"]),
            _cls_row("dept_biz_excluded", official_small_series_code="035", candidate_canonical_major_ids=["business"]),
        ]
        _write_jsonl(work_dir / "departments.normalized.jsonl", self.departments)
        _write_jsonl(work_dir / "classification_results.jsonl", self.classifications)

        self.inputs = load_inputs(
            data_dir=root, survey_year=2025, reviews_dir=reviews_dir,
            group_draft_path=self.universe.group_draft_path, bridge_draft_path=self.universe.bridge_draft_path,
            canonical_majors_path=self.universe.majors_path,
            small_series_code_table_path=self.universe.code_table_path,
        )
        self.by_id = {r["department_id"]: r for r in self.departments}

    def _evaluate(self, department_id: str) -> dict[str, Any]:
        return evaluate_department(self.by_id[department_id], self.inputs)

    def test_computer_science_full_group_ready(self) -> None:
        result = self._evaluate("dept_cs")
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")
        self.assertEqual(result["blocked_reasons"], [])
        self.assertEqual(result["resolved_canonical_major_id"], "computer_science")

    def test_media_communication_ready(self) -> None:
        result = self._evaluate("dept_media")
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")
        self.assertEqual(result["resolved_canonical_major_id"], "media_communication")

    def test_industrial_engineering_included_small_series_ready(self) -> None:
        result = self._evaluate("dept_ie_included")
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")
        self.assertEqual(result["resolved_canonical_major_id"], "industrial_engineering")

    def test_industrial_engineering_excluded_small_series_blocked(self) -> None:
        result = self._evaluate("dept_ie_excluded")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE", result["blocked_reasons"])

    def test_business_included_small_series_ready(self) -> None:
        result = self._evaluate("dept_biz_included")
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")
        self.assertEqual(result["resolved_canonical_major_id"], "business_administration")

    def test_business_excluded_small_series_blocked(self) -> None:
        result = self._evaluate("dept_biz_excluded")
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIn("BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE", result["blocked_reasons"])

    def test_flipping_group_draft_approval_alone_blocks_previously_ready_department(self) -> None:
        """"모든 Gate 승인 시에만 READY_FOR_PROMOTION" — 다른 건 그대로 두고 Group
        Draft 승인만 빼면 다시 BLOCKED이어야 한다."""

        degraded = self.inputs.groups_by_id["computer_science"].model_copy(update={"review_status": "draft"})
        inputs = self.inputs.__class__(**{**self.inputs.__dict__, "groups_by_id": {**self.inputs.groups_by_id, "computer_science": degraded}})
        result = evaluate_department(self.by_id["dept_cs"], inputs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_GROUP_DRAFT"])

    def test_flipping_bridge_mapping_review_alone_blocks(self) -> None:
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["bridge_mapping_reviews"] = {
            k: v for k, v in self.inputs.bridge_mapping_reviews.items() if not k.startswith("computer_science::")
        }
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(self.by_id["dept_cs"], inputs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_BRIDGE_MAPPING_REVIEW"])

    def test_flipping_bridge_scope_review_alone_blocks(self) -> None:
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["bridge_scope_reviews"] = {
            k: v for k, v in self.inputs.bridge_scope_reviews.items() if not k.startswith("computer_science::")
        }
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(self.by_id["dept_cs"], inputs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_BRIDGE_SCOPE_REVIEW"])


class NoReviewBaselineTest(unittest.TestCase):
    """미검수 Fail-Closed — 현재 실제 저장소 상태(42개 Group 전부 draft, Bridge
    Scope/P1/N.C.E 검수 정본 없음)를 그대로 재현한 Fixture. 아무것도 승인하지
    않았으므로 완벽한 학과라도 READY_FOR_PROMOTION이 되면 안 된다."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.universe = _build_universe(root, approved_group_ids=frozenset())  # 전부 draft
        work_dir = root / "academyinfo_work" / "2025"
        self.dept = _dept_row("dept_cs")
        _write_jsonl(work_dir / "departments.normalized.jsonl", [self.dept])
        _write_jsonl(
            work_dir / "classification_results.jsonl",
            [_cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"])],
        )
        self.inputs = load_inputs(
            data_dir=root, survey_year=2025, reviews_dir=root / "reviews",  # 존재하지 않음 — Fail-Closed
            group_draft_path=self.universe.group_draft_path, bridge_draft_path=self.universe.bridge_draft_path,
            canonical_majors_path=self.universe.majors_path, small_series_code_table_path=self.universe.code_table_path,
        )

    def test_no_review_files_means_no_approval_ever_reached(self) -> None:
        self.assertEqual(self.inputs.bridge_mapping_reviews, {})
        self.assertEqual(self.inputs.bridge_scope_reviews, {})
        self.assertEqual(self.inputs.p1_reviews, {})
        self.assertEqual(self.inputs.nce_reviews, {})

    def test_department_blocked_by_group_draft_and_both_bridge_reviews(self) -> None:
        result = evaluate_department(self.dept, self.inputs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(
            result["blocked_reasons"],
            ["BLOCKED_BRIDGE_MAPPING_REVIEW", "BLOCKED_BRIDGE_SCOPE_REVIEW", "BLOCKED_GROUP_DRAFT"],
        )


class IndependentGateBlockingTest(unittest.TestCase):
    """지시서 §10 "각 Gate 단독 차단"·"복수 차단 사유 보존" — 완전히 통과하는 기준
    Fixture(전부 승인)에서 한 축만 깨거나 여러 축을 동시에 깨서 정확히 그 사유(들)만
    나오는지 확인한다."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES))
        reviews_dir = root / "reviews"
        bridge_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
        _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_rows)
        _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_rows)
        work_dir = root / "academyinfo_work" / "2025"
        _write_jsonl(work_dir / "departments.normalized.jsonl", [_dept_row("dept_cs")])
        _write_jsonl(
            work_dir / "classification_results.jsonl",
            [_cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"])],
        )
        self.inputs = load_inputs(
            data_dir=root, survey_year=2025, reviews_dir=reviews_dir,
            group_draft_path=universe.group_draft_path, bridge_draft_path=universe.bridge_draft_path,
            canonical_majors_path=universe.majors_path, small_series_code_table_path=universe.code_table_path,
        )

    def test_night_course_blocks_alone(self) -> None:
        row = _dept_row("dept_cs", recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE", exclusion_reason="EXCLUDED_NIGHT_COURSE")
        result = evaluate_department(row, self.inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_NIGHT_OR_REMOTE"])

    def test_distance_university_blocks_as_night_or_remote(self) -> None:
        row = _dept_row("dept_cs", recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE", exclusion_reason="EXCLUDED_DISTANCE_UNIVERSITY")
        result = evaluate_department(row, self.inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_NIGHT_OR_REMOTE"])

    def test_contract_department_blocks_alone(self) -> None:
        row = _dept_row("dept_cs", recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE", exclusion_reason="CONTRACT_DEPARTMENT")
        result = evaluate_department(row, self.inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_CONTRACT_DEPARTMENT"])

    def test_arts_sports_excluded_blocks_alone(self) -> None:
        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"],
            eligibility_status="EXCLUDED_ARTS_SPORTS",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_ARTS_RECOMMENDATION"])

    def test_p1_review_required_but_unresolved_blocks_alone(self) -> None:
        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"],
            eligibility_status="REVIEW_REQUIRED",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_P1_REVIEW_UNRESOLVED"])

    def test_p1_review_approved_as_eligible_unblocks(self) -> None:
        from src.schemas.academyinfo_p1_classification_review import P1ClassificationReviewDecision

        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"],
            eligibility_status="REVIEW_REQUIRED",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs_dict["p1_reviews"] = {
            "dept_cs": P1ClassificationReviewDecision(
                department_id="dept_cs", reviewer_1_status="APPROVE", resolved_eligibility_status="APPROVED",
            )
        }
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")

    def test_nce_unresolved_blocks_alone(self) -> None:
        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code=None, mapping_status="UNMAPPED",
            decision_reason="공식 소계열이 미분류(N.C.E)라 근거가 없다",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_NCE_UNRESOLVED"])

    def test_duplicate_id_blocks_alone(self) -> None:
        row = _dept_row("dept_cs", duplicate_group_size=2)
        result = evaluate_department(row, self.inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_DUPLICATE_ID"])

    def test_multiple_reasons_all_preserved(self) -> None:
        """복수 차단 사유 보존 — 첫 사유 하나만 남기지 않는다."""

        row = _dept_row(
            "dept_cs", department_status="ABOLISHED", duplicate_group_size=3,
            recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE", exclusion_reason="CONTRACT_DEPARTMENT",
        )
        result = evaluate_department(row, self.inputs)
        self.assertEqual(
            result["blocked_reasons"],
            ["BLOCKED_CONTRACT_DEPARTMENT", "BLOCKED_DUPLICATE_ID", "BLOCKED_INACTIVE_STATUS"],
        )

    def test_missing_lineage_identifiers_blocks(self) -> None:
        row = _dept_row("dept_cs", source_record_id=None)
        result = evaluate_department(row, self.inputs)
        self.assertIn("BLOCKED_MISSING_LINEAGE", result["blocked_reasons"])


class UrlPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES))
        reviews_dir = root / "reviews"
        bridge_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
        _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_rows)
        _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_rows)
        self.root = root
        self.universe = universe
        self.reviews_dir = reviews_dir

    def _inputs_with_url_audit(self, audit_row: dict[str, Any]) -> DryRunInputs:
        work_dir = self.root / "academyinfo_work" / "2025"
        row = _dept_row("dept_cs")
        _write_jsonl(work_dir / "departments.normalized.jsonl", [row])
        _write_jsonl(
            work_dir / "classification_results.jsonl",
            [_cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"])],
        )
        _write_jsonl(work_dir / "department_url_scope_audit.jsonl", [audit_row])
        return load_inputs(
            data_dir=self.root, survey_year=2025, reviews_dir=self.reviews_dir,
            group_draft_path=self.universe.group_draft_path, bridge_draft_path=self.universe.bridge_draft_path,
            canonical_majors_path=self.universe.majors_path, small_series_code_table_path=self.universe.code_table_path,
        )

    def _base_audit_row(self, **overrides: Any) -> dict[str, Any]:
        row = {
            "university_name": "테스트대학교", "department_name": "테스트학과", "college_name": "테스트단과대학",
            "department_url": "https://cs.test.ac.kr/", "department_url_scope": "department", "contains_api_key": False,
        }
        row.update(overrides)
        return row

    def test_department_scope_url_promotes(self) -> None:
        inputs = self._inputs_with_url_audit(self._base_audit_row())
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")
        self.assertEqual(result["resolved_department_url"], "https://cs.test.ac.kr/")

    def test_college_scope_url_never_exposed(self) -> None:
        inputs = self._inputs_with_url_audit(self._base_audit_row(department_url_scope="college"))
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertIsNone(result["resolved_department_url"])
        self.assertNotIn("BLOCKED_URL_POLICY", result["blocked_reasons"])

    def test_api_key_url_blocked(self) -> None:
        inputs = self._inputs_with_url_audit(self._base_audit_row(contains_api_key=True))
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertIn("BLOCKED_URL_POLICY", result["blocked_reasons"])
        self.assertIsNone(result["resolved_department_url"])

    def test_query_string_api_key_rejected_by_department_url_validator(self) -> None:
        inputs = self._inputs_with_url_audit(
            self._base_audit_row(department_url="https://cs.test.ac.kr/?serviceKey=abc123", contains_api_key=False)
        )
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertIn("BLOCKED_URL_POLICY", result["blocked_reasons"])
        self.assertIsNone(result["resolved_department_url"])


class RealMasterAndReviewFilesUntouchedTest(unittest.TestCase):
    """실제 Master(35건)·실제 Review JSON은 이 테스트를 포함해 이 모듈의 어떤 코드도
    쓰지 않는다 — git diff가 비어 있어야 한다."""

    def test_departments_jsonl_unchanged(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "data/master/departments.jsonl"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_review_files_unchanged(self) -> None:
        result = subprocess.run(
            ["git", "diff", "--exit-code", "HEAD", "--", "data/reviews/"],
            cwd=ROOT, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class CleanCloneMissingInputTest(unittest.TestCase):
    """실제 저장소 상태(정규화·분류 결과가 없음)로 CLI를 그대로 실행하면 종료 코드
    2로 실패하고 아무 파일도 쓰지 않아야 한다(`test_academyinfo_queue_clean_clone.py::
    MissingInputSafetyTest`와 같은 패턴)."""

    def test_missing_generation_inputs_exits_2_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "out"
            result = subprocess.run(
                [
                    sys.executable, str(_SCRIPT), "--survey-year", "2025",
                    "--data-dir", str(ROOT / "data"), "--output-dir", str(output_dir),
                ],
                cwd=ROOT, capture_output=True, text=True, timeout=120,
            )
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(output_dir.exists())

    def test_load_inputs_raises_when_normalized_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "academyinfo_work" / "2025").mkdir(parents=True)
            with self.assertRaises(MissingRequiredInputError):
                load_inputs(data_dir=root, survey_year=2025)


class DeterminismTest(unittest.TestCase):
    """같은 입력 2회 실행 byte-identical(지시서 §8)."""

    def test_two_runs_produce_identical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES))
            reviews_dir = root / "reviews"
            bridge_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
            _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_rows)
            _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_rows)
            work_dir = root / "academyinfo_work" / "2025"
            _write_jsonl(
                work_dir / "departments.normalized.jsonl",
                [_dept_row("dept_a"), _dept_row("dept_b", department_status="ABOLISHED")],
            )
            _write_jsonl(
                work_dir / "classification_results.jsonl",
                [
                    _cls_row("dept_a", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"]),
                    _cls_row("dept_b", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"]),
                ],
            )

            def _run(output_dir: Path) -> None:
                env_args = [
                    sys.executable, str(_SCRIPT), "--survey-year", "2025", "--data-dir", str(root),
                    "--output-dir", str(output_dir),
                ]
                result = subprocess.run(env_args, cwd=ROOT, capture_output=True, text=True, timeout=120)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            out1, out2 = root / "run1", root / "run2"
            _run(out1)
            _run(out2)

            for name in (
                "promotion_candidates.jsonl", "promotion_blocked.jsonl",
                "promotion_summary.json", "promotion_summary.md", "promotion_manifest.json",
            ):
                self.assertEqual((out1 / name).read_bytes(), (out2 / name).read_bytes(), name)

            manifest = json.loads((out1 / "promotion_manifest.json").read_text(encoding="utf-8"))
            self.assertNotIn("generated_at", manifest)
            self.assertEqual(manifest["auto_approved_rows"], 0)


if __name__ == "__main__":
    unittest.main()
