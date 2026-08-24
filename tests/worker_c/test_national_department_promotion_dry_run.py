"""전국 학과 → Master 승격 Dry Run 계약 테스트 — c/national-master-promotion-dry-run.

2026-08-24 후속 지시서(a/academyinfo-review-ui-p1-nce 정본 채택) — 이 Dry Run이
자체적으로 만들었던 P1/N.C.E Schema(department_id/cluster_id 키)를 검수 UI의 정본
(candidate_id/official_middle_series_code 키, AcademyInfoP1ClassificationReview/
AcademyInfoNceMiddleSeriesReview)으로 교체한 뒤의 계약을 검증한다.

`tests/worker_c/test_academyinfo_queue_clean_clone.py`의 패턴(Fail-Closed 입력 부재
검사, 실제 Builder subprocess 실행, byte-determinism)을 따르되, Gate 단위 검증은
`evaluate_department()`를 직접 호출해 빠르고 정확하게 확인한다. 실제
`data/reviews/*`·`data/master/*` 파일은 어디서도 열거나 쓰지 않는다(전부
`tempfile.TemporaryDirectory()` 안에서만 만든다)."""

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
    LINEAGE_LEVEL_CROSS_YEAR_VERIFIED,
    LINEAGE_LEVEL_ROW_IDENTITY_ONLY,
    DryRunInputs,
    MissingRequiredInputError,
    evaluate_department,
    load_inputs,
)
from src.ids import generate_offering_id  # noqa: E402
from src.review_ui.academyinfo_nce_middle_series_review_service import (  # noqa: E402
    update_nce_middle_series_review,
)
from src.review_ui.academyinfo_p1_classification_review_service import (  # noqa: E402
    update_p1_classification_review,
)
from src.schemas.academyinfo_nce_middle_series_cluster import AcademyInfoNceMiddleSeriesClusterEntry  # noqa: E402
from src.schemas.academyinfo_nce_middle_series_cluster_review import AcademyInfoNceMiddleSeriesReview  # noqa: E402
from src.schemas.academyinfo_p1_classification import AcademyInfoP1ClassificationEntry  # noqa: E402
from src.schemas.academyinfo_p1_classification_candidate_review import AcademyInfoP1ClassificationReview  # noqa: E402

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
    """합성 Fixture 하나(4개 Group·Bridge·Major·공식 소계열 코드표·P1/N.C.E Draft
    패킷)의 경로 모음."""

    def __init__(self, root: Path, survey_year: int) -> None:
        self.root = root
        self.group_draft_path = root / "canonical_major_groups.draft.jsonl"
        self.bridge_draft_path = root / "master" / "canonical_major_group_bridge.draft.jsonl"
        self.majors_path = root / "master" / "canonical_majors.jsonl"
        self.code_table_path = root / "academyinfo_raw" / str(survey_year) / "codes" / "getCodeBySmallSeries.jsonl.gz"
        work_dir = root / "academyinfo_work" / str(survey_year)
        self.p1_packet_path = work_dir / "packets" / "p1_classification_review.jsonl"
        self.nce_clusters_path = work_dir / "packets" / "nce_reexaminable_middle_series_clusters.jsonl"


def _build_universe(
    root: Path, *, approved_group_ids: frozenset[str] = frozenset(),
    scope_by_group: dict[str, tuple[str, list[str]]] | None = None,
    survey_year: int = 2025,
    p1_packet_rows: list[dict[str, Any]] | None = None,
    nce_cluster_rows: list[dict[str, Any]] | None = None,
) -> _Universe:
    """4개 Group·Bridge·Major·공식 소계열 코드표·P1/N.C.E Draft 패킷을 만든다.

    `scope_by_group`은 `{group_id: (scope_type, included_small_series_codes)}` —
    기본은 실제 데이터와 같은 값(computer_science/media_communication=FULL_GROUP,
    industrial_engineering=INCLUDED_SMALL_SERIES_ONLY[102],
    business=INCLUDED_SMALL_SERIES_ONLY[033])이다.

    `p1_packet_rows`/`nce_cluster_rows`를 생략하면 빈 목록(0행)을 쓴다 — 두 Draft
    패킷 다 2026-08-24부터 필수 입력이라(§6/§7 재검증에 필요) 파일 자체는 항상
    존재해야 하지만, P1/N.C.E Gate를 직접 다루지 않는 테스트는 빈 패킷으로 충분하다
    (그 경우 REVIEW_REQUIRED/N.C.E로 분류되는 학과가 아예 없으므로)."""

    universe = _Universe(root, survey_year)
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

    _write_jsonl(universe.p1_packet_path, p1_packet_rows or [])
    _write_jsonl(universe.nce_clusters_path, nce_cluster_rows or [])

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


def _group_review_row(group_id: str, *, approved: bool = True) -> dict[str, Any]:
    """2026-08-25 지시서(a/final-integration-master-promotion) §3 — Group 승인 정본이
    Draft의 정적 review_status에서 canonical_major_group_review_status.jsonl의
    decision으로 바뀌었다. `CanonicalMajorGroupReview`의 model_validator가
    decision↔reviewer_1_status 대응을 강제하므로(APPROVE_AS_CLASSIFICATION_GROUP↔
    APPROVE) 둘 다 함께 채운다."""

    decision = "APPROVE_AS_CLASSIFICATION_GROUP" if approved else "TBD"
    reviewer_1_status = "APPROVE" if approved else "TBD"
    return {
        "canonical_major_group_id": group_id, "decision": decision,
        "reviewer_1_status": reviewer_1_status, "reviewer_1_comment": "테스트 승인",
        "reviewer_2_status": "TBD", "reviewer_2_comment": "", "resolution_note": "", "revision": 0,
    }


def _write_group_reviews(reviews_dir: Path, group_ids, *, approved: bool = True) -> None:
    _write_jsonl(
        reviews_dir / "canonical_major_group_review_status.jsonl",
        [_group_review_row(g, approved=approved) for g in sorted(group_ids)],
    )


def _p1_packet_row(
    department_id: str, candidate_id: str, *, judgment_evidence_sufficient: bool = True,
    candidate_canonical_major_ids: list[str] | None = None, p1_cluster: str = "CONTENT_MEDIA",
    judgment_candidate: str = "MEDIA_COMMUNICATION_CANDIDATE",
) -> dict[str, Any]:
    """P1 패킷 한 행 — `AcademyInfoP1ClassificationEntry`와 같은 모양."""

    return {
        "candidate_id": candidate_id, "source_record_id": f"src_{candidate_id}",
        "department_id": department_id, "university_name": "테스트대학교", "college_name": "테스트단과대학",
        "department_name": "테스트학과", "official_large_series_name": "테스트계열",
        "official_middle_series_name": "테스트중계열", "official_small_series_name": "테스트소계열",
        "p1_cluster": p1_cluster, "judgment_candidate": judgment_candidate,
        "judgment_candidate_reason": "테스트 사유", "judgment_evidence_sufficient": judgment_evidence_sufficient,
        "candidate_canonical_major_ids": (
            candidate_canonical_major_ids if candidate_canonical_major_ids is not None else ["computer_science"]
        ),
        "arts_sports_possibility": "POSSIBLE_NEEDS_CHECK", "official_curriculum_available": False,
        "official_curriculum_summary": None, "official_evidence_needed": [],
    }


def _p1_review_row(candidate_id: str, decision: str, *, comment: str = "", revision: int = 0) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id, "decision": decision, "reviewer_comment": comment,
        "resolution_note": "", "revision": revision,
    }


def _nce_cluster_row(
    code: str, *, department_ids: list[str], group_linkage_status: str = "PROPOSED_GROUP_CANDIDATE",
    candidate_groups: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """N.C.E 중계열 클러스터 한 행 — `AcademyInfoNceMiddleSeriesClusterEntry`와 같은 모양."""

    members = [
        {
            "candidate_id": f"nce_{d}", "university_name": "테스트대학교", "college_name": "테스트단과대학",
            "department_name": "테스트학과", "department_id": d, "source_record_id": f"src_{d}",
        }
        for d in department_ids
    ]
    return {
        "cluster_id": f"nce_reex_{code}", "official_middle_series_code": code,
        "official_middle_series_name": "테스트중계열", "official_middle_series_code_source": "test",
        "group_linkage_status": group_linkage_status,
        "candidate_canonical_major_groups": (
            candidate_groups if candidate_groups is not None else [{"canonical_major_id": "computer_science", "label": "컴퓨터"}]
        ),
        "candidate_canonical_major_group_basis": "테스트 근거", "unlinkable_or_too_broad_reason": "",
        "additional_official_evidence_needed": [], "forbidden": [], "members": members, "row_count": len(members),
    }


def _nce_review_row(code: str, decision: str, *, comment: str = "", revision: int = 0) -> dict[str, Any]:
    return {
        "official_middle_series_code": code, "decision": decision, "reviewer_comment": comment,
        "resolution_note": "", "revision": revision,
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
        _write_group_reviews(reviews_dir, _GROUP_CODES)

        work_dir = root / "academyinfo_work" / "2025"
        # 2026-08-25 지시서(a/final-integration-master-promotion) §4 — offering_id는
        # schl_id+source_schl_mjr_id로만 계산된다(department_name과 무관) — 이 6개
        # 행에 서로 다른 source_schl_mjr_id를 명시하지 않으면 전부 같은 offering_id로
        # 뭉개져 BLOCKED_DUPLICATE_ID가 잘못 걸린다(department_id 시절엔
        # department_name이 Key 재료라 문제가 없었다).
        self.departments = [
            _dept_row("dept_cs", department_name="컴퓨터공학과", source_schl_mjr_id="mjr_cs"),
            _dept_row("dept_media", department_name="미디어커뮤니케이션학과", source_schl_mjr_id="mjr_media"),
            _dept_row("dept_ie_included", department_name="산업공학과", source_schl_mjr_id="mjr_ie_included"),
            _dept_row("dept_ie_excluded", department_name="안전공학과", source_schl_mjr_id="mjr_ie_excluded"),
            _dept_row("dept_biz_included", department_name="경영학과", source_schl_mjr_id="mjr_biz_included"),
            _dept_row("dept_biz_excluded", department_name="경영정보학과", source_schl_mjr_id="mjr_biz_excluded"),
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
            p1_packet_path=self.universe.p1_packet_path, nce_clusters_path=self.universe.nce_clusters_path,
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
        승인만 빼면 다시 BLOCKED이어야 한다.

        2026-08-25 지시서(a/final-integration-master-promotion) §3 정정 — 승인 정본이
        Draft의 정적 review_status에서 Group Review Store(decision)로 바뀌었으므로,
        이제는 `group_reviews` dict에서 그 Group의 항목을 빼서 재현한다(다른 두
        flipping 테스트가 이미 쓰는 것과 같은 in-memory 패턴)."""

        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["group_reviews"] = {k: v for k, v in self.inputs.group_reviews.items() if k != "computer_science"}
        inputs = self.inputs.__class__(**inputs_dict)
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

    def test_lineage_level_is_row_identity_only_for_every_row(self) -> None:
        """2026-08-24 지시서 §9 — 실제 연도 간 대조가 없는 한 모든 행이
        ROW_IDENTITY_ONLY여야 한다."""

        for department_id in self.by_id:
            result = self._evaluate(department_id)
            self.assertEqual(result["lineage_level"], LINEAGE_LEVEL_ROW_IDENTITY_ONLY)
            self.assertNotEqual(result["lineage_level"], LINEAGE_LEVEL_CROSS_YEAR_VERIFIED)


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
            p1_packet_path=self.universe.p1_packet_path, nce_clusters_path=self.universe.nce_clusters_path,
            # 2026-08(a/final-mapping-review-closeout) 정정 — load_inputs()의
            # p1_review_path/nce_review_path 기본값은 (bridge_mapping_review_path/
            # bridge_scope_review_path와 달리) reviews_dir이 아니라 항상 실제
            # default_p1_review_path()/default_nce_review_path()로 떨어진다(그
            # 두 함수가 reviews_dir 인자를 받지 않는 전역 기본 경로 Store 함수이기
            # 때문 — career_build_national_department_promotion_dry_run.py 자체의
            # 기존 동작이며 이 테스트 파일이 바꾸지 않는다). 이 테스트가 "검수 정본
            # 없음"을 실제로 재현하려면 실제 data/reviews/의 그 두 파일이 무엇이든
            # 상관없이 존재하지 않는 tmp 경로를 명시적으로 줘야 한다 — 다른
            # 클래스(IndependentGateBlockingTest)가 이미 쓰는 것과 같은 패턴이다.
            p1_review_path=root / "reviews" / "academyinfo_p1_classification_review_status.jsonl",
            nce_review_path=root / "reviews" / "academyinfo_nce_middle_series_review_status.jsonl",
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
        _write_group_reviews(reviews_dir, _GROUP_CODES)
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
            p1_packet_path=universe.p1_packet_path, nce_clusters_path=universe.nce_clusters_path,
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

    def test_p1_review_required_but_no_packet_entry_is_excluded_not_unresolved(self) -> None:
        """2026-08-25 지시서(a/final-integration-master-promotion) §3 정정 — P1 Draft
        자체가 없는 행(REVIEW_REQUIRED인데 P1 패킷에 그 학과 행이 없음)은 "검토가
        아직 안 끝났다"가 아니라 "이번 라운드 검토 범위 밖"이다(실측: 이번 연도
        분류 REVIEW_REQUIRED 4,258건 중 374행 P1 패킷 범위 밖이 3,883건). 그래서
        BLOCKED_P1_REVIEW_UNRESOLVED가 아니라 BLOCKED_EXCLUDED_FROM_INITIAL_
        PROMOTION으로 막는다 — 여전히 Fail-Closed(자동 승인하지 않음)라는 결론은
        그대로다."""

        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"],
            eligibility_status="REVIEW_REQUIRED",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION"])
        self.assertNotIn("BLOCKED_P1_REVIEW_UNRESOLVED", result["blocked_reasons"])

    def _p1_review_required_inputs(
        self, *, judgment_evidence_sufficient: bool = True, candidate_canonical_major_ids: list[str] | None = None,
        review_decision: str | None = "APPROVE_PROPOSED_CANDIDATE",
    ):
        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"],
            eligibility_status="REVIEW_REQUIRED",
        )
        p1_draft = AcademyInfoP1ClassificationEntry.model_validate(
            _p1_packet_row(
                "dept_cs", "p1cls_dept_cs", judgment_evidence_sufficient=judgment_evidence_sufficient,
                candidate_canonical_major_ids=candidate_canonical_major_ids,
            )
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs_dict["p1_draft_by_department_id"] = {"dept_cs": p1_draft}
        inputs_dict["p1_draft_by_candidate_id"] = {"p1cls_dept_cs": p1_draft}
        if review_decision is not None:
            inputs_dict["p1_reviews"] = {
                "p1cls_dept_cs": AcademyInfoP1ClassificationReview(
                    candidate_id="p1cls_dept_cs", decision=review_decision,
                )
            }
        else:
            inputs_dict["p1_reviews"] = {}
        return row, self.inputs.__class__(**inputs_dict)

    def test_p1_review_approved_and_eligible_unblocks(self) -> None:
        row, inputs = self._p1_review_required_inputs()
        result = evaluate_department(row, inputs)
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")
        self.assertEqual(result["p1_candidate_id"], "p1cls_dept_cs")
        self.assertEqual(result["p1_review_decision"], "APPROVE_PROPOSED_CANDIDATE")

    def test_p1_review_approved_but_evidence_insufficient_still_blocked(self) -> None:
        """2026-08-24 지시서 §6 방어 검증 — 검수 파일에 APPROVE_PROPOSED_CANDIDATE가
        저장돼 있어도, Draft 원본이 judgment_evidence_sufficient=False면 이 Dry Run은
        그 값을 그대로 믿지 않고 다시 막는다(파일이 수동으로 손상된 경우 대비)."""

        row, inputs = self._p1_review_required_inputs(judgment_evidence_sufficient=False)
        result = evaluate_department(row, inputs)
        self.assertIn("BLOCKED_P1_REVIEW_UNRESOLVED", result["blocked_reasons"])

    def test_p1_review_approved_but_multiple_candidates_still_blocked(self) -> None:
        row, inputs = self._p1_review_required_inputs(
            candidate_canonical_major_ids=["computer_science", "media_communication"],
        )
        result = evaluate_department(row, inputs)
        self.assertIn("BLOCKED_P1_REVIEW_UNRESOLVED", result["blocked_reasons"])

    def test_p1_review_approved_but_candidate_is_group_id_not_service_major_still_blocked(self) -> None:
        """DESIGN_ARTS_EXCLUDED류 — candidate_canonical_major_ids가 42개 Group ID를
        가리키면(예: fine_arts_design) 10개 서비스 Major가 아니므로 여전히 막는다."""

        row, inputs = self._p1_review_required_inputs(candidate_canonical_major_ids=["fine_arts_design"])
        result = evaluate_department(row, inputs)
        self.assertIn("BLOCKED_P1_REVIEW_UNRESOLVED", result["blocked_reasons"])

    def test_all_non_approve_p1_decisions_block(self) -> None:
        """지시서(a/academyinfo-review-ui-p1-nce) §6 "나머지 Decision은 모두 차단" —
        APPROVE_PROPOSED_CANDIDATE 외에는 전부 READY로 이어지지 않는다.

        2026-08-25 지시서(a/final-integration-master-promotion) §3 정정 — "모두
        차단"은 여전히 참이지만, 어느 사유로 막히는지는 decision마다 다르게 구분
        해야 한다("검수 완료 항목을 P1_REVIEW_UNRESOLVED로 집계하지 않는다"):
        진짜 미결(TBD/REVISE_CANDIDATE/HOLD)만 BLOCKED_P1_REVIEW_UNRESOLVED,
        예체능(EXCLUDE_ARTS_RECOMMENDATION)은 BLOCKED_ARTS_RECOMMENDATION,
        검토 완료·이번 라운드 제외(KEEP_UNMAPPED/NEEDS_OFFICIAL_CURRICULUM)는
        BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION."""

        expected_reason_by_decision = {
            "TBD": "BLOCKED_P1_REVIEW_UNRESOLVED",
            "REVISE_CANDIDATE": "BLOCKED_P1_REVIEW_UNRESOLVED",
            "HOLD": "BLOCKED_P1_REVIEW_UNRESOLVED",
            "EXCLUDE_ARTS_RECOMMENDATION": "BLOCKED_ARTS_RECOMMENDATION",
            "KEEP_UNMAPPED": "BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION",
            "NEEDS_OFFICIAL_CURRICULUM": "BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION",
        }
        for decision, expected_reason in expected_reason_by_decision.items():
            with self.subTest(decision=decision):
                row, inputs = self._p1_review_required_inputs(review_decision=decision)
                result = evaluate_department(row, inputs)
                self.assertIn(expected_reason, result["blocked_reasons"])
                self.assertNotEqual(result["status"], "READY_FOR_PROMOTION")

    def test_no_p1_review_saved_at_all_blocks(self) -> None:
        row, inputs = self._p1_review_required_inputs(review_decision=None)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_P1_REVIEW_UNRESOLVED"])
        self.assertEqual(result["p1_review_decision"], "TBD")

    def test_nce_unresolved_blocks_alone(self) -> None:
        """진짜 미결(클러스터는 있지만 검수가 TBD)일 때만 BLOCKED_NCE_UNRESOLVED다
        (2026-08-25 지시서 §3 — 클러스터 자체가 없는 경우는 별도 테스트에서 다룬다)."""

        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code=None, mapping_status="UNMAPPED",
            decision_reason="공식 소계열이 미분류(N.C.E)라 근거가 없다",
        )
        cluster = AcademyInfoNceMiddleSeriesClusterEntry.model_validate(_nce_cluster_row("99", department_ids=["dept_cs"]))
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs_dict["nce_middle_series_code_by_department"] = {"dept_cs": "99"}
        inputs_dict["nce_clusters_by_code"] = {"99": cluster}
        inputs_dict["nce_reviews"] = {}  # 검수 파일 자체가 없음 — decision은 기본값 TBD.
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_NCE_UNRESOLVED"])

    def test_nce_cluster_not_covered_by_review_scope_is_excluded_not_unresolved(self) -> None:
        """2026-08-25 지시서 §3 정정 — 이번 연도 분류가 N.C.E로 표시했지만 24개
        검수 완료 클러스터 어디에도 속하지 않는 행(실측 2,953건)은 "검토가 아직 안
        끝났다"가 아니라 "이번 라운드 검토 범위 밖"이다 — BLOCKED_EXCLUDED_FROM_
        INITIAL_PROMOTION으로 막는다."""

        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code=None, mapping_status="UNMAPPED",
            decision_reason="공식 소계열이 미분류(N.C.E)라 근거가 없다",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs_dict["nce_middle_series_code_by_department"] = {}  # 어떤 클러스터에도 속하지 않음.
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION"])
        self.assertNotIn("BLOCKED_NCE_UNRESOLVED", result["blocked_reasons"])

    def test_nce_accept_as_review_candidate_without_bridge_still_blocks(self) -> None:
        """2026-08-25 지시서 §3 정정 — ACCEPT_GROUP_AS_REVIEW_CANDIDATE가 저장돼
        있어도 그 자체로 학과 승격 승인이 되지는 않는다. 후보 Group에 아직 Bridge
        Mapping이 승인한 EVIDENCED 서비스 Major가 없으면(이 테스트의 "law" Group —
        `_GROUP_TO_MAJOR`에 없어 Bridge가 전혀 없다) BLOCKED_EXCLUDED_FROM_INITIAL_
        PROMOTION으로 막힌다(추측 Mapping 금지) — resolved_canonical_major_group_id는
        여전히 채워지지 않는다. (Bridge가 정확히 1개일 때 실제로 풀리는 성공 경로는
        UiSavedReviewConsumedByDryRunTest가 별도로 검증한다.)"""

        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code=None, mapping_status="UNMAPPED",
            decision_reason="공식 소계열이 미분류(N.C.E)라 근거가 없다",
        )
        cluster = AcademyInfoNceMiddleSeriesClusterEntry.model_validate(
            _nce_cluster_row("99", department_ids=["dept_cs"], candidate_groups=[{"canonical_major_id": "law", "label": "법학"}])
        )
        nce_review = AcademyInfoNceMiddleSeriesReview(
            official_middle_series_code="99", decision="ACCEPT_GROUP_AS_REVIEW_CANDIDATE",
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}
        inputs_dict["nce_middle_series_code_by_department"] = {"dept_cs": "99"}
        inputs_dict["nce_clusters_by_code"] = {"99": cluster}
        inputs_dict["nce_reviews"] = {"99": nce_review}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION"])
        self.assertIsNone(result["resolved_canonical_major_group_id"])
        self.assertIsNone(result["resolved_canonical_major_id"])
        # 감사용 참고 필드에는 실제 판단이 남아 있다 — "왜 아직 막혔는지" 추적 가능.
        self.assertEqual(result["nce_middle_series_code"], "99")
        self.assertEqual(result["nce_review_decision"], "ACCEPT_GROUP_AS_REVIEW_CANDIDATE")

    def test_duplicate_id_blocks_alone(self) -> None:
        """2026-08-25 지시서 §4 정정 — 유일 Key가 department_id에서 offering_id로
        바뀌어, 이제 중복은 department_id 행의 duplicate_group_size가 아니라
        offering_id_counts로 판정한다. 이 행의 offering_id를 직접 계산해
        offering_id_counts에서 2로 주입해 진짜 충돌을 재현한다."""

        row = _dept_row("dept_cs")
        offering_id = generate_offering_id(row["schl_id"], row["source_schl_mjr_id"])
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["offering_id_counts"] = {offering_id: 2}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_DUPLICATE_ID"])

    def test_multiple_reasons_all_preserved(self) -> None:
        """복수 차단 사유 보존 — 첫 사유 하나만 남기지 않는다."""

        row = _dept_row(
            "dept_cs", department_status="ABOLISHED",
            recommendation_scope="OUT_OF_RECOMMENDATION_SCOPE", exclusion_reason="CONTRACT_DEPARTMENT",
        )
        offering_id = generate_offering_id(row["schl_id"], row["source_schl_mjr_id"])
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["offering_id_counts"] = {offering_id: 3}
        inputs = self.inputs.__class__(**inputs_dict)
        result = evaluate_department(row, inputs)
        self.assertEqual(
            result["blocked_reasons"],
            ["BLOCKED_CONTRACT_DEPARTMENT", "BLOCKED_DUPLICATE_ID", "BLOCKED_INACTIVE_STATUS"],
        )

    def test_missing_lineage_identifiers_blocks(self) -> None:
        row = _dept_row("dept_cs", source_record_id=None)
        result = evaluate_department(row, self.inputs)
        self.assertIn("BLOCKED_MISSING_LINEAGE", result["blocked_reasons"])

    def test_ambiguous_multiple_evidenced_bridge_candidates_distinct_from_no_candidate(self) -> None:
        """2026-08-24 지시서 §8 — Group에 EVIDENCED 후보가 0개면
        BLOCKED_NO_SERVICE_CANONICAL_MAJOR, 2개 이상이면
        BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR로 서로 다른 사유가 나와야 한다."""

        row = _dept_row("dept_cs")
        cls = _cls_row(
            "dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"],
        )
        inputs_dict = dict(self.inputs.__dict__)
        inputs_dict["classification_by_department"] = {"dept_cs": cls}

        # 0개 EVIDENCED (Group을 아예 안 다룬 상태로 흉내) — 기존 Bridge Entry 목록에서 지운다.
        no_candidate_inputs = self.inputs.__class__(
            **{**inputs_dict, "bridge_entries_by_group": {}},
        )
        result_no_candidate = evaluate_department(row, no_candidate_inputs)
        self.assertIn("BLOCKED_NO_SERVICE_CANONICAL_MAJOR", result_no_candidate["blocked_reasons"])
        self.assertNotIn("BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR", result_no_candidate["blocked_reasons"])

        # 2개 EVIDENCED — 같은 Group에 두 번째 Major 후보를 추가한다.
        second_entry = self.inputs.bridge_entries_by_group["computer_science"][0].model_copy(
            update={"canonical_major_id": "media_communication"}
        )
        two_candidate_entries = {
            **self.inputs.bridge_entries_by_group,
            "computer_science": [*self.inputs.bridge_entries_by_group["computer_science"], second_entry],
        }
        two_candidate_inputs = self.inputs.__class__(
            **{**inputs_dict, "bridge_entries_by_group": two_candidate_entries},
        )
        result_ambiguous = evaluate_department(row, two_candidate_inputs)
        self.assertIn("BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR", result_ambiguous["blocked_reasons"])
        self.assertNotIn("BLOCKED_NO_SERVICE_CANONICAL_MAJOR", result_ambiguous["blocked_reasons"])

    def test_ambiguous_multiple_auto_candidates_distinct_from_zero_candidates(self) -> None:
        """같은 구분을 classification 단계(AUTO_CANDIDATE의 candidate_canonical_
        major_ids)에서도 확인한다."""

        row = _dept_row("dept_cs")

        zero_cls = _cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=[])
        inputs_zero = self.inputs.__class__(
            **{**dict(self.inputs.__dict__), "classification_by_department": {"dept_cs": zero_cls}},
        )
        result_zero = evaluate_department(row, inputs_zero)
        self.assertIn("BLOCKED_NO_SERVICE_CANONICAL_MAJOR", result_zero["blocked_reasons"])

        multi_cls = _cls_row(
            "dept_cs", official_small_series_code="089",
            candidate_canonical_major_ids=["computer_science", "media_communication"],
        )
        inputs_multi = self.inputs.__class__(
            **{**dict(self.inputs.__dict__), "classification_by_department": {"dept_cs": multi_cls}},
        )
        result_multi = evaluate_department(row, inputs_multi)
        self.assertIn("BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR", result_multi["blocked_reasons"])


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
        _write_group_reviews(reviews_dir, _GROUP_CODES)
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
            p1_packet_path=self.universe.p1_packet_path, nce_clusters_path=self.universe.nce_clusters_path,
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
        """이 테스트가 실제로 지키려는 것은 "이 Dry Run 모듈 자체가 Master를 쓰지
        않는다"이지 "Master가 이 브랜치에서 영원히 35건이어야 한다"가 아니다.
        2026-08-25 전국 학과 1,072건 Production Master 전환(a/national-master-
        promotion-final-wiring)은 별도의 `scripts/career_promote_national_
        departments_master.py`가 이 Dry Run의 READY_FOR_PROMOTION 결과를 입력
        삼아 의도적으로 교체했다 — 옛 35건은 data/archive/departments_legacy_
        demo_35.jsonl로 보존됐다. 그래서 여기서는 "이 Dry Run 모듈 소스 자체에
        Master를 쓰는 코드가 없다"만 정적으로 확인한다(모듈 docstring이 이미 명시한
        "실제 Master도 공개 API/Mock도 절대" 원칙 그대로)."""
        source = (ROOT / "scripts" / "career_build_national_department_promotion_dry_run.py").read_text(
            encoding="utf-8"
        )
        # "departments.jsonl"(Master 파일명 전체)이 등장하는 곳은 전부 docstring·주석·
        # 문자열 보고서 문구뿐이다 — 실제로 이 경로에 쓰는 호출(write_jsonl(...)·
        # .write_text(...)의 대상 인자)로는 한 번도 쓰이지 않는지만 확인한다.
        for line in source.splitlines():
            if "departments.jsonl" in line:
                self.assertNotIn("write_jsonl(", line)
                self.assertNotIn(".write_text(", line)

    # 2026-08(a/final-mapping-review-closeout)가 사용자 최종 결정에 따라 이 5개
    # 파일에 실제 검수 결과를 기록했다 — 이 테스트가 실제로 지키려는 것은 "이 Dry
    # Run 모듈 자체가 data/reviews/에 쓰지 않는다"이지 "data/reviews/ 전체가
    # 영원히 git-clean이어야 한다"가 아니다(Dry Run은 §8 "Master·API는 이 실행으로
    # 바뀌지 않는다"만 보장하면 된다 — Review 파일도 읽기만 한다). 그 5개만 제외
    # 하고 나머지는 여전히 무변경이어야 한다.
    # 2026-08-25(a/final-integration-master-promotion §7)가 사용자 최종 결정("기존
    # 코멘트로 수정 요청된 문항을 제외하고 수정 완료된 질문은 모두 통과")에 따라
    # 12개 ContextPack 검수 상태 파일도 실제로 갱신했다 — 같은 이유로 허용 목록에
    # 추가한다.
    _INTENTIONALLY_FINALIZED_REVIEW_FILES = (
        "data/reviews/canonical_major_group_review_status.jsonl",
        "data/reviews/canonical_major_group_bridge_review_status.json",
        "data/reviews/canonical_major_group_bridge_scope_review_status.jsonl",
        "data/reviews/academyinfo_p1_classification_review_status.jsonl",
        "data/reviews/academyinfo_nce_middle_series_review_status.jsonl",
        "data/reviews/context_packs/art_design_review_status.json",
        "data/reviews/context_packs/business_review_status.json",
        "data/reviews/context_packs/cooking_review_status.json",
        "data/reviews/context_packs/fashion_beauty_review_status.json",
        "data/reviews/context_packs/history_humanities_review_status.json",
        "data/reviews/context_packs/law_politics_review_status.json",
        "data/reviews/context_packs/making_review_status.json",
        "data/reviews/context_packs/science_review_status.json",
        "data/reviews/context_packs/sports_review_status.json",
        "data/reviews/context_packs/travel_review_status.json",
        "data/reviews/context_packs/volunteer_review_status.json",
        "data/reviews/context_packs/writing_review_status.json",
    )

    def test_real_review_files_unchanged(self) -> None:
        result = subprocess.run(
            ["git", "status", "--porcelain", "--", "data/reviews/"],
            cwd=ROOT, capture_output=True, text=True,
        )
        changed = [line[3:] for line in result.stdout.splitlines() if line.strip()]
        unexpected = [p for p in changed if p not in self._INTENTIONALLY_FINALIZED_REVIEW_FILES]
        self.assertEqual(unexpected, [], f"data/reviews/ 아래 의도하지 않은 변경: {unexpected}")


class DuplicateSchemaRemovedTest(unittest.TestCase):
    """§2 "중복 Schema 삭제" — Dry Run이 자체적으로 만들었던 두 Schema 파일이
    실제로 사라졌고, 그 이름의 클래스가 저장소 어디에도 남아 있지 않은지 확인한다."""

    def test_old_p1_schema_file_removed(self) -> None:
        self.assertFalse((ROOT / "src" / "schemas" / "academyinfo_p1_classification_review.py").exists())

    def test_old_nce_schema_file_removed(self) -> None:
        self.assertFalse((ROOT / "src" / "schemas" / "academyinfo_nce_middle_series_review.py").exists())

    def test_old_class_names_absent_from_source_tree(self) -> None:
        for py_file in (ROOT / "src").rglob("*.py"):
            text = py_file.read_text(encoding="utf-8")
            self.assertNotIn("P1ClassificationReviewDecision", text, py_file)
            self.assertNotIn("NceMiddleSeriesReviewDecision", text, py_file)

    def test_dry_run_uses_canonical_review_ui_classes(self) -> None:
        """§3 "검수 UI 정본 사용"."""

        source = _SCRIPT.read_text(encoding="utf-8")
        self.assertIn("AcademyInfoP1ClassificationReview", source)
        self.assertIn("AcademyInfoNceMiddleSeriesReview", source)
        self.assertIn("from src.review_ui.academyinfo_p1_classification_review_service import p1_approve_eligible", source)


class JsonlPathOnlyTest(unittest.TestCase):
    """§4 "파일 경로 통일"·필수 테스트 "`.json` 경로 사용 0건" — Dry Run 소스에서
    P1/N.C.E 검수 파일에 `.json`(jsonl이 아닌) 확장자를 쓰는 곳이 하나도 없어야
    한다. Bridge Mapping(`canonical_major_group_bridge_review_status.json`)은
    이 지시서의 대상이 아니라서 검사에서 제외한다."""

    def test_no_dot_json_path_used_for_p1_or_nce_review(self) -> None:
        source = _SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn('academyinfo_p1_classification_review_status.json"', source)
        self.assertNotIn('academyinfo_nce_middle_series_review_status.json"', source)
        self.assertIn('academyinfo_p1_classification_review_status.jsonl', source)
        self.assertIn('academyinfo_nce_middle_series_review_status.jsonl', source)

    def test_default_paths_match_review_ui_store_defaults(self) -> None:
        from src.services.academyinfo_nce_middle_series_review_store import (
            nce_review_path as canonical_nce_path,
        )
        from src.services.academyinfo_p1_classification_review_store import (
            p1_review_path as canonical_p1_path,
        )
        import scripts.career_build_national_department_promotion_dry_run as dry_run_module

        self.assertEqual(dry_run_module.default_p1_review_path(), canonical_p1_path())
        self.assertEqual(dry_run_module.default_nce_review_path(), canonical_nce_path())


class UiSavedReviewConsumedByDryRunTest(unittest.TestCase):
    """필수 테스트 "UI 저장 JSONL을 Dry Run이 실제로 소비" — 검수 UI의 PATCH
    Endpoint가 실제로 호출하는 바로 그 서비스 함수(update_p1_classification_review/
    update_nce_middle_series_review)로 저장한 뒤, 이 Dry Run이 같은 파일을 읽어
    그 결정을 실제로 반영하는지 end-to-end로 확인한다."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def test_p1_ui_approve_flows_into_ready_for_promotion(self) -> None:
        root = self.root
        p1_packet_row = _p1_packet_row(
            "dept_cs", "p1cls_dept_cs", judgment_evidence_sufficient=True,
            candidate_canonical_major_ids=["computer_science"],
        )
        universe = _build_universe(
            root, approved_group_ids=frozenset(_GROUP_CODES), p1_packet_rows=[p1_packet_row],
        )
        reviews_dir = root / "reviews"
        bridge_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
        _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_rows)
        _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_rows)
        _write_group_reviews(reviews_dir, _GROUP_CODES)

        work_dir = root / "academyinfo_work" / "2025"
        _write_jsonl(work_dir / "departments.normalized.jsonl", [_dept_row("dept_cs")])
        _write_jsonl(
            work_dir / "classification_results.jsonl",
            [
                _cls_row(
                    "dept_cs", official_small_series_code="089",
                    candidate_canonical_major_ids=["computer_science"], eligibility_status="REVIEW_REQUIRED",
                )
            ],
        )

        p1_review_path = reviews_dir / "academyinfo_p1_classification_review_status.jsonl"
        # 검수 UI PATCH Endpoint가 실제로 부르는 바로 그 함수 — 손으로 JSONL을 쓰지 않는다.
        out = update_p1_classification_review(
            "p1cls_dept_cs", decision="APPROVE_PROPOSED_CANDIDATE", comment="UI에서 승인", resolution_note=None,
            expected_revision=0, packet_path=universe.p1_packet_path, review_status_path=p1_review_path,
        )
        self.assertTrue(out.ok)

        inputs = load_inputs(
            data_dir=root, survey_year=2025, reviews_dir=reviews_dir,
            group_draft_path=universe.group_draft_path, bridge_draft_path=universe.bridge_draft_path,
            canonical_majors_path=universe.majors_path, small_series_code_table_path=universe.code_table_path,
            p1_packet_path=universe.p1_packet_path, p1_review_path=p1_review_path,
        )
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertEqual(result["status"], "READY_FOR_PROMOTION")

    def test_nce_ui_accept_flows_into_ready_when_bridge_is_unambiguous(self) -> None:
        """2026-08-25 지시서(a/final-integration-master-promotion) §3 정정 — 이전
        버전은 "N.C.E는 §7 규칙대로 절대 안 풀린다"고 단언했다. 실제 지시는
        "ACCEPT_GROUP_AS_REVIEW_CANDIDATE는 그 후보 Group에 이미 Bridge Mapping이
        승인한 EVIDENCED 서비스 Major가 정확히 1개일 때만" 그 뒤 Group/Bridge/Scope
        Gate를 그대로 통과시킨다 — 이 시나리오(후보 Group 1개=computer_science,
        FULL_GROUP이라 소계열 확인 불필요, Bridge 1개)가 정확히 그 경우라 이제는
        READY_FOR_PROMOTION이 맞다."""

        root = self.root
        nce_row = _nce_cluster_row("99", department_ids=["dept_cs"])
        universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES), nce_cluster_rows=[nce_row])
        reviews_dir = root / "reviews"
        bridge_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
        _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_rows)
        _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_rows)
        _write_group_reviews(reviews_dir, _GROUP_CODES)

        work_dir = root / "academyinfo_work" / "2025"
        _write_jsonl(work_dir / "departments.normalized.jsonl", [_dept_row("dept_cs")])
        _write_jsonl(
            work_dir / "classification_results.jsonl",
            [
                _cls_row(
                    "dept_cs", official_small_series_code=None, mapping_status="UNMAPPED",
                    decision_reason="공식 소계열이 미분류(N.C.E)라 근거가 없다",
                )
            ],
        )

        nce_review_path = reviews_dir / "academyinfo_nce_middle_series_review_status.jsonl"
        out = update_nce_middle_series_review(
            "99", decision="ACCEPT_GROUP_AS_REVIEW_CANDIDATE", comment="UI에서 후보로 인정", resolution_note=None,
            expected_revision=0, cluster_path=universe.nce_clusters_path, review_status_path=nce_review_path,
        )
        self.assertTrue(out.ok)

        inputs = load_inputs(
            data_dir=root, survey_year=2025, reviews_dir=reviews_dir,
            group_draft_path=universe.group_draft_path, bridge_draft_path=universe.bridge_draft_path,
            canonical_majors_path=universe.majors_path, small_series_code_table_path=universe.code_table_path,
            nce_clusters_path=universe.nce_clusters_path, nce_review_path=nce_review_path,
        )
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertEqual(result["status"], "READY_FOR_PROMOTION", result["blocked_reasons"])
        self.assertEqual(result["resolved_canonical_major_id"], "computer_science")
        self.assertEqual(result["nce_review_decision"], "ACCEPT_GROUP_AS_REVIEW_CANDIDATE")

    def test_nce_ui_accept_blocked_when_no_bridge_or_ambiguous(self) -> None:
        """§3 "후보 없음 또는 복수 Bridge면 초기 승격 제외" — 후보 Group이 아직
        어떤 서비스 Major에도 Bridge Mapping이 없으면(0개), 승인 결정을 받았어도
        BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION으로 막힌다(추측 Mapping 금지)."""

        root = self.root
        nce_row = _nce_cluster_row(
            "99", department_ids=["dept_cs"],
            candidate_groups=[{"canonical_major_id": "fine_arts_design", "label": "미술디자인"}],
        )
        universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES), nce_cluster_rows=[nce_row])
        reviews_dir = root / "reviews"
        bridge_rows = [_approval_review_row(g, m) for g, m in _GROUP_TO_MAJOR.items()]
        _write_json_list(reviews_dir / "canonical_major_group_bridge_review_status.json", bridge_rows)
        _write_jsonl(reviews_dir / "canonical_major_group_bridge_scope_review_status.jsonl", bridge_rows)
        _write_group_reviews(reviews_dir, _GROUP_CODES)

        work_dir = root / "academyinfo_work" / "2025"
        _write_jsonl(work_dir / "departments.normalized.jsonl", [_dept_row("dept_cs")])
        _write_jsonl(
            work_dir / "classification_results.jsonl",
            [
                _cls_row(
                    "dept_cs", official_small_series_code=None, mapping_status="UNMAPPED",
                    decision_reason="공식 소계열이 미분류(N.C.E)라 근거가 없다",
                )
            ],
        )

        nce_review_path = reviews_dir / "academyinfo_nce_middle_series_review_status.jsonl"
        out = update_nce_middle_series_review(
            "99", decision="ACCEPT_GROUP_AS_REVIEW_CANDIDATE", comment="UI에서 후보로 인정", resolution_note=None,
            expected_revision=0, cluster_path=universe.nce_clusters_path, review_status_path=nce_review_path,
        )
        self.assertTrue(out.ok)

        inputs = load_inputs(
            data_dir=root, survey_year=2025, reviews_dir=reviews_dir,
            group_draft_path=universe.group_draft_path, bridge_draft_path=universe.bridge_draft_path,
            canonical_majors_path=universe.majors_path, small_series_code_table_path=universe.code_table_path,
            nce_clusters_path=universe.nce_clusters_path, nce_review_path=nce_review_path,
        )
        result = evaluate_department(_dept_row("dept_cs"), inputs)
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["blocked_reasons"], ["BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION"])
        self.assertNotIn("BLOCKED_NCE_UNRESOLVED", result["blocked_reasons"])


class CleanCloneMissingInputTest(unittest.TestCase):
    """CLI를 정규화·분류 결과가 없는 data-dir로 실행하면 종료 코드 2로 실패하고
    아무 파일도 쓰지 않아야 한다(`test_academyinfo_queue_clean_clone.py::
    MissingInputSafetyTest`와 같은 패턴).

    2026-08(a/final-mapping-review-closeout) 정정 — 이전 버전은 실제 저장소의
    `data/`를 그대로 `--data-dir`로 썼다("실제 저장소에는 정규화·분류 결과가 없다"는
    당시의 참인 사실에 의존). 그 작업이 §8 "최종 Review 정본으로 전국 Dry Run을
    실행"을 위해 이 Worktree 로컬에 실제로 그 두 파일(Git 제외 입력)을 생성한
    이후로는 이 가정이 더 이상 참이 아니다 — "정규화·분류 결과가 없으면 exit 2"라는
    이 테스트의 실제 취지는 그대로 두고, 그 상태를 완전히 빈 tmp data-dir로
    직접 만들어 검증한다(`load_inputs()`가 이 두 파일의 존재 여부를 다른 어떤
    입력보다 먼저 확인하므로, Group/Bridge/P1/N.C.E Fixture 없이도 exit 2가
    재현된다)."""

    def test_missing_generation_inputs_exits_2_and_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir()
            output_dir = Path(tmp) / "out"
            result = subprocess.run(
                [
                    sys.executable, str(_SCRIPT), "--survey-year", "2025",
                    "--data-dir", str(data_dir), "--output-dir", str(output_dir),
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

    def test_missing_p1_packet_raises_even_when_normalization_present(self) -> None:
        """2026-08-24 지시서 §1 — P1 Draft 패킷도 이제 필수 입력이다."""

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES))
            universe.p1_packet_path.unlink()
            work_dir = root / "academyinfo_work" / "2025"
            _write_jsonl(work_dir / "departments.normalized.jsonl", [_dept_row("dept_cs")])
            _write_jsonl(
                work_dir / "classification_results.jsonl",
                [_cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"])],
            )
            with self.assertRaises(MissingRequiredInputError):
                load_inputs(
                    data_dir=root, survey_year=2025, reviews_dir=root / "reviews",
                    group_draft_path=universe.group_draft_path, bridge_draft_path=universe.bridge_draft_path,
                    canonical_majors_path=universe.majors_path, small_series_code_table_path=universe.code_table_path,
                    p1_packet_path=universe.p1_packet_path, nce_clusters_path=universe.nce_clusters_path,
                )

    def test_missing_nce_clusters_raises_even_when_normalization_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            universe = _build_universe(root, approved_group_ids=frozenset(_GROUP_CODES))
            universe.nce_clusters_path.unlink()
            work_dir = root / "academyinfo_work" / "2025"
            _write_jsonl(work_dir / "departments.normalized.jsonl", [_dept_row("dept_cs")])
            _write_jsonl(
                work_dir / "classification_results.jsonl",
                [_cls_row("dept_cs", official_small_series_code="089", candidate_canonical_major_ids=["computer_science"])],
            )
            with self.assertRaises(MissingRequiredInputError):
                load_inputs(
                    data_dir=root, survey_year=2025, reviews_dir=root / "reviews",
                    group_draft_path=universe.group_draft_path, bridge_draft_path=universe.bridge_draft_path,
                    canonical_majors_path=universe.majors_path, small_series_code_table_path=universe.code_table_path,
                    p1_packet_path=universe.p1_packet_path, nce_clusters_path=universe.nce_clusters_path,
                )


class RealVsFixtureRunDistinctionTest(unittest.TestCase):
    """§10 "Fixture 검증과 실제 전국 실행을 완료 보고에서 구분" — 이 파일의 나머지
    READY_FOR_PROMOTION류 테스트가 합성 Fixture로만 검증된 것인지 실제 전국
    데이터로도 검증된 것인지, 완료 보고 시점에 헷갈리지 않도록 그 사실을 테스트로
    고정해둔다.

    2026-08-25(a/final-integration-master-promotion) 갱신 — §2 확정 Snapshot(SHA-256
    검증 완료, 대학알리미 API 재호출 없음)으로 §5 전국 Dry Run과 §6 전국 Master
    승격을 실제로 실행했다(완료 보고에 실측 결과를 남겼다). 두 생성 입력은 Git
    제외 로컬 전용 산출물이라 그대로 남아 있다 — Dry Run 증거(promotion_manifest.
    json/promotion_summary.json/.md)는 커밋 대상이다."""

    def test_real_national_generation_inputs_are_present_for_this_integration_round(self) -> None:
        """2026-08-25(a/national-master-promotion-final-wiring) 정정: departments.
        normalized.jsonl·classification_results.jsonl은 .gitignore 대상 대용량 작업
        산출물이라(data/academyinfo_work/*/*) 어느 로컬 세션이 마지막에 재생성했는지에
        따라 있다가도 없어진다 — Git 이력이 보증하지 않는 상태를 "실행 증거"로 삼으면
        이 테스트 자체가 세션마다 뒤집힌다. 실제로 커밋되는, 재현 가능한 증거는 전국
        1,072건 승격 산출물이다: national_master_promotion_candidates.jsonl(1,072건)·
        national_master_promotion_report.json과, 그 결과로 실제 교체된 운영 Master
        (data/master/departments.jsonl, 1,072건)."""
        candidates = (
            ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run"
            / "national_master_promotion_candidates.jsonl"
        )
        report = (
            ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run"
            / "national_master_promotion_report.json"
        )
        master = ROOT / "data" / "master" / "departments.jsonl"
        self.assertTrue(candidates.exists(), "전국 승격 후보 산출물이 없다 — §5/§6이 실제 데이터로 실행되지 않았다")
        self.assertTrue(report.exists(), "전국 승격 보고서가 없다 — §5/§6이 실제 데이터로 실행되지 않았다")
        candidate_rows = [l for l in candidates.read_text(encoding="utf-8").splitlines() if l.strip()]
        master_rows = [l for l in master.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.assertEqual(len(candidate_rows), 1072)
        self.assertEqual(len(master_rows), 1072)


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
