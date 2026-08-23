"""사용자 검수 결과 보존 회귀 — 2026-08-23 Trait Ontology v2(2.5.4단계) §1/§10.

2.5.4단계 시작 시점에 사용자가 검수 페이지에서 직접 남긴 판정(별도 커밋 ea7de9c로
보존)이 이후 코드 작업 과정에서 손상되지 않았는지 확인한다.

- Context Routing 질문 3개: reviewer_1_status=APPROVE
- Seed Anchor 질문 15개: reviewer_1_status=APPROVE
- 기존 Backup 질문 6개: reviewer_1_status=REVISE
- game_backup_02/screen_review 선택지의 "이런 경우는 너무 드문 경우같아" 메모(TBD)
- Direct Probe 질문·선택지: TBD 유지
- 기존 Backup 선택지: TBD 유지(질문 단위 REVISE 메모 외에는)
"""

from __future__ import annotations

import unittest

from src.services.backup_question_review_store import (
    load_backup_option_review_entries,
    load_backup_question_review_entries,
)
from src.services.context_routing_review_store import load_routing_question_review_entries
from src.services.seed_anchor_review_store import load_seed_anchor_question_review_entries
from src.services.v2_direct_probe_review_store import load_option_review_entries, load_question_review_entries


class ContextRoutingApprovePreservedTest(unittest.TestCase):
    def test_all_3_routing_questions_are_reviewer_1_approve(self) -> None:
        entries = load_routing_question_review_entries()
        self.assertEqual(len(entries), 3)
        for entry in entries:
            self.assertEqual(entry.reviewer_1_status, "APPROVE")
            self.assertEqual(entry.reviewer_1_comment, "사용자 검수 결과 Context Routing 질문이 적절함.")


class SeedAnchorApprovePreservedTest(unittest.TestCase):
    def test_all_15_seed_anchor_questions_are_reviewer_1_approve(self) -> None:
        entries = load_seed_anchor_question_review_entries()
        self.assertEqual(len(entries), 15)
        for entry in entries:
            self.assertEqual(entry.reviewer_1_status, "APPROVE")
            self.assertEqual(entry.reviewer_1_comment, "사용자 검수 결과 Seed Anchor 질문이 적절함.")


class OldBackupRevisePreservedTest(unittest.TestCase):
    def test_all_6_old_backup_questions_are_reviewer_1_revise(self) -> None:
        entries = load_backup_question_review_entries()
        self.assertEqual(len(entries), 6)
        for entry in entries:
            self.assertEqual(entry.reviewer_1_status, "REVISE")
            self.assertEqual(
                entry.reviewer_1_comment, "사용자 검수 결과 Backup 질문이 전반적으로 부자연스러워 재작성이 필요함.",
            )

    def test_game_backup_02_screen_review_rare_case_memo_preserved(self) -> None:
        entries = load_backup_option_review_entries()
        entry = next(e for e in entries if e.blueprint_id == "game_backup_02" and e.role_id == "screen_review")
        self.assertEqual(entry.reviewer_1_comment, "이런 경우는 너무 드문 경우같아")
        self.assertEqual(entry.reviewer_1_status, "TBD")
        self.assertEqual(entry.reviewer_2_status, "TBD")

    def test_no_other_old_backup_option_gained_a_comment(self) -> None:
        entries = load_backup_option_review_entries()
        self.assertEqual(len(entries), 30)
        commented = [
            (e.blueprint_id, e.role_id) for e in entries if e.reviewer_1_comment or e.reviewer_2_comment
        ]
        self.assertEqual(commented, [("game_backup_02", "screen_review")])


class DirectProbeStillTbdTest(unittest.TestCase):
    def test_direct_probe_questions_and_options_still_tbd_except_known_6_memos(self) -> None:
        question_entries = load_question_review_entries()
        option_entries = load_option_review_entries()
        self.assertEqual(len(question_entries), 14)
        self.assertEqual(len(option_entries), 70)
        for entry in [*question_entries, *option_entries]:
            self.assertEqual(entry.reviewer_1_status, "TBD")
            self.assertEqual(entry.reviewer_2_status, "TBD")


if __name__ == "__main__":
    unittest.main()
