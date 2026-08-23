"""Anchor별 Backup Question 15개 — 2026-08-23 Trait Ontology v2(2.5.4단계) §3/§4/§5.

사용자가 기존 6개 Backup(Context당 2개, 모든 Anchor 공통)을 전부 "부자연스러움"으로
REVISE 판정했다(2.5.4단계 §1) — Context 전체를 억지로 포괄하려다 특정 Anchor에서
어색해지는 문제였다. 이 파일은 그 문제를 다른 방식으로 푼다: 15개 Anchor마다 그
Anchor의 실제 상황에서 자연스러운 Backup 질문을 1개씩 따로 쓴다. Context 전체를
아우르려 하지 않는다 — 각 질문은 정확히 그 Anchor 하나에서만 쓰인다
(`anchor_backup_applicability.py`가 `allowed_anchor_ids`로 강제한다).

설계 원칙(§4/§5):
- Trait를 골고루 채우려고 억지로 만들지 않는다 — 한 질문에 2개 NO_SIGNAL이 있어도
  된다("이 행동만으로는 특정 성향을 단정할 근거가 약하다"가 정직한 답일 때가 많다).
- 드문 행동(예: "게임 결과를 그림으로 표현한다")을 Trait 측정용으로 넣지 않는다.
- 미디어 Anchor는 감상 행동만 다룬다(제작·편집 전제 없음).
- 학교생활 Anchor는 조별 활동을 전제하지 않는다(club_activity만 예외적으로 허용).
- "콘텐츠를 본다"→visual_expression, "반응을 본다"→audience_response_prediction,
  "친구와 이야기함"→collaboration_preference, "바로 정함"→uncertainty_tolerance,
  "감정을 고려함"→emotional_interpretation 같은 자동 연결을 하지 않았다 — 각 Mapping은
  그 상황에서 실제로 그 행동이 무엇을 직접 보여주는지로만 정했다.

`primary_trait_delta={}`인 Option은 NO_SIGNAL이다(V2 Direct Probe·Context Routing과
같은 관례 — server가 만드는 FinalizedOption 스키마에는 별도 mapping_type 필드가 없어서
빈 dict 자체가 "이 선택지는 특정 Trait로 단정하지 않는다"는 뜻이다)."""

from __future__ import annotations

from src.schemas.question import FinalizedOption, FinalizedQuestion

# ============================== game ==============================

GAME_BACKUP_STORY_EXPLORATION_V2 = FinalizedQuestion(
    question_id="game_backup_story_exploration_v2",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="게임 속 이야기를 진행하다가 예상하지 못한 선택지가 나왔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="game_backup_story_exploration_v2_o1", role_id="weigh_outcome",
            text="이 선택이 이야기에 어떤 영향을 줄지 먼저 생각해본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="game_backup_story_exploration_v2_o2", role_id="pick_intuitively",
            text="끌리는 선택지를 바로 골라본다",
            primary_trait_delta={"immediate_execution": 1},
        ),
        FinalizedOption(
            option_id="game_backup_story_exploration_v2_o3", role_id="check_others_choice",
            text="다른 사람들은 어떤 선택을 했는지 찾아본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="game_backup_story_exploration_v2_o4", role_id="recall_pattern",
            text="이전 선택들과 비슷하게 이어지는 흐름이 있는지 떠올려본다",
            primary_trait_delta={"pattern_finding": 1},
        ),
        FinalizedOption(
            option_id="game_backup_story_exploration_v2_o5", role_id="reread_context",
            text="앞의 내용을 다시 읽어보고 정한다",
            primary_trait_delta={},
        ),
    ],
)

GAME_BACKUP_STRATEGY_PUZZLE_V2 = FinalizedQuestion(
    question_id="game_backup_strategy_puzzle_v2",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="전략을 짜거나 퍼즐을 풀다가 막혔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="game_backup_strategy_puzzle_v2_o1", role_id="reexamine_conditions",
            text="주어진 조건을 하나하나 다시 확인해본다",
            primary_trait_delta={"detail_orientation": 1},
        ),
        FinalizedOption(
            option_id="game_backup_strategy_puzzle_v2_o2", role_id="try_different_approach",
            text="다른 방법을 바로 시도해본다",
            primary_trait_delta={"immediate_execution": 1},
        ),
        FinalizedOption(
            option_id="game_backup_strategy_puzzle_v2_o3", role_id="search_solution",
            text="비슷한 문제의 해법을 찾아 비교해본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="game_backup_strategy_puzzle_v2_o4", role_id="take_a_break",
            text="잠깐 쉬었다가 다시 본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="game_backup_strategy_puzzle_v2_o5", role_id="narrow_down_pattern",
            text="막힌 지점에서 반복되는 규칙이 있는지 살펴본다",
            primary_trait_delta={"pattern_finding": 1},
        ),
    ],
)

GAME_BACKUP_COMPETITION_MASTERY_V2 = FinalizedQuestion(
    question_id="game_backup_competition_mastery_v2",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="실력을 겨루거나 기록에 도전하다가 계속 잘 안 될 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="game_backup_competition_mastery_v2_o1", role_id="analyze_mistake",
            text="어느 부분에서 왜 안 되는지 원인을 짚어본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="game_backup_competition_mastery_v2_o2", role_id="keep_retrying",
            text="같은 방식으로 될 때까지 계속 다시 시도한다",
            primary_trait_delta={"persistence_completion": 1},
        ),
        FinalizedOption(
            option_id="game_backup_competition_mastery_v2_o3", role_id="change_method",
            text="방법을 바꿔서 다시 시도한다",
            primary_trait_delta={"change_adaptation": 1},
        ),
        FinalizedOption(
            option_id="game_backup_competition_mastery_v2_o4", role_id="watch_others",
            text="잘하는 사람의 방식을 지켜본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="game_backup_competition_mastery_v2_o5", role_id="lower_goal",
            text="목표를 조금 낮춰서 부담을 줄인다",
            primary_trait_delta={},
        ),
    ],
)

GAME_BACKUP_COOPERATIVE_ROLE_V2 = FinalizedQuestion(
    question_id="game_backup_cooperative_role_v2",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="팀원과 역할을 나눠 게임을 진행하다가 상황이 갑자기 바뀌면 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="game_backup_cooperative_role_v2_o1", role_id="reassign_roles",
            text="팀원과 역할을 다시 나눠 맞춘다",
            primary_trait_delta={"collaboration_preference": 1},
        ),
        FinalizedOption(
            option_id="game_backup_cooperative_role_v2_o2", role_id="decide_alone_fast",
            text="일단 내 역할부터 바로 조정해서 움직인다",
            primary_trait_delta={"immediate_execution": 1},
        ),
        FinalizedOption(
            option_id="game_backup_cooperative_role_v2_o3", role_id="ask_team_opinion",
            text="팀원들 의견을 모아서 다음 방향을 정한다",
            primary_trait_delta={"opinion_mediation": 1},
        ),
        FinalizedOption(
            option_id="game_backup_cooperative_role_v2_o4", role_id="explain_situation",
            text="바뀐 상황을 팀원에게 설명해준다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="game_backup_cooperative_role_v2_o5", role_id="observe_team_first",
            text="팀원들이 어떻게 움직이는지 먼저 지켜본다",
            primary_trait_delta={},
        ),
    ],
)

GAME_BACKUP_BUILDING_CREATION_V2 = FinalizedQuestion(
    question_id="game_backup_building_creation_v2",
    context="game",
    target_traits=[],
    frame_id="backup",
    question_text="무언가를 만들거나 꾸미다가 생각한 대로 잘 안 될 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="game_backup_building_creation_v2_o1", role_id="redesign_structure",
            text="구조나 배치를 완전히 다르게 다시 구상해본다",
            primary_trait_delta={"creative_ideation": 1},
        ),
        FinalizedOption(
            option_id="game_backup_building_creation_v2_o2", role_id="try_again_same_way",
            text="같은 방식으로 계속 다시 시도한다",
            primary_trait_delta={"persistence_completion": 1},
        ),
        FinalizedOption(
            option_id="game_backup_building_creation_v2_o3", role_id="find_reference",
            text="다른 사람이 만든 것을 찾아 참고한다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="game_backup_building_creation_v2_o4", role_id="use_new_material",
            text="다른 재료나 도구를 새로 써본다",
            primary_trait_delta={"tool_utilization": 1},
        ),
        FinalizedOption(
            option_id="game_backup_building_creation_v2_o5", role_id="step_away_first",
            text="잠깐 손을 떼고 나중에 다시 본다",
            primary_trait_delta={},
        ),
    ],
)

# ============================== media ==============================

MEDIA_BACKUP_FILM_DRAMA_V2 = FinalizedQuestion(
    question_id="media_backup_film_drama_v2",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="영화나 드라마를 보다가 인상 깊은 장면이 나왔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_film_drama_v2_o1", role_id="rewind_scene",
            text="그 장면을 다시 돌려보며 세부적인 부분을 확인한다",
            primary_trait_delta={"detail_orientation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_film_drama_v2_o2", role_id="guess_reason",
            text="인물이 왜 그런 선택을 했는지 이유를 생각해본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="media_backup_film_drama_v2_o3", role_id="imagine_ending",
            text="이후 이야기가 어떻게 이어질지 상상해본다",
            primary_trait_delta={"creative_ideation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_film_drama_v2_o4", role_id="tell_someone",
            text="옆에 있는 사람에게 바로 이야기한다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="media_backup_film_drama_v2_o5", role_id="keep_watching",
            text="별다른 행동 없이 계속 본다",
            primary_trait_delta={},
        ),
    ],
)

MEDIA_BACKUP_ONLINE_VIDEO_V2 = FinalizedQuestion(
    question_id="media_backup_online_video_v2",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="유튜브 같은 온라인 영상을 보다가 흥미로운 내용이 나왔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_online_video_v2_o1", role_id="pause_and_check",
            text="영상을 멈추고 그 부분을 다시 확인한다",
            primary_trait_delta={"detail_orientation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_online_video_v2_o2", role_id="search_more_info",
            text="관련된 다른 정보를 검색해서 찾아본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="media_backup_online_video_v2_o3", role_id="predict_next",
            text="다음에 어떤 내용이 나올지 예상해본다",
            primary_trait_delta={"audience_response_prediction": 1},
        ),
        FinalizedOption(
            option_id="media_backup_online_video_v2_o4", role_id="skip_ahead",
            text="지루한 부분은 건너뛰고 본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="media_backup_online_video_v2_o5", role_id="read_comments",
            text="댓글 반응이 어떤지 확인해본다",
            primary_trait_delta={},
        ),
    ],
)

MEDIA_BACKUP_ANIMATION_WEBCONTENT_V2 = FinalizedQuestion(
    question_id="media_backup_animation_webcontent_v2",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="애니메이션이나 웹툰을 보다가 새로운 등장인물이나 설정이 나왔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_animation_webcontent_v2_o1", role_id="connect_to_world",
            text="이 설정이 전체 세계관과 어떻게 연결되는지 생각해본다",
            primary_trait_delta={"systems_thinking": 1},
        ),
        FinalizedOption(
            option_id="media_backup_animation_webcontent_v2_o2", role_id="compare_similar_work",
            text="비슷한 다른 작품과 비교해본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="media_backup_animation_webcontent_v2_o3", role_id="imagine_backstory",
            text="이 인물에게 어떤 사연이 있을지 상상해본다",
            primary_trait_delta={"creative_ideation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_animation_webcontent_v2_o4", role_id="keep_reading",
            text="별다른 생각 없이 계속 본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="media_backup_animation_webcontent_v2_o5", role_id="check_reactions",
            text="다른 사람들 반응이 어떤지 찾아본다",
            primary_trait_delta={},
        ),
    ],
)

MEDIA_BACKUP_STAGE_PERFORMANCE_V2 = FinalizedQuestion(
    question_id="media_backup_stage_performance_v2",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="공연이나 뮤지컬을 보다가 인상 깊은 장면이 나왔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_stage_performance_v2_o1", role_id="notice_staging",
            text="무대·조명이 어떻게 꾸며졌는지 자세히 살펴본다",
            primary_trait_delta={"detail_orientation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_stage_performance_v2_o2", role_id="guess_actor_emotion",
            text="배우가 그 순간 어떤 감정으로 연기했을지 헤아려본다",
            primary_trait_delta={"emotional_interpretation": 1},
        ),
        FinalizedOption(
            option_id="media_backup_stage_performance_v2_o3", role_id="compare_other_performance",
            text="이전에 본 다른 공연과 비교해본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="media_backup_stage_performance_v2_o4", role_id="clap_or_react",
            text="자연스럽게 박수를 치거나 반응한다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="media_backup_stage_performance_v2_o5", role_id="keep_watching",
            text="별다른 행동 없이 계속 본다",
            primary_trait_delta={},
        ),
    ],
)

MEDIA_BACKUP_DOCUMENTARY_V2 = FinalizedQuestion(
    question_id="media_backup_documentary_v2",
    context="media",
    target_traits=[],
    frame_id="backup",
    question_text="다큐멘터리를 보다가 새로운 사실이나 정보가 나왔을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="media_backup_documentary_v2_o1", role_id="question_evidence",
            text="그 내용이 왜 그런 결론에 이르렀는지 근거를 따져본다",
            primary_trait_delta={"causal_analysis": 1},
        ),
        FinalizedOption(
            option_id="media_backup_documentary_v2_o2", role_id="compare_other_source",
            text="다른 자료에서는 어떻게 설명하는지 찾아본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="media_backup_documentary_v2_o3", role_id="connect_bigger_picture",
            text="이 내용이 전체 주제와 어떻게 연결되는지 생각해본다",
            primary_trait_delta={"systems_thinking": 1},
        ),
        FinalizedOption(
            option_id="media_backup_documentary_v2_o4", role_id="accept_as_is",
            text="별다른 의문 없이 그대로 받아들인다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="media_backup_documentary_v2_o5", role_id="share_with_someone",
            text="흥미로운 내용을 다른 사람에게 공유한다",
            primary_trait_delta={},
        ),
    ],
)

# ============================== school_life ==============================

SCHOOL_LIFE_BACKUP_ACADEMIC_STUDY_V2 = FinalizedQuestion(
    question_id="school_life_backup_academic_study_v2",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="시험공부를 하다가 예상보다 진도가 늦어지고 있다는 걸 깨달았을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_academic_study_v2_o1", role_id="replan_schedule",
            text="남은 시간과 순서를 다시 계획한다",
            primary_trait_delta={"planning": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_academic_study_v2_o2", role_id="push_through",
            text="원래 계획대로 끝까지 밀어붙인다",
            primary_trait_delta={"persistence_completion": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_academic_study_v2_o3", role_id="cut_less_important",
            text="덜 중요한 부분을 줄이고 방식을 바꾼다",
            primary_trait_delta={"change_adaptation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_academic_study_v2_o4", role_id="ask_friend_progress",
            text="친구는 어디까지 했는지 물어본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="school_life_backup_academic_study_v2_o5", role_id="take_short_rest",
            text="잠깐 쉬었다가 다시 시작한다",
            primary_trait_delta={},
        ),
    ],
)

SCHOOL_LIFE_BACKUP_ASSIGNMENT_EVALUATION_V2 = FinalizedQuestion(
    question_id="school_life_backup_assignment_evaluation_v2",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="수행평가 제출 기한이 얼마 남지 않았는데 아직 다 끝내지 못했을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_assignment_evaluation_v2_o1", role_id="prioritize_remaining",
            text="남은 항목의 우선순위를 다시 정한다",
            primary_trait_delta={"planning": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_assignment_evaluation_v2_o2", role_id="finish_current_first",
            text="지금 하던 부분부터 끝까지 마무리한다",
            primary_trait_delta={"persistence_completion": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_assignment_evaluation_v2_o3", role_id="ask_teacher_extension",
            text="선생님께 상황을 말씀드려본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="school_life_backup_assignment_evaluation_v2_o4", role_id="simplify_remaining",
            text="남은 부분은 간단하게 방식을 바꿔 끝낸다",
            primary_trait_delta={"change_adaptation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_assignment_evaluation_v2_o5", role_id="check_requirements_again",
            text="제출 조건을 다시 하나하나 확인한다",
            primary_trait_delta={"detail_orientation": 1},
        ),
    ],
)

SCHOOL_LIFE_BACKUP_COURSE_CAREER_V2 = FinalizedQuestion(
    question_id="school_life_backup_course_career_v2",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="선택과목이나 진로를 정해야 하는데 아직 확신이 서지 않을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_course_career_v2_o1", role_id="research_more_info",
            text="관련 정보를 더 찾아서 비교해본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_course_career_v2_o2", role_id="decide_with_current_info",
            text="지금까지 알아본 것만으로 일단 정한다",
            primary_trait_delta={"uncertainty_tolerance": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_course_career_v2_o3", role_id="ask_teacher_or_senior",
            text="선생님이나 선배에게 물어본다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="school_life_backup_course_career_v2_o4", role_id="list_pros_cons",
            text="선택지별 장단점을 정리해본다",
            primary_trait_delta={"planning": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_course_career_v2_o5", role_id="postpone_decision",
            text="일단 결정을 미뤄둔다",
            primary_trait_delta={},
        ),
    ],
)

SCHOOL_LIFE_BACKUP_FRIENDSHIP_V2 = FinalizedQuestion(
    question_id="school_life_backup_friendship_v2",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="친구와 이야기하다가 생각이 다르다는 걸 알게 됐을 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_friendship_v2_o1", role_id="explain_my_view",
            text="내 생각을 친구에게 분명하게 말한다",
            primary_trait_delta={"opinion_expression": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_friendship_v2_o2", role_id="find_common_ground",
            text="서로 받아들일 수 있는 지점을 찾아본다",
            primary_trait_delta={"opinion_mediation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_friendship_v2_o3", role_id="understand_friend_view",
            text="친구가 왜 그렇게 생각하는지 먼저 이해해본다",
            primary_trait_delta={"emotional_interpretation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_friendship_v2_o4", role_id="drop_the_topic",
            text="그 이야기는 넘어가고 다른 얘기를 한다",
            primary_trait_delta={},
        ),
        FinalizedOption(
            option_id="school_life_backup_friendship_v2_o5", role_id="follow_friend_opinion",
            text="친구 생각에 맞춰준다",
            primary_trait_delta={},
        ),
    ],
)

SCHOOL_LIFE_BACKUP_CLUB_ACTIVITY_V2 = FinalizedQuestion(
    question_id="school_life_backup_club_activity_v2",
    context="school_life",
    target_traits=[],
    frame_id="backup",
    question_text="동아리 활동 방향을 정해야 하는데 부원들 의견이 갈릴 때 무엇을 가장 먼저 하나요?",
    options=[
        FinalizedOption(
            option_id="school_life_backup_club_activity_v2_o1", role_id="gather_opinions",
            text="부원들 의견을 모아서 공통점을 찾아본다",
            primary_trait_delta={"opinion_mediation": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_club_activity_v2_o2", role_id="propose_own_idea",
            text="내 생각을 먼저 제안해본다",
            primary_trait_delta={"opinion_expression": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_club_activity_v2_o3", role_id="check_precedent",
            text="예전에는 어떻게 정했는지 찾아본다",
            primary_trait_delta={"information_comparison": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_club_activity_v2_o4", role_id="assign_roles",
            text="역할을 나눠 각자 맡은 부분을 진행한다",
            primary_trait_delta={"collaboration_preference": 1},
        ),
        FinalizedOption(
            option_id="school_life_backup_club_activity_v2_o5", role_id="wait_for_decision",
            text="누군가 정해줄 때까지 기다린다",
            primary_trait_delta={},
        ),
    ],
)

ANCHOR_BACKUP_QUESTIONS: list[FinalizedQuestion] = [
    GAME_BACKUP_STORY_EXPLORATION_V2, GAME_BACKUP_STRATEGY_PUZZLE_V2, GAME_BACKUP_COMPETITION_MASTERY_V2,
    GAME_BACKUP_COOPERATIVE_ROLE_V2, GAME_BACKUP_BUILDING_CREATION_V2,
    MEDIA_BACKUP_FILM_DRAMA_V2, MEDIA_BACKUP_ONLINE_VIDEO_V2, MEDIA_BACKUP_ANIMATION_WEBCONTENT_V2,
    MEDIA_BACKUP_STAGE_PERFORMANCE_V2, MEDIA_BACKUP_DOCUMENTARY_V2,
    SCHOOL_LIFE_BACKUP_ACADEMIC_STUDY_V2, SCHOOL_LIFE_BACKUP_ASSIGNMENT_EVALUATION_V2,
    SCHOOL_LIFE_BACKUP_COURSE_CAREER_V2, SCHOOL_LIFE_BACKUP_FRIENDSHIP_V2, SCHOOL_LIFE_BACKUP_CLUB_ACTIVITY_V2,
]

# (context_id, anchor_id) -> 질문. question_id의 "{context}_backup_{anchor_id}_v2" 규칙과
# 별개로, Runtime 조회는 항상 이 Key로 한다(질문 문구 파싱에 의존하지 않는다).
ANCHOR_BACKUP_QUESTIONS_BY_KEY: dict[tuple[str, str], FinalizedQuestion] = {
    ("game", "story_exploration"): GAME_BACKUP_STORY_EXPLORATION_V2,
    ("game", "strategy_puzzle"): GAME_BACKUP_STRATEGY_PUZZLE_V2,
    ("game", "competition_mastery"): GAME_BACKUP_COMPETITION_MASTERY_V2,
    ("game", "cooperative_role"): GAME_BACKUP_COOPERATIVE_ROLE_V2,
    ("game", "building_creation"): GAME_BACKUP_BUILDING_CREATION_V2,
    ("media", "film_drama"): MEDIA_BACKUP_FILM_DRAMA_V2,
    ("media", "online_video"): MEDIA_BACKUP_ONLINE_VIDEO_V2,
    ("media", "animation_webcontent"): MEDIA_BACKUP_ANIMATION_WEBCONTENT_V2,
    ("media", "stage_performance"): MEDIA_BACKUP_STAGE_PERFORMANCE_V2,
    ("media", "documentary"): MEDIA_BACKUP_DOCUMENTARY_V2,
    ("school_life", "academic_study"): SCHOOL_LIFE_BACKUP_ACADEMIC_STUDY_V2,
    ("school_life", "assignment_evaluation"): SCHOOL_LIFE_BACKUP_ASSIGNMENT_EVALUATION_V2,
    ("school_life", "course_career"): SCHOOL_LIFE_BACKUP_COURSE_CAREER_V2,
    ("school_life", "friendship"): SCHOOL_LIFE_BACKUP_FRIENDSHIP_V2,
    ("school_life", "club_activity"): SCHOOL_LIFE_BACKUP_CLUB_ACTIVITY_V2,
}

ANCHOR_BACKUP_QUESTIONS_BY_ID: dict[str, FinalizedQuestion] = {q.question_id: q for q in ANCHOR_BACKUP_QUESTIONS}
