"""사용자 검토 메모 6개 필드 값 보존 — 2026-08-23 Trait Ontology v2(2.5.2단계) §13/§15.

2.5.2단계는 `data/reviews/v2_direct_probe_question_review_status.json`/
`v2_direct_probe_option_review_status.json`을 전혀 쓰지 않는다(Seed Anchor Variant는
별도 새 파일을 쓴다) — 이 테스트는 그 사실을 "파일 SHA가 같다"가 아니라 "라운드
시작 시점에 기록해 둔 6개 메모의 실제 필드 값과 정확히 같다"로 구조적으로 재확인한다
(작업 지시문 §13: "파일 전체 SHA는 JSON 필드 순서나 새로운 기록 때문에 바뀔 수
있으므로, 단순 SHA만 주장하지 말고 기존 6개 항목의 필드 값을 구조적으로
비교하세요")."""

from __future__ import annotations

import unittest

from src.services.v2_direct_probe_review_store import (
    OPTION_REVIEW_PATH,
    QUESTION_REVIEW_PATH,
    load_option_review_entries,
    load_question_review_entries,
)

# 2.5.2단계 라운드 시작 시점(커밋 4ae513e)에 기록해 둔 6개 사용자 메모의 정확한
# 필드 값 — /tmp/anchor_2_5_2_snapshot/user_memos_before.txt에서 그대로 옮겼다.
_EXPECTED_QUESTION_MEMOS = {
    "systems_thinking_game_v1": {
        "reviewer_1_comment": (
            "게임이나 드라마 영화같이 장르가 나뉘는 카테고리들은 선호하는 장르를 먼저 물어보고 "
            "장르에 따라 질문을 달리해야될 것같아 게임 중에서도 협동형 게임이 있고, 혼자 플레이하는 "
            "게임이 있고 장르가 다양해서 한 질문이 모든 장르를 포괄하긴 어려운것같아"
        ),
    },
    "detail_orientation_media_v1": {
        "reviewer_1_comment": "내가 말한 미디어는 이런 편집이나 제출의 느낌보다는 영화,드라마,유튜브,뮤지컬,공연 등의 문화생활을 말한거였어",
    },
}
_EXPECTED_OPTION_MEMOS = {
    ("systems_thinking_game_v1", "st_compare_items"): {
        "reviewer_1_comment": "기존 아이템들과 비교해보는건 개인의 특성에 따라 갈리는 영역이 아닌 당연한 영역이야 ",
    },
    ("systems_thinking_game_v1", "st_ask_team"): {
        "reviewer_1_comment": "팀원들끼리 같이 하는 게임이 아닌 혼자 하는 게임일 수 도 있어",
    },
    ("systems_thinking_school_life_v1", "st_replan"): {
        "reviewer_1_comment": (
            "남은 일정과 순서를 처음부터 다시 짜는건 무조건적으로 1번 선택지인 이 변화가 어떤 영향을 "
            "주는지 짚어본 후에야 나올 수 있는 생각인것같아"
        ),
    },
    ("systems_thinking_school_life_v1", "st_adapt_now"): {
        "reviewer_1_comment": "상황에 맞게 바로 대응한다는 모든 답변을 포괄하는 답변이라 애매한것같아",
    },
}


class UserReviewMemoStructuralPreservationTest(unittest.TestCase):
    def test_2_question_level_memos_preserved_field_by_field(self) -> None:
        entries = {e.blueprint_id: e for e in load_question_review_entries(QUESTION_REVIEW_PATH)}
        self.assertEqual(len(_EXPECTED_QUESTION_MEMOS), 2)
        for blueprint_id, expected in _EXPECTED_QUESTION_MEMOS.items():
            entry = entries[blueprint_id]
            self.assertEqual(entry.reviewer_1_comment, expected["reviewer_1_comment"])
            self.assertEqual(entry.reviewer_1_status, "TBD")
            self.assertEqual(entry.reviewer_2_status, "TBD")
            self.assertEqual(entry.reviewer_2_comment, "")
            self.assertEqual(entry.resolution_note, "")

    def test_4_option_level_memos_preserved_field_by_field(self) -> None:
        entries = {(e.blueprint_id, e.role_id): e for e in load_option_review_entries(OPTION_REVIEW_PATH)}
        self.assertEqual(len(_EXPECTED_OPTION_MEMOS), 4)
        for key, expected in _EXPECTED_OPTION_MEMOS.items():
            entry = entries[key]
            self.assertEqual(entry.reviewer_1_comment, expected["reviewer_1_comment"])
            self.assertEqual(entry.reviewer_1_status, "TBD")
            self.assertEqual(entry.reviewer_2_status, "TBD")
            self.assertEqual(entry.reviewer_2_comment, "")
            self.assertEqual(entry.resolution_note, "")

    def test_no_other_entries_gained_a_non_empty_comment(self) -> None:
        question_entries = load_question_review_entries(QUESTION_REVIEW_PATH)
        option_entries = load_option_review_entries(OPTION_REVIEW_PATH)
        commented_questions = {e.blueprint_id for e in question_entries if e.reviewer_1_comment or e.reviewer_2_comment}
        commented_options = {
            (e.blueprint_id, e.role_id) for e in option_entries if e.reviewer_1_comment or e.reviewer_2_comment
        }
        self.assertEqual(commented_questions, set(_EXPECTED_QUESTION_MEMOS.keys()))
        self.assertEqual(commented_options, set(_EXPECTED_OPTION_MEMOS.keys()))

    def test_still_all_84_entries_are_draft_status(self) -> None:
        question_entries = load_question_review_entries(QUESTION_REVIEW_PATH)
        option_entries = load_option_review_entries(OPTION_REVIEW_PATH)
        self.assertEqual(len(question_entries), 14)
        self.assertEqual(len(option_entries), 70)
        for e in [*question_entries, *option_entries]:
            self.assertEqual(e.final_status, "DRAFT")


if __name__ == "__main__":
    unittest.main()
