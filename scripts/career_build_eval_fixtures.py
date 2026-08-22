"""검증 입력 3종 생성 (작업자 C 소유) — C 지시서 §3 "검증 입력과 데이터 테스트".

1. RAG 검색 Query별 기대 문서와 허용 가능한 결과
2. Major-Trait · Subject-Trait · Canonical Mapping 기대값
3. LLM 장애 대비 질문 Cache

기대값은 사람이 먼저 적고, 이 스크립트가 실제 파이프라인을 돌려 어긋나면 멈춘다.
기대값을 실행 결과로부터 만들어 내지 않는다 — 그러면 무엇을 검증하는지 사라진다.

출력:
    data/eval_fixtures/rag_query_expectations.json
    data/eval_fixtures/mapping_expectations.json
    data/master/question_cache.jsonl

실행:
    python scripts/career_build_eval_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.canonical_mapper import CanonicalMapper, load_canonical_majors  # noqa: E402
from src.rag.retrieve import build_retriever_from_data_dir  # noqa: E402
from src.repositories.department_repository import JsonlDepartmentRepository  # noqa: E402

DATA_DIR = ROOT / "data"
FIXTURE_DIR = DATA_DIR / "eval_fixtures"
DRAFT_QUESTION_DIR = DATA_DIR / "drafts" / "question_blueprints"

# (질의, 필터로 쓸 학과 표기 또는 None, 상위 결과에 반드시 있어야 하는 source_url 조각, top_k)
RAG_EXPECTATIONS: list[dict] = [
    {
        "query": "컴퓨터공학부 졸업요건",
        "department": ["서울대학교", "컴퓨터공학부"],
        "expect_source_contains": "컴퓨터공학부",
        "expect_min_results": 1,
        "note": "학과 필터를 걸면 그 학과 문서만 나와야 한다.",
    },
    {
        "query": "미디어커뮤니케이션 교육과정 수용자 조사",
        "department": None,
        "expect_source_contains": "미디어커뮤니케이션학부",
        "expect_min_results": 1,
        "note": "필터 없이도 질의어와 맞는 문서가 1순위 근처에 와야 한다.",
    },
    {
        "query": "고교에서 준비하면 좋은 과목 물리학 미적분",
        "department": ["서울대학교", "기계공학부"],
        "expect_source_contains": "기계공학부",
        "expect_min_results": 1,
        "note": "본문에 있는 과목명으로도 문서를 찾을 수 있어야 한다.",
    },
    {
        "query": "존재하지 않는 학과의 장학금 규정",
        "department": ["부산대학교", "교육학과"],
        "expect_source_contains": None,
        "expect_min_results": 0,
        "note": "근거가 없으면 빈 결과여야 한다 — 아무 문서나 끌어오면 안 된다.",
    },
]

# (원본 학과 표기, 기대 canonical major, 기대 mapping_status)
CANONICAL_MAPPING_EXPECTATIONS: list[tuple[str, str, str, str]] = [
    ("서울대학교", "컴퓨터공학부", "computer_science", "AUTO_MAPPED"),
    ("연세대학교", "컴퓨터과학과", "computer_science", "AUTO_MAPPED"),
    ("고려대학교", "컴퓨터학과", "computer_science", "AUTO_MAPPED"),
    ("한양대학교", "커뮤니케이션디자인학과", "design", "AUTO_MAPPED"),
    ("서강대학교", "신문방송학전공", "media_communication", "AUTO_MAPPED"),
    ("충남대학교", "생물과학과", "life_science", "AUTO_MAPPED"),
    ("연세대학교", "경영학과", "business_administration", "AUTO_MAPPED"),
    # 자유전공학부는 어느 canonical major에도 대응되지 않는다 — 자동 확정하면 안 된다.
    ("충남대학교", "자유전공학부", "", "REVIEW_REQUIRED"),
]

# Subject-Trait Mapping 기대값: (과목명, 그 과목에서 가장 높은 등급이어야 하는 trait_id들)
SUBJECT_TRAIT_EXPECTATIONS: list[tuple[str, list[str]]] = [
    ("정보", ["tool_utilization"]),
    ("인공지능 기초", ["tool_utilization", "pattern_finding"]),
    ("미술 창작", ["visual_expression"]),
    ("인간과 심리", ["emotional_interpretation"]),
    ("생명과학", ["causal_analysis", "pattern_finding"]),
    ("창의 공학 설계", ["tool_utilization", "planning"]),
]

# Major-Trait Mapping 기대값: (major_id, 최고 등급이어야 하는 trait_id들)
MAJOR_TRAIT_EXPECTATIONS: list[tuple[str, list[str]]] = [
    ("computer_science", ["causal_analysis", "pattern_finding", "tool_utilization"]),
    ("design", ["visual_expression", "audience_response_prediction"]),
    ("education", ["planning", "collaboration_preference", "opinion_mediation", "emotional_interpretation"]),
    ("psychology", ["causal_analysis", "emotional_interpretation"]),
]


def _load_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def _department_index() -> dict[tuple[str, str], dict]:
    return {
        (row["university_name"], row["department_name"]): row
        for row in _load_jsonl(DATA_DIR / "master" / "departments.jsonl")
    }


def build_rag_expectations() -> list[dict]:
    retriever = build_retriever_from_data_dir(DATA_DIR)
    index = _department_index()
    rows: list[dict] = []

    for spec in RAG_EXPECTATIONS:
        department_id = None
        if spec["department"]:
            key = (spec["department"][0], spec["department"][1])
            if key not in index:
                raise SystemExit(f"master에 없는 학과: {key}")
            department_id = index[key]["department_id"]

        filters = {"related_department_id": department_id} if department_id else None
        results = retriever.search(spec["query"], filters=filters, top_k=5)

        if len(results) < spec["expect_min_results"]:
            raise SystemExit(
                f"질의 {spec['query']!r}: 결과 {len(results)}건으로 기대 최소 "
                f"{spec['expect_min_results']}건에 못 미친다"
            )
        if spec["expect_min_results"] == 0 and results:
            raise SystemExit(
                f"질의 {spec['query']!r}: 근거가 없어야 하는데 {len(results)}건이 나왔다"
            )
        needle = spec["expect_source_contains"]
        if needle and not any(needle in r.source_url for r in results):
            found = [r.source_url for r in results]
            raise SystemExit(f"질의 {spec['query']!r}: {needle!r}가 결과에 없다 — {found}")
        for result in results:  # 출처·기준일이 빠진 결과는 나가면 안 된다 (§19)
            if not result.source_url or result.as_of_date is None:
                raise SystemExit(f"질의 {spec['query']!r}: 출처 또는 기준일이 빠진 결과가 있다")

        rows.append(
            {
                "query": spec["query"],
                "filter_department_id": department_id,
                "expect_min_results": spec["expect_min_results"],
                "expect_source_contains": needle,
                "note": spec["note"],
                "observed_top_source_urls": [r.source_url for r in results],
            }
        )
    return rows


def build_mapping_expectations() -> dict:
    index = _department_index()
    repository = JsonlDepartmentRepository(path=DATA_DIR / "master" / "departments.jsonl")
    mapper = CanonicalMapper(load_canonical_majors(DATA_DIR / "master" / "canonical_majors.jsonl"))

    canonical_rows: list[dict] = []
    for university, department_name, expected_major, expected_status in CANONICAL_MAPPING_EXPECTATIONS:
        row = index.get((university, department_name))
        if row is None:
            raise SystemExit(f"master에 없는 학과: {university} {department_name}")
        department = repository.get(row["department_id"])
        assert department is not None
        result = mapper.map(department)
        if result.mapping_status != expected_status:
            raise SystemExit(
                f"{university} {department_name}: 기대 {expected_status}, 실제 {result.mapping_status}"
            )
        if expected_major and result.primary_candidate != expected_major:
            raise SystemExit(
                f"{university} {department_name}: 기대 {expected_major}, 실제 {result.primary_candidate}"
            )
        canonical_rows.append(
            {
                "university_name": university,
                "department_name": department_name,
                "department_id": department.department_id,
                "expected_primary_candidate": expected_major or None,
                "expected_mapping_status": expected_status,
            }
        )

    subject_by_label = {
        row["label"]: row for row in _load_jsonl(DATA_DIR / "master" / "subjects.jsonl")
    }
    subject_rows: list[dict] = []
    for label, expected_top_traits in SUBJECT_TRAIT_EXPECTATIONS:
        profile = subject_by_label.get(label)
        if profile is None:
            raise SystemExit(f"subjects.jsonl에 없는 과목: {label}")
        vector = profile["trait_vector"]
        top_value = max(vector.values())
        actual_top = sorted(t for t, v in vector.items() if v == top_value)
        if actual_top != sorted(expected_top_traits):
            raise SystemExit(f"{label}: 최고 등급 Trait 기대 {expected_top_traits}, 실제 {actual_top}")
        subject_rows.append(
            {
                "subject_id": profile["subject_id"],
                "label": label,
                "expected_top_trait_ids": sorted(expected_top_traits),
            }
        )

    major_by_id = {
        row["major_id"]: row for row in _load_jsonl(DATA_DIR / "master" / "major_profiles.jsonl")
    }
    major_rows: list[dict] = []
    for major_id, expected_top_traits in MAJOR_TRAIT_EXPECTATIONS:
        profile = major_by_id.get(major_id)
        if profile is None:
            raise SystemExit(f"major_profiles.jsonl에 없는 전공: {major_id}")
        merged: dict[str, float] = {}
        for key in ("interest_vector", "cognitive_vector", "work_style_vector", "environment_vector"):
            merged.update(profile[key])
        top_value = max(merged.values())
        actual_top = sorted(t for t, v in merged.items() if v == top_value)
        if actual_top != sorted(expected_top_traits):
            raise SystemExit(f"{major_id}: 최고 등급 Trait 기대 {expected_top_traits}, 실제 {actual_top}")
        major_rows.append(
            {"major_id": major_id, "expected_top_trait_ids": sorted(expected_top_traits)}
        )

    return {
        "canonical_mapping": canonical_rows,
        "subject_trait": subject_rows,
        "major_trait": major_rows,
    }


def build_question_cache() -> list[dict]:
    """LLM 장애 대비 질문 Cache — 비핵심 Context 10개의 Seed Question을 그대로 담는다.

    §11 Fallback이 요구하는 건 "미리 준비된 질문"이고, C가 만든 Seed Question 초안이
    그대로 그 역할을 한다. 핵심 5개용 Backup은 A가
    `src/data/questions/vertical_slice_backup_questions.py`에 이미 갖고 있다.
    """

    rows: list[dict] = []
    for path in sorted(DRAFT_QUESTION_DIR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(
            {
                "context_id": payload["context_id"],
                "usage": "llm_unavailable_fallback",
                "review_stage": payload["draft_entry"]["review_stage"],
                "seed_question": payload["seed_question"],
            }
        )
    (DATA_DIR / "master" / "question_cache.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    return rows


if __name__ == "__main__":
    use_utf8_stdout()
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    rag_rows = build_rag_expectations()
    (FIXTURE_DIR / "rag_query_expectations.json").write_text(
        json.dumps({"format_version": "rag_expectations_v1", "queries": rag_rows},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"RAG 기대값 {len(rag_rows)}건 — 전부 실제 검색 결과와 일치")

    mapping = build_mapping_expectations()
    (FIXTURE_DIR / "mapping_expectations.json").write_text(
        json.dumps({"format_version": "mapping_expectations_v1", **mapping},
                   ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Mapping 기대값 — Canonical {}건 / Subject {}건 / Major {}건".format(
            len(mapping["canonical_mapping"]), len(mapping["subject_trait"]), len(mapping["major_trait"])
        )
    )

    cache = build_question_cache()
    print(f"질문 Cache {len(cache)}건 — data/master/question_cache.jsonl")
