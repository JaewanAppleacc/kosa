"""Backup Question 적합성 판정 — 2026-08-23 Trait Ontology v2(2.5.3단계) §2/§3/§11.

`_use_backup()`(실제 Runtime의 Backup 선택 경로)와 검수 UI의 Anchor Preview가 정확히
같은 판정 로직을 쓰도록 이 함수 하나로 뽑아냈다 — "실제 Runtime의 Backup 적합성 검사
함수를 재사용하고 UI 전용 가짜 판정을 만들지 않는다"(§11)는 요구를 이 구조로
충족한다. Applicability(허용/제외 Anchor 목록)를 먼저 확인하고, 그다음
Quality Gate(문자열 금지 검사 등)를 확인한다 — 둘 중 하나라도 막히면 부적합하다."""

from __future__ import annotations

from src.engines.question_quality_gate import QuestionQualityGateResult, run_quality_gate
from src.schemas.backup_applicability import BackupQuestionApplicability
from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.question import FinalizedQuestion


def check_backup_candidate(
    backup: FinalizedQuestion,
    *,
    anchor: ContextAnchorPresentation | None,
    applicability: BackupQuestionApplicability | None,
    previous_question_texts: list[str] | None = None,
) -> QuestionQualityGateResult:
    anchor_id = anchor.anchor_id if anchor is not None else None
    if applicability is not None and not applicability.allows(anchor_id):
        return QuestionQualityGateResult(
            passed=False, failures=[f"Backup Applicability가 이 Anchor({anchor_id})를 허용하지 않는다"],
        )

    forbidden_anchor_phrases = tuple(anchor.forbidden_assumptions) if anchor is not None else ()
    return run_quality_gate(
        backup, previous_question_texts, forbidden_anchor_assumption_phrases=forbidden_anchor_phrases,
    )
