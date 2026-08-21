"""Backup Question — 설계안 §11 Fallback: "일반 장애에 대응할 최소 Backup Question은
Context별 2~3개 준비한다. Backup은 동일 세션에서 재사용하지 않는다." LLM 생성이 재생성까지
실패했을 때만 쓰는 완전히 고정된 질문이라, Seed와 마찬가지로 손으로 직접 작성했다.
FinalizedQuestion 형태로 바로 저장한다 — LLM 경유가 없으므로 Blueprint 결합 단계가 필요 없다.
"""

from __future__ import annotations

from src.schemas.question import FinalizedOption, FinalizedQuestion

GAME_BACKUP_01 = FinalizedQuestion(
    question_id="game_backup_01",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="새로운 게임 규칙을 팀원들과 처음 접했을 때, 가장 먼저 하고 싶은 행동은?",
    options=[
        FinalizedOption(
            option_id="game_backup_01_o1",
            role_id="rule_reasoning",
            text="규칙이 왜 이렇게 설계됐는지 먼저 분석해본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="game_backup_01_o2",
            role_id="trial_and_error",
            text="일단 몸으로 부딪히며 시행착오로 익힌다",
            primary_trait_delta={"immediate_execution": 1},
        ),
        FinalizedOption(
            option_id="game_backup_01_o3",
            role_id="guide_comparison",
            text="비슷한 게임의 공략을 찾아보고 비교한다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="game_backup_01_o4",
            role_id="role_split",
            text="팀원들과 역할을 나눠서 같이 파악한다",
            primary_trait_delta={"collaboration_preference": 1},
        ),
        FinalizedOption(
            option_id="game_backup_01_o5",
            role_id="pattern_watch",
            text="규칙이 바뀌는 패턴이 있는지 눈여겨본다",
            primary_trait_delta={"pattern_finding": 1},
        ),
    ],
)

GAME_BACKUP_02 = FinalizedQuestion(
    question_id="game_backup_02",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="게임 결과가 예상과 다르게 나왔을 때 무엇을 가장 먼저 확인하나요?",
    options=[
        FinalizedOption(
            option_id="game_backup_02_o1",
            role_id="screen_review",
            text="화면 구성을 다시 살펴보며 놓친 게 있는지 본다",
            primary_trait_delta={"visual_expression": 1},
        ),
        FinalizedOption(
            option_id="game_backup_02_o2",
            role_id="reaction_check",
            text="다른 플레이어들이 어떻게 반응했는지 살핀다",
            primary_trait_delta={"audience_response_prediction": 1},
        ),
        FinalizedOption(
            option_id="game_backup_02_o3",
            role_id="strategy_switch",
            text="전략을 완전히 바꿔서 다시 시도한다",
            primary_trait_delta={"change_adaptation": 1},
        ),
        FinalizedOption(
            option_id="game_backup_02_o4",
            role_id="plan_ahead",
            text="다음엔 미리 계획을 세워두고 시작한다",
            primary_trait_delta={"planning": 1},
        ),
        FinalizedOption(
            option_id="game_backup_02_o5",
            role_id="new_tool_first",
            text="새로운 도구·아이템부터 먼저 써본다",
            primary_trait_delta={"tool_utilization": 1},
        ),
    ],
)

MEDIA_BACKUP_01 = FinalizedQuestion(
    question_id="media_backup_01",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="영상이나 콘텐츠를 볼 때 사람들 반응이 갈리면 가장 먼저 무엇을 하나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_01_o1",
            role_id="reason_for_split",
            text="왜 반응이 갈렸는지 원인을 따져본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="media_backup_01_o2",
            role_id="opinion_bridge",
            text="서로 다른 의견을 절충할 지점을 찾는다",
            primary_trait_delta={"opinion_mediation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_01_o3",
            role_id="comment_reading",
            text="댓글이나 반응을 보며 감정을 읽어본다",
            primary_trait_delta={"emotional_interpretation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_01_o4",
            role_id="cross_content_compare",
            text="비슷한 콘텐츠들과 비교해서 원인을 찾는다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="media_backup_01_o5",
            role_id="predict_next_reaction",
            text="다음엔 어떤 장면이 더 반응이 좋을지 예측해본다",
            primary_trait_delta={"audience_response_prediction": 1},
        ),
    ],
)

MEDIA_BACKUP_02 = FinalizedQuestion(
    question_id="media_backup_02",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="콘텐츠를 기획할 때 어떤 부분에 가장 신경 쓰나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_02_o1",
            role_id="sequence_plan",
            text="전체 진행 순서를 미리 계획한다",
            primary_trait_delta={"planning": 1},
        ),
        FinalizedOption(
            option_id="media_backup_02_o2",
            role_id="visual_layout",
            text="화면 구성과 시각적 배치를 신경 쓴다",
            primary_trait_delta={"visual_expression": 1},
        ),
        FinalizedOption(
            option_id="media_backup_02_o3",
            role_id="new_editing_tool",
            text="편집 도구의 새로운 기능을 먼저 써본다",
            primary_trait_delta={"tool_utilization": 1},
        ),
        FinalizedOption(
            option_id="media_backup_02_o4",
            role_id="reference_pattern",
            text="반복되는 좋은 패턴을 참고한다",
            primary_trait_delta={"pattern_finding": 1},
        ),
        FinalizedOption(
            option_id="media_backup_02_o5",
            role_id="team_split",
            text="팀원과 역할을 나눠 함께 만든다",
            primary_trait_delta={"collaboration_preference": 1},
        ),
    ],
)

SCHOOL_LIFE_BACKUP_01 = FinalizedQuestion(
    question_id="school_life_backup_01",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="조별 과제에서 의견이 갈릴 때 가장 먼저 하는 행동은?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_01_o1",
            role_id="disagreement_reason",
            text="의견 차이의 원인을 짚어본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_01_o2",
            role_id="find_middle_ground",
            text="서로 다른 의견을 절충할 방법을 찾는다",
            primary_trait_delta={"opinion_mediation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_01_o3",
            role_id="other_group_compare",
            text="다른 조는 어떻게 하는지 비교해본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_01_o4",
            role_id="just_start",
            text="일단 하나를 정해서 바로 진행해본다",
            primary_trait_delta={"immediate_execution": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_01_o5",
            role_id="feelings_care",
            text="친구들의 감정이 상하지 않게 신경 쓴다",
            primary_trait_delta={"emotional_interpretation": 1},
        ),
    ],
)

SCHOOL_LIFE_BACKUP_02 = FinalizedQuestion(
    question_id="school_life_backup_02",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="새로운 활동이나 과제가 주어지면 가장 먼저 무엇을 하나요?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_02_o1",
            role_id="schedule_plan",
            text="전체 일정과 순서를 미리 계획한다",
            primary_trait_delta={"planning": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_02_o2",
            role_id="prepare_tools",
            text="필요한 도구나 자료부터 준비한다",
            primary_trait_delta={"tool_utilization": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_02_o3",
            role_id="recall_pattern",
            text="예전에 비슷했던 경우의 패턴을 떠올린다",
            primary_trait_delta={"pattern_finding": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_02_o4",
            role_id="adjust_on_change",
            text="상황이 바뀌면 바로 방식을 조정한다",
            primary_trait_delta={"change_adaptation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_02_o5",
            role_id="anticipate_reaction",
            text="다른 사람들 반응을 미리 예상해본다",
            primary_trait_delta={"audience_response_prediction": 1},
        ),
    ],
)

VERTICAL_SLICE_BACKUP_QUESTIONS: dict[str, list[FinalizedQuestion]] = {
    "game": [GAME_BACKUP_01, GAME_BACKUP_02],
    "media": [MEDIA_BACKUP_01, MEDIA_BACKUP_02],
    "school_life": [SCHOOL_LIFE_BACKUP_01, SCHOOL_LIFE_BACKUP_02],
}
