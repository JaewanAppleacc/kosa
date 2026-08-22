"""저장소에 실제로 들어 있는 데이터 파일이 계약을 지키는지 확인한다.

앞의 테스트들이 "코드가 규칙대로 도는가"를 본다면, 여기는 "지금 커밋돼 있는 데이터가
그 규칙을 통과하는가"를 본다. 데이터만 바꾸고 코드를 안 건드린 커밋에서 계약이 깨지는
경우를 잡기 위한 것이다.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from eval.trait_eval import evaluate_persona_against_fixture
from src.agents.course.course_document_parser import SubjectAliasIndex
from src.engines.admission_filter import assert_single_group, validate_group_field
from src.engines.canonical_mapper import CanonicalMapper, confirm, load_canonical_majors
from src.rag.embed import HashingEmbedder
from src.rag.retrieve import build_retriever_from_data_dir
from src.repositories.admission_repository import (
    JsonlAdmissionRepository,
    load_admission_references,
)
from src.repositories.department_repository import JsonlDepartmentRepository, load_departments
from src.schemas.course import SubjectProfile
from src.schemas.major import MajorProfile
from src.schemas.mcp_contracts import AdmissionSearchCriteria
from src.schemas.persona import HandCalculatedFixture, Persona
from src.schemas.question import OptionBlueprint, SeedQuestion
from src.schemas.review import DraftEntry

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"


def read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


class MasterDataTest(unittest.TestCase):
    def test_departments_load_and_are_unique(self) -> None:
        departments = load_departments(DATA_DIR / "master" / "departments.jsonl")
        self.assertGreaterEqual(len(departments), 20)
        ids = [d.department_id for d in departments]
        self.assertEqual(len(ids), len(set(ids)))
        for department in departments:
            self.assertTrue(department.source_url.startswith("http"))

    def test_every_department_has_a_mapping_result(self) -> None:
        departments = load_departments(DATA_DIR / "master" / "departments.jsonl")
        results = read_jsonl(DATA_DIR / "master" / "canonical_mapping_results.jsonl")
        self.assertEqual({d.department_id for d in departments}, {r["department_id"] for r in results})

    def test_unconfirmed_mapping_is_never_promoted(self) -> None:
        """REVIEW_REQUIRED인 학과에 canonical_major_id가 채워져 있으면 안 된다 (§8 완료 조건).

        2026-08-22 8차: CONFIRMED(canonical_mapper.confirm() — 사람이 검토해 확정하는
        유일한 경로)는 AUTO_MAPPED와 마찬가지로 "확정된" 상태라 채워져 있는 게 맞다.
        아직 확정되지 않은 REVIEW_REQUIRED만 이 검사 대상이다."""

        departments = {d.department_id: d for d in load_departments(DATA_DIR / "master" / "departments.jsonl")}
        for row in read_jsonl(DATA_DIR / "master" / "canonical_mapping_results.jsonl"):
            if row["mapping_status"] not in ("AUTO_MAPPED", "CONFIRMED"):
                self.assertIsNone(departments[row["department_id"]].canonical_major_id)

    def test_mapping_is_reproducible_from_current_data(self) -> None:
        """2026-08-22 8차: CONFIRMED 결과는 CanonicalMapper.map()이 스스로 만들지 않는다
        (사람이 confirm()으로 확정한 것만 CONFIRMED가 된다) — 그래서 이 재현성 검사는
        저장된 data/master/canonical_mapping_manual_confirmations.jsonl을 "현재 데이터"의
        일부로 취급해, map() 결과에 그 확정을 다시 적용한 뒤 비교한다. 그래야 손으로 고쳐
        저장한 결과와 실제 파이프라인 산출물이 갈라지는 걸 여전히 잡아낸다."""

        repository = JsonlDepartmentRepository(path=DATA_DIR / "master" / "departments.jsonl")
        mapper = CanonicalMapper(
            load_canonical_majors(DATA_DIR / "master" / "canonical_majors.jsonl"),
            embedder=HashingEmbedder(),
        )
        stored = {r["department_id"]: r for r in read_jsonl(DATA_DIR / "master" / "canonical_mapping_results.jsonl")}
        manual_path = DATA_DIR / "master" / "canonical_mapping_manual_confirmations.jsonl"
        manual_by_department_id = {
            row["department_id"]: row for row in (read_jsonl(manual_path) if manual_path.exists() else [])
        }

        for department in repository.all():
            result = mapper.map(department)
            manual = manual_by_department_id.get(department.department_id)
            if manual is not None:
                result = confirm(result, manual["reviewer_id"], manual["chosen_major_id"])
            self.assertEqual(result.mapping_status, stored[department.department_id]["mapping_status"])
            self.assertEqual(result.primary_candidate, stored[department.department_id]["primary_candidate"])

    def test_major_profiles_cover_all_traits(self) -> None:
        rows = read_jsonl(DATA_DIR / "master" / "major_profiles.jsonl")
        self.assertGreaterEqual(len(rows), 5)  # 지시서 §3: 대표 전공 5~8개
        self.assertLessEqual(len(rows), 8)
        for row in rows:
            profile = MajorProfile.model_validate(row)
            merged = {
                **profile.interest_vector,
                **profile.cognitive_vector,
                **profile.work_style_vector,
                **profile.environment_vector,
            }
            self.assertEqual(len(merged), 12)

    def test_subject_aliases_are_unambiguous(self) -> None:
        index = SubjectAliasIndex.load(DATA_DIR / "master" / "subject_aliases.jsonl")
        subjects = [SubjectProfile.model_validate(r) for r in read_jsonl(DATA_DIR / "master" / "subjects.jsonl")]
        for subject in subjects:
            matched = index.exact(subject.label)
            self.assertIsNotNone(matched, msg=f"{subject.label} alias 누락")
            self.assertEqual(matched[0], subject.subject_id)


class AdmissionDataTest(unittest.TestCase):
    def setUp(self) -> None:
        self.references = load_admission_references(
            DATA_DIR / "admissions" / "admission_references.jsonl"
        )

    def test_comparability_group_matches_derivation(self) -> None:
        self.assertEqual(validate_group_field(self.references), [])

    def test_at_least_fifteen_departments_covered(self) -> None:
        """지시서 §3: 공식 비교 자료가 존재하는 학과 15~30개."""

        self.assertGreaterEqual(len({r.department_id for r in self.references}), 15)

    def test_repository_never_mixes_groups(self) -> None:
        repository = JsonlAdmissionRepository(self.references)
        for department_id in {r.department_id for r in self.references}:
            rows = repository.find_comparable(AdmissionSearchCriteria(department_id=department_id))
            assert_single_group(rows)

    def test_unverified_rows_carry_no_score(self) -> None:
        """출처가 확정되기 전에는 컷 점수를 채우지 않는다 — 검증되지 않은 수치를 만들지 않기 위해."""

        for reference in self.references:
            if reference.review_status == "draft":
                self.assertIsNone(reference.score_50_cut)
                self.assertIsNone(reference.score_70_cut)


class RagCorpusTest(unittest.TestCase):
    def test_sources_have_url_and_as_of_date(self) -> None:
        for row in read_jsonl(DATA_DIR / "rag" / "sources.jsonl"):
            self.assertTrue(row["source_url"])
            self.assertTrue(row["as_of_date"])

    def test_sample_documents_are_marked_as_non_official(self) -> None:
        """공식 자료가 아닌 문서는 sample:// 로 시작해 공식 출처와 섞이지 않아야 한다."""

        for row in read_jsonl(DATA_DIR / "rag" / "sources.jsonl"):
            if "샘플" in row["document_type"]:
                self.assertTrue(row["source_url"].startswith("sample://"))

    def test_shipped_corpus_search_returns_sourced_results(self) -> None:
        retriever = build_retriever_from_data_dir(DATA_DIR)
        self.assertGreater(len(retriever), 0)
        results = retriever.search("졸업요건", top_k=3)
        self.assertTrue(results)
        for item in results:
            self.assertTrue(item.source_url)
            self.assertIsNotNone(item.as_of_date)

    def test_rag_query_expectations_still_hold(self) -> None:
        payload = json.loads(
            (DATA_DIR / "eval_fixtures" / "rag_query_expectations.json").read_text(encoding="utf-8")
        )
        retriever = build_retriever_from_data_dir(DATA_DIR)
        for spec in payload["queries"]:
            filters = (
                {"related_department_id": spec["filter_department_id"]}
                if spec["filter_department_id"]
                else None
            )
            results = retriever.search(spec["query"], filters=filters, top_k=5)
            self.assertGreaterEqual(len(results), spec["expect_min_results"], msg=spec["query"])
            if spec["expect_min_results"] == 0:
                self.assertEqual(results, [], msg=spec["query"])
            if spec["expect_source_contains"]:
                self.assertTrue(
                    any(spec["expect_source_contains"] in r.source_url for r in results),
                    msg=spec["query"],
                )


class DraftTest(unittest.TestCase):
    def test_every_draft_has_valid_metadata(self) -> None:
        paths = sorted((DATA_DIR / "drafts").rglob("*.json"))
        self.assertGreater(len(paths), 0)
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry = DraftEntry.model_validate(payload["draft_entry"])
            self.assertEqual(entry.author_id, "worker_c")
            self.assertIsNotNone(entry.as_of_date)

    def test_question_blueprints_pass_lint(self) -> None:
        paths = sorted((DATA_DIR / "drafts" / "question_blueprints").glob("*.json"))
        self.assertEqual(len(paths), 10)  # 비핵심 Context 10개
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            question = SeedQuestion.model_validate(payload["seed_question"])
            blueprint = OptionBlueprint.model_validate(payload["option_blueprint"])
            self.assertEqual(len(question.options), 5)
            self.assertEqual(len(blueprint.roles), 5)

    def test_core_contexts_are_not_authored_by_c(self) -> None:
        """핵심 5개 Context의 Seed Question은 A 소유다 — C 초안에 들어오면 안 된다."""

        from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS

        core = {c.context_id for c in CONTEXT_DEFINITIONS if c.is_core}
        authored = {
            json.loads(p.read_text(encoding="utf-8"))["context_id"]
            for p in (DATA_DIR / "drafts" / "question_blueprints").glob("*.json")
        }
        self.assertEqual(core & authored, set())


class PersonaFixtureTest(unittest.TestCase):
    def test_every_shipped_persona_matches_the_engine(self) -> None:
        paths = sorted((DATA_DIR / "eval_fixtures" / "personas").glob("*.json"))
        self.assertGreaterEqual(len(paths), 4)
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            persona = Persona.model_validate(payload["persona"])
            fixture = HandCalculatedFixture.model_validate(payload["hand_calculated_fixture"])
            blueprints = {
                question_id: OptionBlueprint.model_validate(blueprint)
                for question_id, blueprint in payload["option_blueprints"].items()
            }
            result = evaluate_persona_against_fixture(persona, fixture, blueprints)
            self.assertTrue(result.passed, msg=f"{path.name}: {result.mismatches}")

    def test_fixture_is_self_contained(self) -> None:
        """A의 Harness가 다른 모듈을 import하지 않고 파일 하나만 읽어도 되도록."""

        for path in sorted((DATA_DIR / "eval_fixtures" / "personas").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            persona = Persona.model_validate(payload["persona"])
            self.assertEqual(
                {a.question_id for a in persona.answers}, set(payload["option_blueprints"])
            )

    def test_calculation_notes_explain_the_number(self) -> None:
        for path in sorted((DATA_DIR / "eval_fixtures" / "personas").glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            fixture = HandCalculatedFixture.model_validate(payload["hand_calculated_fixture"])
            for expectation in fixture.trait_expectations:
                self.assertGreaterEqual(len(expectation.calculation_notes), 15)


class ThresholdRationaleTest(unittest.TestCase):
    """코드에 박힌 임계값이 "지금 데이터에서도" 근거를 유지하는지 본다.

    근거를 문서에만 적어 두면 데이터가 바뀐 뒤에도 옛날 주장이 그대로 남는다. 문턱을
    정당화한 측정 자체를 테스트로 고정해, 데이터가 바뀌어 분리가 깨지면 실패하게 한다.
    """

    def setUp(self) -> None:
        from scripts.career_measure_thresholds import run

        self.measurements = run()

    def test_subject_alias_threshold_separates_true_and_false_matches(self) -> None:
        m = self.measurements["fuzzy_threshold"]
        self.assertLess(
            m["highest_false_positive"],
            m["threshold"],
            msg="다른 과목인데 문턱을 넘는 표기가 생겼다 — 잘못된 매칭이 사용자에게 제안된다",
        )
        self.assertLessEqual(
            m["threshold"],
            m["lowest_true_positive"],
            msg="같은 과목인데 문턱에 못 미치는 표기가 생겼다",
        )

    def test_search_floor_separates_grounded_and_ungrounded_queries(self) -> None:
        m = self.measurements["query_coverage"]
        self.assertLess(
            m["highest_ungrounded"],
            m["threshold"],
            msg="코퍼스에 근거가 없는 질의가 바닥선을 넘었다 — 근거 없는 결과가 나간다",
        )
        self.assertLessEqual(m["threshold"], m["lowest_grounded"])

    def test_no_chunk_exceeds_the_configured_size(self) -> None:
        m = self.measurements["chunk_size"]
        self.assertLessEqual(m["max_length"], m["chunk_size"])


class DataQualityAuditTest(unittest.TestCase):
    def test_audit_reports_no_error(self) -> None:
        from scripts.career_audit_data_quality import run

        findings = run()
        errors = [f for f in findings.items if f["severity"] == "ERROR"]
        self.assertEqual(errors, [], msg=f"데이터 품질 ERROR {len(errors)}건")


if __name__ == "__main__":
    unittest.main()
