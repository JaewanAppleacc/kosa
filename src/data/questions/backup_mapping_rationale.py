"""Backup Question Mapping Rationale Draft 정본 — 2026-08-23 Trait Ontology
v2(2.5.3단계) §9.

6개 Backup × 5개 Option = 30개 전부에 대해 "왜 이 문구가 이 Trait 후보로 연결되는지"
한 문장 초안을 남긴다. `_validate()`가 import 시점에 실제
Backup Question(`VERTICAL_SLICE_BACKUP_QUESTIONS`)과 Key(question_id, role_id) 집합이
정확히 같은지, trait_id가 실제 Option의 `primary_trait_delta`와 일치하는지, 빈
Rationale이 없는지 Fail-Fast로 검증한다."""

from __future__ import annotations

from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.schemas.backup_option_rationale import BackupOptionRationale, BackupOptionRationaleError

BACKUP_MAPPING_RATIONALE: list[BackupOptionRationale] = [
    # --- game_backup_01 ---
    BackupOptionRationale(
        question_id="game_backup_01", role_id="rule_reasoning", trait_id="causal_analysis",
        mapping_rationale_draft="규칙 설계 이유를 능동적으로 분석하는 행동이 직접 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_01", role_id="trial_and_error", trait_id="immediate_execution",
        mapping_rationale_draft="생각보다 먼저 직접 부딪혀보는 행동이 드러나 immediate_execution 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_01", role_id="guide_comparison", trait_id="information_comparison",
        mapping_rationale_draft="여러 자료를 찾아 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_01", role_id="role_split", trait_id="collaboration_preference",
        mapping_rationale_draft="다른 사람과 역할을 나눠 함께 해결하는 행동이 드러나 collaboration_preference 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_01", role_id="pattern_watch", trait_id="pattern_finding",
        mapping_rationale_draft="반복되는 규칙을 스스로 찾아내는 행동이 드러나 pattern_finding 후보로 연결된다",
    ),
    # --- game_backup_02 ---
    BackupOptionRationale(
        question_id="game_backup_02", role_id="screen_review", trait_id="visual_expression",
        mapping_rationale_draft="상황을 직접 그림·도표로 표현하는 산출 행동이 드러나 visual_expression 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_02", role_id="reaction_check", trait_id="audience_response_prediction",
        mapping_rationale_draft="다른 사람의 반응을 살피는 행동이 드러나 audience_response_prediction 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_02", role_id="strategy_switch", trait_id="change_adaptation",
        mapping_rationale_draft="상황에 맞춰 접근 방식을 바꾸는 행동이 드러나 change_adaptation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_02", role_id="plan_ahead", trait_id="planning",
        mapping_rationale_draft="미리 계획을 세우는 행동이 직접 드러나 planning 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_02", role_id="new_tool_first", trait_id="tool_utilization",
        mapping_rationale_draft="새로운 도구를 익혀 활용하는 행동이 드러나 tool_utilization 후보로 연결된다",
    ),
    # --- media_backup_01 ---
    BackupOptionRationale(
        question_id="media_backup_01", role_id="reason_for_split", trait_id="causal_analysis",
        mapping_rationale_draft="반응이 갈린 이유를 능동적으로 따지는 행동이 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_01", role_id="opinion_bridge", trait_id="opinion_mediation",
        mapping_rationale_draft="서로 다른 의견 사이에서 절충점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_01", role_id="comment_reading", trait_id="emotional_interpretation",
        mapping_rationale_draft="댓글에 담긴 감정을 해석해보는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_01", role_id="cross_content_compare", trait_id="information_comparison",
        mapping_rationale_draft="여러 콘텐츠를 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_01", role_id="predict_next_reaction", trait_id="audience_response_prediction",
        mapping_rationale_draft="앞으로의 반응을 미리 예측하는 행동이 드러나 audience_response_prediction 후보로 연결된다",
    ),
    # --- media_backup_02 ---
    BackupOptionRationale(
        question_id="media_backup_02", role_id="sequence_plan", trait_id="planning",
        mapping_rationale_draft="탐색 순서를 미리 계획하는 행동이 직접 드러나 planning 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_02", role_id="visual_layout", trait_id="visual_expression",
        mapping_rationale_draft="직접 그림·이미지로 표현하는 산출 행동이 드러나 visual_expression 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_02", role_id="new_editing_tool", trait_id="tool_utilization",
        mapping_rationale_draft="새로운 도구를 활용해 자료를 모으는 행동이 드러나 tool_utilization 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_02", role_id="reference_pattern", trait_id="pattern_finding",
        mapping_rationale_draft="반복되는 패턴을 스스로 찾아내는 행동이 드러나 pattern_finding 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_02", role_id="team_split", trait_id="collaboration_preference",
        mapping_rationale_draft="다른 사람과 함께 알아보는 행동이 드러나 collaboration_preference 후보로 연결된다",
    ),
    # --- school_life_backup_01 ---
    BackupOptionRationale(
        question_id="school_life_backup_01", role_id="disagreement_reason", trait_id="causal_analysis",
        mapping_rationale_draft="의견 차이의 원인을 능동적으로 짚는 행동이 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_01", role_id="find_middle_ground", trait_id="opinion_mediation",
        mapping_rationale_draft="서로 다른 의견 사이의 절충점을 찾는 행동이 드러나 opinion_mediation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_01", role_id="other_group_compare", trait_id="information_comparison",
        mapping_rationale_draft="다른 사례와 비교하는 행동이 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_01", role_id="just_start", trait_id="immediate_execution",
        mapping_rationale_draft="생각보다 먼저 바로 실행하는 행동이 드러나 immediate_execution 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_01", role_id="feelings_care", trait_id="emotional_interpretation",
        mapping_rationale_draft="다른 사람의 감정을 살피는 행동이 드러나 emotional_interpretation 후보로 연결된다",
    ),
    # --- school_life_backup_02 ---
    BackupOptionRationale(
        question_id="school_life_backup_02", role_id="schedule_plan", trait_id="planning",
        mapping_rationale_draft="일정과 순서를 미리 계획하는 행동이 직접 드러나 planning 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_02", role_id="prepare_tools", trait_id="tool_utilization",
        mapping_rationale_draft="필요한 도구를 준비하는 행동이 드러나 tool_utilization 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_02", role_id="recall_pattern", trait_id="pattern_finding",
        mapping_rationale_draft="과거 사례의 패턴을 떠올리는 행동이 드러나 pattern_finding 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_02", role_id="adjust_on_change", trait_id="change_adaptation",
        mapping_rationale_draft="상황 변화에 맞춰 방식을 바꾸는 행동이 드러나 change_adaptation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_02", role_id="anticipate_reaction", trait_id="audience_response_prediction",
        mapping_rationale_draft="발표·공유 후 반응을 미리 예상하는 행동이 드러나 audience_response_prediction 후보로 연결된다",
    ),
]

BACKUP_MAPPING_RATIONALE_BY_KEY: dict[tuple[str, str], BackupOptionRationale] = {
    (r.question_id, r.role_id): r for r in BACKUP_MAPPING_RATIONALE
}


def _validate() -> None:
    keys = [(r.question_id, r.role_id) for r in BACKUP_MAPPING_RATIONALE]
    if len(keys) != len(set(keys)):
        raise BackupOptionRationaleError(f"(question_id, role_id) 중복이 있다: {keys}")

    expected: dict[tuple[str, str], str] = {}
    for backups in VERTICAL_SLICE_BACKUP_QUESTIONS.values():
        for question in backups:
            for option in question.options:
                trait_id = next(iter(option.primary_trait_delta))
                expected[(question.question_id, option.role_id)] = trait_id

    if set(keys) != set(expected.keys()):
        missing = set(expected.keys()) - set(keys)
        extra = set(keys) - set(expected.keys())
        raise BackupOptionRationaleError(
            f"Backup Mapping Rationale 집합이 실제 Backup Option 목록과 다르다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    for rationale in BACKUP_MAPPING_RATIONALE:
        key = (rationale.question_id, rationale.role_id)
        if rationale.trait_id != expected[key]:
            raise BackupOptionRationaleError(
                f"{key}: trait_id가 실제 Option Mapping과 다르다"
                f"(정본: {expected[key]!r}, 여기: {rationale.trait_id!r})"
            )
        if not rationale.mapping_rationale_draft.strip():
            raise BackupOptionRationaleError(f"{key}: Mapping Rationale Draft가 비어 있다")


_validate()
