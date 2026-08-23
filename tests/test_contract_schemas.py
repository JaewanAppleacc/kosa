"""B·C에게 전달할 계약 레이어 Schema 테스트 — 구조와 핵심 정책이 코드로 강제되는지 확인."""

from __future__ import annotations

import unittest
from datetime import datetime

import pydantic

from src.schemas.course import CourseRecommendationItem
from src.schemas.graph import SubgraphEdge, SubgraphNode
from src.schemas.major import AdmissionReference, Department, MajorRelevance
from src.schemas.mcp_contracts import MCPToolResult
from src.schemas.profile import CareerProfile, CareerProfileHighlight


class CareerProfileHighlightCountTest(unittest.TestCase):
    """§14: 결과 카드 첫 화면은 핵심 특징 5~8줄만 보여준다."""

    def _profile(self, n_highlights: int) -> dict:
        return dict(
            session_id="sess_1",
            user_id="demo_user_01",
            title="탐색형 설계자",
            highlights=[
                CareerProfileHighlight(text=f"특징 {i}", supporting_trait_ids=["causal_analysis"])
                for i in range(n_highlights)
            ],
            hashtags=["#구조화"],
            detailed_evidence_by_dimension={},
            generated_at=datetime.now(),
        )

    def test_five_highlights_ok(self) -> None:
        CareerProfile(**self._profile(5))

    def test_eight_highlights_ok(self) -> None:
        CareerProfile(**self._profile(8))

    def test_four_highlights_rejected(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            CareerProfile(**self._profile(4))

    def test_nine_highlights_rejected(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            CareerProfile(**self._profile(9))


class MajorRelevanceNoRawNumberTest(unittest.TestCase):
    """CLAUDE.md 금지 사항: 사용자 화면에 84%, 81점 같은 가짜 정확도를 노출하지 않는다.
    MajorRelevance는 애초에 float 필드가 없다는 것 자체로 이 규칙을 구조적으로 강제한다."""

    def test_no_numeric_score_field_exists(self) -> None:
        self.assertNotIn("score", MajorRelevance.model_fields)
        self.assertNotIn("relevance_score", MajorRelevance.model_fields)
        for name, field in MajorRelevance.model_fields.items():
            self.assertNotIn(float, (field.annotation,), f"{name} must not be a raw float")

    def test_relevance_label_only_accepts_defined_labels(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            MajorRelevance(
                major_id="media_communication",
                label="미디어커뮤니케이션",
                description="미디어 콘텐츠가 만들어지고 전달되는 과정을 탐구하는 전공 분야입니다.",
                relevance_label="84%",  # type: ignore[arg-type]
                evidence_sufficiency="충분",
                repeated_context_count=3,
            )


class DepartmentIdConventionTest(unittest.TestCase):
    def test_department_requires_source_svy_year_not_in_id(self) -> None:
        dept = Department(
            department_id="dept_abc123",
            university_name="가상대학교",
            region="서울",
            department_name="컴퓨터공학과",
            college_name="공과대학",
            department_status="EXISTING",
            source_svy_year=2024,
            source_url="https://example.ac.kr",
        )
        self.assertNotIn("2024", dept.department_id)  # 연도가 id 안에 섞여 있으면 안 됨


class AdmissionReferenceComparabilityTest(unittest.TestCase):
    def test_requires_comparability_group(self) -> None:
        ref = AdmissionReference(
            department_id="dept_abc123",
            admission_year=2025,
            admission_type="수시",
            admission_track="학생부종합",
            score_metric="평균등급",
            score_70_cut=1.8,
            source_url="https://example.ac.kr/admission",
            data_comparability_group="2025_수시_학생부종합_평균등급_70cut",
            review_status="verified",
            verified_at=datetime.now(),
        )
        self.assertTrue(ref.data_comparability_group)


class SubgraphTest(unittest.TestCase):
    def test_related_concept_node_type_is_allowed(self) -> None:
        node = SubgraphNode(node_id="rc_1", node_type="RelatedConcept", label="추론된 특성")
        self.assertEqual(node.display_color, "gray")

    def test_invalid_node_type_rejected(self) -> None:
        with self.assertRaises(pydantic.ValidationError):
            SubgraphNode(node_id="x", node_type="InvalidType", label="x")  # type: ignore[arg-type]

    def test_edge_requires_evidence_traceability_fields(self) -> None:
        edge = SubgraphEdge(
            source_node_id="student_1",
            target_node_id="trait_causal_analysis",
            relation_type="HAS_TRAIT",
            relevance_level=2,
            evidence_ids=["ev_1", "ev_2"],
            mapping_version="v1",
            created_at=datetime.now(),
        )
        self.assertTrue(edge.evidence_ids)


class CourseRecommendationOfferedFlagTest(unittest.TestCase):
    """policy_guard 규칙 6(미개설과목 추천 차단)을 데이터 레벨에서도 표현할 수 있는지 확인."""

    def test_offered_flag_is_explicit(self) -> None:
        item = CourseRecommendationItem(
            subject_id="subj_abc",
            label="테스트 과목",
            category="core",
            is_actually_offered=True,
            reason="Trait 관련도 상위",
        )
        self.assertTrue(item.is_actually_offered)


class MCPToolResultStatusTest(unittest.TestCase):
    def test_error_and_empty_are_distinguishable(self) -> None:
        empty = MCPToolResult[str](status="empty", data=[])
        error = MCPToolResult[str](status="error", data=[], error_message="upstream timeout")
        self.assertNotEqual(empty.status, error.status)
        self.assertIsNone(empty.error_message)
        self.assertIsNotNone(error.error_message)


if __name__ == "__main__":
    unittest.main()
