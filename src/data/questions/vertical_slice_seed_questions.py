"""Vertical Slice Seed Question 3개 — 1차 초안 (DRAFT, 2인 교차검토 전).

설계안 §7-1: Seed Question은 "해당 Context 안에서 학생이 가장 흥미를 느끼는 지점을 넓게
탐색"하는 역할이라, 위치별 테마가 고정된 꼬리질문(§7-2)과 달리 5개 선택지를 그 Context
안에서 관찰 가능한 여러 Trait에 최대한 넓게 흩어 배정했다.

3개 Seed(15개 선택지) 전체에서 12개 Trait가 전부 최소 1번씩은 나오도록 설계했다
(causal_analysis·collaboration_preference·emotional_interpretation은 두 Context에서
겹쳐 나온다 — 서로 다른 Context에서 같은 성향이 반복 관찰되는지 보는 §13 판정 로직상
의도적으로 남겨둔 중복이다. pattern_finding처럼 겹치지 않는 Trait는 하나만 배정했다).

각 옵션의 `next_probe`/`preferred_frames`는 이 옵션을 고른 학생에게 이어질 첫 꼬리질문
(§7-2 위치 1, DEEPEN 테마)이 참고할 힌트다. `preferred_frames`는
`src/data/question_frames/frame_role_map.py`에 정의된 실제 frame_id만 사용했다.
"""

from __future__ import annotations

from src.ids import generate_option_id, generate_question_id
from src.schemas.question import SeedOption, SeedQuestion

_GAME_QID = generate_question_id("game", "seed", 1)
_MEDIA_QID = generate_question_id("media", "seed", 1)
_SCHOOL_QID = generate_question_id("school_life", "seed", 1)


def _opt(question_id: str, index: int, **kwargs) -> SeedOption:
    return SeedOption(option_id=generate_option_id(question_id, index), **kwargs)


GAME_SEED_01 = SeedQuestion(
    question_id=_GAME_QID,
    context="game",
    question_text="게임을 할 때 가장 흥미를 느끼는 부분은 무엇인가요?",
    options=[
        _opt(
            _GAME_QID, 1,
            text="왜 이 전략이 통하는지 원리를 파악하는 것",
            role_id="strategy_analysis",
            primary_trait_delta={"causal_analysis": 1},
            next_probe="원인 분석을 더 깊이 파고드는 경향인지 확인",
            preferred_frames=["problem_check", "longest_focus"],
        ),
        _opt(
            _GAME_QID, 2,
            text="일단 해보면서 방법을 찾아가는 것",
            role_id="quick_execution",
            primary_trait_delta={"immediate_execution": 1},
            next_probe="즉시 실행 성향이 새로운 상황에서도 이어지는지 확인",
            preferred_frames=["new_tool", "unexpected_result"],
        ),
        _opt(
            _GAME_QID, 3,
            text="같이 하는 사람들과 역할을 맞춰가는 것",
            role_id="team_coordination",
            primary_trait_delta={"collaboration_preference": 1},
            next_probe="협업 상황에서 역할 분담 방식을 더 확인",
            preferred_frames=["team_role", "conflicting_opinions"],
        ),
        _opt(
            _GAME_QID, 4,
            text="여러 상황이나 상대의 행동에서 반복되는 패턴을 찾아내는 것",
            role_id="pattern_recognition",
            primary_trait_delta={"pattern_finding": 1},
            next_probe="패턴 탐색이 다른 상황에서도 이어지는지 확인",
            preferred_frames=["longest_focus", "problem_check"],
        ),
        _opt(
            _GAME_QID, 5,
            text="아이템이나 장비를 직접 다루고 활용하는 것",
            role_id="tool_mastery",
            primary_trait_delta={"tool_utilization": 1},
            next_probe="도구·장비 활용이 다른 상황에서도 나타나는지 확인",
            preferred_frames=["new_tool", "longest_focus"],
        ),
    ],
)

MEDIA_SEED_01 = SeedQuestion(
    question_id=_MEDIA_QID,
    context="media",
    question_text="SNS·영화·드라마 같은 콘텐츠를 볼 때 가장 흥미를 느끼는 부분은 무엇인가요?",
    options=[
        _opt(
            _MEDIA_QID, 1,
            text="이야기나 장면이 왜 그렇게 구성됐는지 생각하는 것",
            role_id="structure_analysis",
            primary_trait_delta={"causal_analysis": 1},
            next_probe="구조 분석이 다른 Context에서도 반복되는지 확인",
            preferred_frames=["problem_check", "longest_focus"],
        ),
        _opt(
            _MEDIA_QID, 2,
            text="직접 영상이나 이미지를 만들어보는 것",
            role_id="creative_making",
            primary_trait_delta={"visual_expression": 1},
            next_probe="직접 제작 성향이 어떤 도구·방식으로 이어지는지 확인",
            preferred_frames=["new_tool", "first_action"],
        ),
        _opt(
            _MEDIA_QID, 3,
            text="사람들이 이 콘텐츠에 어떻게 반응할지 예상해보는 것",
            role_id="audience_reaction",
            primary_trait_delta={"audience_response_prediction": 1},
            next_probe="반응 예측이 결과물을 만들 때 기준으로 이어지는지 확인",
            preferred_frames=["unexpected_result", "others_reaction"],
        ),
        _opt(
            _MEDIA_QID, 4,
            text="등장인물이나 만든 사람의 감정을 이해해보는 것",
            role_id="character_empathy",
            primary_trait_delta={"emotional_interpretation": 1},
            next_probe="감정 해석이 다른 사람 관점 이해로 이어지는지 확인",
            preferred_frames=["others_reaction", "conflicting_opinions"],
        ),
        _opt(
            _MEDIA_QID, 5,
            text="요즘 유행하는 콘텐츠를 찾아보고 비교하는 것",
            role_id="trend_research",
            primary_trait_delta={"information_comparison": 1},
            next_probe="트렌드 비교가 실제 선택 기준으로 이어지는지 확인",
            preferred_frames=["limited_time_priority", "first_action"],
        ),
    ],
)

SCHOOL_LIFE_SEED_01 = SeedQuestion(
    question_id=_SCHOOL_QID,
    context="school_life",
    question_text="학교에서 수업·과제·동아리·친구 관계 중 가장 흥미를 느끼는 부분은 무엇인가요?",
    options=[
        _opt(
            _SCHOOL_QID, 1,
            text="과제나 프로젝트를 어떻게 진행할지 미리 계획하는 것",
            role_id="task_planning",
            primary_trait_delta={"planning": 1},
            next_probe="계획 수립이 실제 실행 방식으로 이어지는지 확인",
            preferred_frames=["limited_time_priority", "first_action"],
        ),
        _opt(
            _SCHOOL_QID, 2,
            text="조별 활동에서 역할을 나누고 함께 만들어가는 것",
            role_id="team_project",
            primary_trait_delta={"collaboration_preference": 1},
            next_probe="협업 선호가 역할 분담 기준으로 이어지는지 확인",
            preferred_frames=["team_role", "conflicting_opinions"],
        ),
        _opt(
            _SCHOOL_QID, 3,
            text="의견이 다를 때 기준을 세워서 조율하는 것",
            role_id="conflict_mediation",
            primary_trait_delta={"opinion_mediation": 1},
            next_probe="조정 기준이 다른 상황에서도 일관되는지 확인",
            preferred_frames=["conflicting_opinions", "others_reaction"],
        ),
        _opt(
            _SCHOOL_QID, 4,
            text="친구의 감정이나 상황을 이해하고 챙기는 것",
            role_id="peer_understanding",
            primary_trait_delta={"emotional_interpretation": 1},
            next_probe="감정 이해가 실제 행동으로 이어지는지 확인",
            preferred_frames=["others_reaction", "team_role"],
        ),
        _opt(
            _SCHOOL_QID, 5,
            text="계획이 틀어졌을 때 상황에 맞게 바꿔가는 것",
            role_id="adapting_change",
            primary_trait_delta={"change_adaptation": 1},
            next_probe="변화 대응이 새로운 도구·상황에서도 이어지는지 확인",
            preferred_frames=["new_tool", "unexpected_result"],
        ),
    ],
)

VERTICAL_SLICE_SEED_QUESTIONS: dict[str, SeedQuestion] = {
    "game": GAME_SEED_01,
    "media": MEDIA_SEED_01,
    "school_life": SCHOOL_LIFE_SEED_01,
}
