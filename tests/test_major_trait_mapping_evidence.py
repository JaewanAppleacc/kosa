"""2026-08-22 12차 리뷰 — Major-Trait Mapping 근거 기반 확정 작업의 §13 필수 테스트 28개.

네 카테고리 그대로 나눈다: Trait Ontology(1~6) / Major-Trait Evidence(7~15) /
Profile Build(16~22) / Matching 회귀(23~28). 각 테스트 docstring에 지시서 번호를 그대로
남겨서, 나중에 지시서와 대조하기 쉽게 한다.

정상 테스트는 LLM·Embedding·LangSmith 등 실제 네트워크 호출을 절대 하지 않는다 — 전부
이미 저장된 데이터 파일과 결정론적 빌드 함수만 사용한다.
"""

from __future__ import annotations

import inspect
import unittest

from pydantic import ValidationError

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS
from src.engines.matching_engine import compute_major_match, compute_student_trait_states
from src.schemas.evidence import TraitEvidenceSummary
from src.schemas.major import MajorProfile, MajorRelevance
from src.services.major_trait_mapping_evidence import (
    MajorTraitMappingRecord,
    load_major_trait_mapping_evidence,
)

from scripts.career_build_major_profiles import (
    EVIDENCE_BASED_MAJOR_LABELS,
    build_evidence_based_profiles,
)

_ALLOWED_VECTOR_GROUPS = {"interest", "cognitive", "work_style", "environment"}
_ALLOWED_GROUNDING_TYPES = {"ONET_STRONG", "ONET_PARTIAL", "RIASEC_REFERENCE", "TEAM_DEFINED"}
_ALLOWED_NORMALIZED_VALUES = {0.0, 0.33, 0.67, 1.00}


class TraitOntologyAuditTest(unittest.TestCase):
    """§13 1~6."""

    def setUp(self) -> None:
        self.traits = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}

    def test_1_twelve_trait_ids_have_no_duplicates(self) -> None:
        ids = [t.trait_id for t in VERTICAL_SLICE_TRAITS]
        self.assertEqual(len(ids), 12)
        self.assertEqual(len(ids), len(set(ids)))

    def test_2_definition_and_indicators_are_non_empty(self) -> None:
        for trait in VERTICAL_SLICE_TRAITS:
            self.assertTrue(trait.definition.strip(), msg=trait.trait_id)
            self.assertTrue(trait.positive_indicators, msg=trait.trait_id)
            self.assertTrue(trait.conflicting_indicators, msg=trait.trait_id)

    def test_3_every_trait_has_a_grounding_type(self) -> None:
        for trait in VERTICAL_SLICE_TRAITS:
            self.assertIn(trait.grounding_type, _ALLOWED_GROUNDING_TYPES, msg=trait.trait_id)

    def test_4_team_defined_traits_are_not_overstated_as_onet_grounded(self) -> None:
        """immediate_execution/opinion_mediation/audience_response_prediction은 O*NET/Holland
        공식 대응이 없어 TEAM_DEFINED로 확정됐다 — source_references가 "팀 정의"로 시작해야
        하고, "강함"/"보통"으로 시작해 O*NET 근거를 주장하면 안 된다."""

        team_defined = {t.trait_id for t in VERTICAL_SLICE_TRAITS if t.grounding_type == "TEAM_DEFINED"}
        self.assertEqual(
            team_defined, {"immediate_execution", "opinion_mediation", "audience_response_prediction"}
        )
        for trait_id in team_defined:
            reference = self.traits[trait_id].source_references[0]
            self.assertTrue(reference.startswith("팀 정의"), msg=trait_id)

    def test_5_primary_vector_group_is_an_allowed_value(self) -> None:
        for trait in VERTICAL_SLICE_TRAITS:
            self.assertIn(trait.primary_vector_group, _ALLOWED_VECTOR_GROUPS, msg=trait.trait_id)

    def test_6_similar_trait_distinction_records_exist(self) -> None:
        """outputs/trait_ontology_draft.md §2-1에 지시서가 요구한 7개 쌍이 모두 문서화돼
        있는지 확인한다 — 사람이 읽는 문서지만, 이 테스트가 없으면 문서가 조용히 삭제돼도
        아무도 못 잡는다."""

        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "outputs" / "trait_ontology_draft.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("2-1", text)
        required_pairs = [
            "causal_analysis vs pattern_finding",
            "planning vs immediate_execution",
            "planning vs information_comparison",
            "collaboration_preference vs opinion_mediation",
            "emotional_interpretation vs audience_response_prediction",
            "visual_expression vs tool_utilization",
            "change_adaptation vs immediate_execution",
        ]
        for pair in required_pairs:
            self.assertIn(pair, text, msg=pair)


class MajorTraitMappingEvidenceTest(unittest.TestCase):
    """§13 7~15."""

    def setUp(self) -> None:
        self.records = load_major_trait_mapping_evidence()
        self.trait_ids = {t.trait_id for t in VERTICAL_SLICE_TRAITS}

    def test_7_every_major_id_is_a_representative_major(self) -> None:
        for record in self.records:
            self.assertIn(record.major_id, EVIDENCE_BASED_MAJOR_LABELS, msg=record.major_id)

    def test_8_every_trait_id_exists_in_current_ontology(self) -> None:
        for record in self.records:
            self.assertIn(record.trait_id, self.trait_ids, msg=f"{record.major_id}/{record.trait_id}")

    def test_9_evidenced_mappings_have_at_least_one_evidence_entry(self) -> None:
        for record in self.records:
            if record.mapping_status in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
                self.assertGreaterEqual(
                    len(record.evidence), 1, msg=f"{record.major_id}/{record.trait_id}"
                )

    def test_10_evidence_urls_are_https(self) -> None:
        for record in self.records:
            for evidence in record.evidence:
                self.assertTrue(
                    evidence.source_url.startswith("https://"),
                    msg=f"{record.major_id}/{record.trait_id}: {evidence.source_url}",
                )

    def test_11_no_sample_blog_community_or_namuwiki_urls(self) -> None:
        banned_substrings = ("sample://", "namu.wiki", "blog", "cafe.naver", "community", "tistory")
        for record in self.records:
            for evidence in record.evidence:
                url = evidence.source_url.lower()
                for banned in banned_substrings:
                    self.assertNotIn(banned, url, msg=f"{record.major_id}/{record.trait_id}: {url}")

    def test_12_grade_is_an_integer_0_to_3(self) -> None:
        for record in self.records:
            if record.grade is not None:
                self.assertIsInstance(record.grade, int, msg=f"{record.major_id}/{record.trait_id}")
                self.assertIn(record.grade, (0, 1, 2, 3), msg=f"{record.major_id}/{record.trait_id}")

    def test_13_unmapped_is_never_converted_to_a_zero_score(self) -> None:
        """공식 근거를 찾지 못함 ≠ Trait 중요도 0 — UNMAPPED/REVIEW_REQUIRED 레코드는
        grade가 아예 없어야 한다(0이 아니라 None)."""

        for record in self.records:
            if record.mapping_status in ("UNMAPPED", "REVIEW_REQUIRED"):
                self.assertIsNone(record.grade, msg=f"{record.major_id}/{record.trait_id}")

    def test_14_no_duplicate_major_trait_pairs(self) -> None:
        pairs = [(r.major_id, r.trait_id) for r in self.records]
        self.assertEqual(len(pairs), len(set(pairs)))

    def test_15_no_grade_3_without_evidence(self) -> None:
        for record in self.records:
            if record.grade == 3:
                self.assertGreater(
                    len(record.evidence), 0, msg=f"{record.major_id}/{record.trait_id}"
                )


class MappingStatusGradeSchemaTest(unittest.TestCase):
    """2026-08-23 13차 리뷰 §2: 상태별 허용 grade 범위를 Pydantic ValidationError로 강제하는지
    확인한다. mapping_status가 EVIDENCED/NO_DIRECT_EVIDENCE/REVIEW_REQUIRED/UNMAPPED 4개, grade가
    None/0/1/2/3 5개인 20개 조합을 전부 명시적으로 검증한다 — 어느 조합이 왜 허용/차단되는지
    표로 명확히 남긴다."""

    def _record(self, mapping_status: str, grade: int | None, *, with_evidence: bool) -> dict:
        payload = {
            "major_id": "industrial_engineering",
            "trait_id": "causal_analysis",
            "mapping_status": mapping_status,
            "grade": grade,
            "author_id": "worker_a",
            "mapping_version": "test_v1",
        }
        if with_evidence:
            payload["evidence"] = [
                {
                    "university_name": "테스트대학교",
                    "department_name": "테스트학과",
                    "evidence_type": "OFFICIAL_CURRICULUM",
                    "course_or_goal": "테스트 교과",
                    "source_url": "https://example.ac.kr/curriculum",
                    "reason": "테스트용",
                }
            ]
        return payload

    def test_evidenced_accepts_grade_1_to_3_with_evidence(self) -> None:
        for grade in (1, 2, 3):
            MajorTraitMappingRecord.model_validate(
                self._record("EVIDENCED", grade, with_evidence=True)
            )

    def test_evidenced_rejects_grade_0(self) -> None:
        with self.assertRaises(ValidationError):
            MajorTraitMappingRecord.model_validate(
                self._record("EVIDENCED", 0, with_evidence=True)
            )

    def test_evidenced_rejects_grade_none(self) -> None:
        with self.assertRaises(ValidationError):
            MajorTraitMappingRecord.model_validate(
                self._record("EVIDENCED", None, with_evidence=True)
            )

    def test_no_direct_evidence_accepts_only_grade_0_with_evidence(self) -> None:
        MajorTraitMappingRecord.model_validate(
            self._record("NO_DIRECT_EVIDENCE", 0, with_evidence=True)
        )

    def test_no_direct_evidence_rejects_grade_1_to_3(self) -> None:
        for grade in (1, 2, 3):
            with self.assertRaises(ValidationError):
                MajorTraitMappingRecord.model_validate(
                    self._record("NO_DIRECT_EVIDENCE", grade, with_evidence=True)
                )

    def test_no_direct_evidence_rejects_grade_none(self) -> None:
        with self.assertRaises(ValidationError):
            MajorTraitMappingRecord.model_validate(
                self._record("NO_DIRECT_EVIDENCE", None, with_evidence=True)
            )

    def test_review_required_accepts_only_grade_none(self) -> None:
        MajorTraitMappingRecord.model_validate(
            self._record("REVIEW_REQUIRED", None, with_evidence=False)
        )

    def test_review_required_rejects_any_grade(self) -> None:
        for grade in (0, 1, 2, 3):
            with self.assertRaises(ValidationError):
                MajorTraitMappingRecord.model_validate(
                    self._record("REVIEW_REQUIRED", grade, with_evidence=True)
                )

    def test_unmapped_accepts_only_grade_none(self) -> None:
        MajorTraitMappingRecord.model_validate(
            self._record("UNMAPPED", None, with_evidence=False)
        )

    def test_unmapped_rejects_any_grade(self) -> None:
        for grade in (0, 1, 2, 3):
            with self.assertRaises(ValidationError):
                MajorTraitMappingRecord.model_validate(
                    self._record("UNMAPPED", grade, with_evidence=True)
                )

    def test_evidenced_without_evidence_list_is_rejected_regardless_of_grade_fix(self) -> None:
        """근거 목록이 비어 있으면 grade가 Rubric상 유효한 값이어도(1~3) 여전히 막혀야 한다 —
        상태별 등급 범위 검사가 기존 '근거 필수' 검사를 대체하는 게 아니라 추가되는 것임을 확인."""

        with self.assertRaises(ValidationError):
            MajorTraitMappingRecord.model_validate(
                self._record("EVIDENCED", 2, with_evidence=False)
            )


class ProfileBuildTest(unittest.TestCase):
    """§13 16~22."""

    def setUp(self) -> None:
        self.profiles = {p.major_id: p for p in build_evidence_based_profiles()}
        self.trait_group_by_id = {t.trait_id: t.primary_vector_group for t in VERTICAL_SLICE_TRAITS}

    def _merged_vector(self, profile: MajorProfile) -> dict[str, float]:
        return {
            **profile.interest_vector,
            **profile.cognitive_vector,
            **profile.work_style_vector,
            **profile.environment_vector,
        }

    def test_16_rerunning_with_same_input_is_byte_identical(self) -> None:
        first = [p.model_dump_json() for p in build_evidence_based_profiles()]
        second = [p.model_dump_json() for p in build_evidence_based_profiles()]
        self.assertEqual(first, second)

    def test_17_profile_traits_are_placed_in_the_correct_vector_group(self) -> None:
        for profile in self.profiles.values():
            for group_name, vector in (
                ("interest", profile.interest_vector),
                ("cognitive", profile.cognitive_vector),
                ("work_style", profile.work_style_vector),
                ("environment", profile.environment_vector),
            ):
                for trait_id in vector:
                    self.assertEqual(
                        self.trait_group_by_id[trait_id], group_name, msg=f"{profile.major_id}/{trait_id}"
                    )

    def test_18_normalized_values_are_one_of_the_four_allowed(self) -> None:
        for profile in self.profiles.values():
            for value in self._merged_vector(profile).values():
                self.assertIn(value, _ALLOWED_NORMALIZED_VALUES, msg=profile.major_id)

    def test_19_all_three_vertical_slice_profiles_are_generated(self) -> None:
        self.assertEqual(set(self.profiles), {"media_communication", "hci_ux", "industrial_engineering"})

    def test_20_source_ids_are_non_empty(self) -> None:
        for profile in self.profiles.values():
            self.assertTrue(profile.source_ids, msg=profile.major_id)

    def test_21_runtime_and_master_profile_values_match(self) -> None:
        """단일 정본 확인 — Runtime Loader(vertical_slice_major_profiles.py)가 읽은 값과
        빌드 함수가 방금 만든 값이 (재실행 없이도) 똑같아야 한다."""

        from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES

        by_id = {p.major_id: p for p in VERTICAL_SLICE_MAJOR_PROFILES}
        for major_id, built in self.profiles.items():
            self.assertEqual(by_id[major_id].model_dump(), built.model_dump(), msg=major_id)

    def test_22_no_manually_duplicated_vector_remains_in_runtime(self) -> None:
        """vertical_slice_major_profiles.py가 정본(data/master/major_profiles.jsonl)에서
        읽는 얇은 Loader로만 남아 있는지 — 사람이 손으로 MajorProfile(...)을 다시 만들면
        정본과 갈라질 수 있으므로, 소스 코드 자체에 MajorProfile( 생성자 호출이 없는지
        확인한다(model_validate_json으로만 읽어야 한다)."""

        import src.data.majors.vertical_slice_major_profiles as module

        source = inspect.getsource(module)
        self.assertNotIn("MajorProfile(", source)
        self.assertIn("model_validate_json", source)


class VerticalSliceLoaderTest(unittest.TestCase):
    """2026-08-23 13차 리뷰 §3: `load_vertical_slice_major_profiles`의 중복 방지·필수 전공
    누락 차단·순서 보장을 직접 임시 파일로 확인한다(실제 정본 파일을 건드리지 않는다)."""

    def _row(self, major_id: str, label: str = "테스트 라벨") -> str:
        import json as _json

        return _json.dumps(
            {
                "major_id": major_id,
                "label": label,
                "interest_vector": {},
                "cognitive_vector": {},
                "work_style_vector": {},
                "environment_vector": {},
                "source_ids": ["https://example.ac.kr/"],
                "extraction_method": "rule",
                "review_status": "draft",
                "profile_version": "test_v1",
                "updated_at": "2026-08-23T00:00:00Z",
            },
            ensure_ascii=False,
        )

    def _write(self, tmp_path, lines: list[str]):
        tmp_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return tmp_path

    def test_normal_file_loads_successfully(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        from src.data.majors.vertical_slice_major_profiles import load_vertical_slice_major_profiles

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write(
                _Path(tmp_dir) / "major_profiles.jsonl",
                [
                    self._row("media_communication"),
                    self._row("hci_ux"),
                    self._row("industrial_engineering"),
                    self._row("computer_science"),  # Vertical Slice 3개 아닌 행은 무시돼야 함
                ],
            )
            profiles = load_vertical_slice_major_profiles(path)
            self.assertEqual(
                [p.major_id for p in profiles],
                ["media_communication", "hci_ux", "industrial_engineering"],
            )

    def test_missing_required_major_is_blocked(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        from src.data.majors.vertical_slice_major_profiles import load_vertical_slice_major_profiles

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write(
                _Path(tmp_dir) / "major_profiles.jsonl",
                [self._row("media_communication"), self._row("hci_ux")],  # industrial_engineering 누락
            )
            with self.assertRaises(ValueError):
                load_vertical_slice_major_profiles(path)

    def test_duplicate_major_id_is_blocked_not_silently_overwritten(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        from src.data.majors.vertical_slice_major_profiles import load_vertical_slice_major_profiles

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = self._write(
                _Path(tmp_dir) / "major_profiles.jsonl",
                [
                    self._row("media_communication", label="첫 번째 값"),
                    self._row("hci_ux"),
                    self._row("industrial_engineering"),
                    self._row("media_communication", label="두 번째 값(중복)"),
                ],
            )
            with self.assertRaises(ValueError):
                load_vertical_slice_major_profiles(path)

    def test_return_order_follows_vertical_slice_major_ids_regardless_of_file_row_order(self) -> None:
        import tempfile
        from pathlib import Path as _Path

        from src.data.majors.vertical_slice_major_profiles import (
            VERTICAL_SLICE_MAJOR_IDS,
            load_vertical_slice_major_profiles,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            # 파일 안 순서를 VERTICAL_SLICE_MAJOR_IDS 선언 순서와 일부러 다르게 뒤섞는다.
            path = self._write(
                _Path(tmp_dir) / "major_profiles.jsonl",
                [
                    self._row("industrial_engineering"),
                    self._row("media_communication"),
                    self._row("hci_ux"),
                ],
            )
            profiles = load_vertical_slice_major_profiles(path)
            self.assertEqual([p.major_id for p in profiles], list(VERTICAL_SLICE_MAJOR_IDS))


class MatchingRegressionTest(unittest.TestCase):
    """§13 23~28."""

    def setUp(self) -> None:
        from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES

        self.majors = {m.major_id: m for m in VERTICAL_SLICE_MAJOR_PROFILES}
        self.trait_defs = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}

    def test_23_existing_schema_fields_are_preserved(self) -> None:
        self.assertEqual(
            set(MajorProfile.model_fields),
            {
                "major_id", "label", "interest_vector", "cognitive_vector", "work_style_vector",
                "environment_vector", "source_ids", "extraction_method", "review_status",
                "profile_version", "updated_at",
            },
        )
        self.assertEqual(
            set(MajorRelevance.model_fields),
            {"major_id", "label", "relevance_label", "evidence_sufficiency", "repeated_context_count"},
        )

    def test_24_fixed_persona_matching_is_deterministic(self) -> None:
        summaries = {
            trait_id: TraitEvidenceSummary(
                trait_id=trait_id, support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
            )
            for trait_id in self.trait_defs
        }
        states = compute_student_trait_states(summaries, self.trait_defs, set())
        first = compute_major_match(states, self.majors["industrial_engineering"])
        second = compute_major_match(states, self.majors["industrial_engineering"])
        self.assertEqual(first.model_dump(), second.model_dump())

    def test_25_ranking_shift_fixtures_document_their_reasoning(self) -> None:
        """근거 기반 Profile로 바뀌며 순위가 실제로 바뀐 Fixture(tests/test_matching_engine.py
        FixedPersonaVerticalSliceMatchingTest, tests/test_vertical_slice_major_department_
        alignment.py FixedPersonaEndToEndTest::test_persona_a)가 "왜 바뀌었는지" docstring에
        근거를 남겼는지 확인한다 — 조용히 숫자만 바꾸지 않았다는 증거."""

        from pathlib import Path

        root = Path(__file__).resolve().parent
        matching_text = (root / "test_matching_engine.py").read_text(encoding="utf-8")
        alignment_text = (root / "test_vertical_slice_major_department_alignment.py").read_text(encoding="utf-8")
        for text in (matching_text, alignment_text):
            self.assertIn("12차 리뷰", text)
        self.assertIn("빅데이터분석과미디어", matching_text)

    def test_26_hci_ux_profile_has_no_industrial_design_evidence(self) -> None:
        records = load_major_trait_mapping_evidence()
        for record in records:
            if record.major_id != "hci_ux":
                continue
            for evidence in record.evidence:
                self.assertNotIn("산업디자인", evidence.department_name, msg=record.trait_id)
                self.assertNotIn("서울여대", evidence.university_name, msg=record.trait_id)

    def test_27_arts_and_pe_majors_are_not_added_to_the_recommendation_list(self) -> None:
        from src.services.major_exploration_service import EXCLUDED_RECOMMENDATION_MAJOR_IDS

        self.assertIn("design", EXCLUDED_RECOMMENDATION_MAJOR_IDS)
        self.assertNotIn("design", self.majors)
        self.assertNotIn("design", EVIDENCE_BASED_MAJOR_LABELS)

    def test_28_unmapped_traits_are_never_miscalculated_as_a_zero_score_mismatch(self) -> None:
        """hci_ux 벡터에는 causal_analysis가 없다(UNMAPPED로 빠졌다) — 학생이 causal_analysis
        에 아무리 강한 근거를 가져도, hci_ux 점수는 그 Trait를 넣기 전과 후가 완전히
        같아야 한다(0점으로 끼워져 점수를 깎으면 안 된다)."""

        self.assertNotIn("causal_analysis", self.majors["hci_ux"].cognitive_vector)

        base_summaries = {
            trait_id: TraitEvidenceSummary(
                trait_id=trait_id, support_count=2, opportunity_count=2, context_count=1, distinct_frame_count=1
            )
            for trait_id in ("visual_expression", "audience_response_prediction", "tool_utilization")
        }
        for trait_id in self.trait_defs:
            base_summaries.setdefault(trait_id, TraitEvidenceSummary(trait_id=trait_id, support_count=0, opportunity_count=0))

        with_strong_unmapped_trait = dict(base_summaries)
        with_strong_unmapped_trait["causal_analysis"] = TraitEvidenceSummary(
            trait_id="causal_analysis", support_count=3, opportunity_count=3, context_count=2, distinct_frame_count=2
        )

        states_without = compute_student_trait_states(base_summaries, self.trait_defs, set())
        states_with = compute_student_trait_states(with_strong_unmapped_trait, self.trait_defs, set())

        result_without = compute_major_match(states_without, self.majors["hci_ux"])
        result_with = compute_major_match(states_with, self.majors["hci_ux"])

        self.assertEqual(result_without.score, result_with.score)
        self.assertEqual(result_without.usable_trait_count, result_with.usable_trait_count)


if __name__ == "__main__":
    unittest.main()
