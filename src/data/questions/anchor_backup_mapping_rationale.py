"""Anchor Backup Question Mapping Rationale Draft 정본 — 2026-08-23 Trait Ontology
v2(2.5.4단계) §5/§9.

75개(15 질문 x 5 Option) 전부에 대해 "왜 이 문구가 이 Trait 후보로 연결되는지 또는
왜 NO_SIGNAL인지" 한 문장 초안을 남긴다. `_validate()`가 import 시점에 실제
Anchor Backup Question(`ANCHOR_BACKUP_QUESTIONS`)과 Key(question_id, role_id)
집합이 정확히 같은지, trait_id가 실제 Option Mapping과 일치하는지, 빈 Rationale이
없는지 Fail-Fast로 검증한다."""

from __future__ import annotations

from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS
from src.schemas.backup_option_rationale import BackupOptionRationale, BackupOptionRationaleError

ANCHOR_BACKUP_MAPPING_RATIONALE: list[BackupOptionRationale] = [
    BackupOptionRationale(
        question_id="game_backup_story_exploration_v2", role_id="weigh_outcome", trait_id="causal_analysis",
        mapping_rationale_draft="이야기 선택이 가져올 영향을 능동적으로 따져보는 행동이 직접 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_story_exploration_v2", role_id="pick_intuitively", trait_id="immediate_execution",
        mapping_rationale_draft="생각보다 먼저 끌리는 선택지를 바로 고르는 행동이 직접 드러나 immediate_execution 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_story_exploration_v2", role_id="check_others_choice", trait_id=None,
        mapping_rationale_draft="다른 사람의 선택을 찾아보는 것은 정보 확인 행동일 뿐, 특정 성향을 직접 보여주는 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="game_backup_story_exploration_v2", role_id="recall_pattern", trait_id="pattern_finding",
        mapping_rationale_draft="이전 선택들과 이어지는 흐름을 스스로 찾아내는 행동이 드러나 pattern_finding 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_story_exploration_v2", role_id="reread_context", trait_id=None,
        mapping_rationale_draft="앞 내용을 다시 읽는 것은 진행을 위한 일반적인 확인 행동일 뿐, 특정 성향의 직접 근거는 아니다",
    ),
    BackupOptionRationale(
        question_id="game_backup_strategy_puzzle_v2", role_id="reexamine_conditions", trait_id="detail_orientation",
        mapping_rationale_draft="주어진 조건을 하나하나 다시 확인하는 행동이 직접 드러나 detail_orientation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_strategy_puzzle_v2", role_id="try_different_approach", trait_id="immediate_execution",
        mapping_rationale_draft="생각보다 먼저 다른 방법을 바로 시도하는 행동이 드러나 immediate_execution 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_strategy_puzzle_v2", role_id="search_solution", trait_id="information_comparison",
        mapping_rationale_draft="비슷한 문제의 해법을 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_strategy_puzzle_v2", role_id="take_a_break", trait_id=None,
        mapping_rationale_draft="잠깐 쉬는 것은 일반적인 컨디션 관리 행동일 뿐, 특정 성향의 직접 근거로 보기 어렵다",
    ),
    BackupOptionRationale(
        question_id="game_backup_strategy_puzzle_v2", role_id="narrow_down_pattern", trait_id="pattern_finding",
        mapping_rationale_draft="막힌 지점에서 반복 규칙을 스스로 찾아내는 행동이 드러나 pattern_finding 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_competition_mastery_v2", role_id="analyze_mistake", trait_id="causal_analysis",
        mapping_rationale_draft="실패 원인을 능동적으로 짚어보는 행동이 직접 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_competition_mastery_v2", role_id="keep_retrying", trait_id="persistence_completion",
        mapping_rationale_draft="같은 목표를 포기하지 않고 계속 시도하는 행동이 직접 드러나 persistence_completion 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_competition_mastery_v2", role_id="change_method", trait_id="change_adaptation",
        mapping_rationale_draft="안 되는 방법을 버리고 접근 방식을 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_competition_mastery_v2", role_id="watch_others", trait_id=None,
        mapping_rationale_draft="다른 사람의 방식을 구경하는 것은 정보 습득 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="game_backup_competition_mastery_v2", role_id="lower_goal", trait_id=None,
        mapping_rationale_draft="목표를 낮추는 것은 적극적 대응이라기보다 부담을 줄이는 소극적 선택이라 특정 성향으로 단정하기 어렵다",
    ),
    BackupOptionRationale(
        question_id="game_backup_cooperative_role_v2", role_id="reassign_roles", trait_id="collaboration_preference",
        mapping_rationale_draft="팀원과 실제로 역할을 다시 나누는 행동이 직접 드러나 collaboration_preference 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_cooperative_role_v2", role_id="decide_alone_fast", trait_id="immediate_execution",
        mapping_rationale_draft="생각보다 먼저 내 몫부터 바로 조정해 움직이는 행동이 드러나 immediate_execution 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_cooperative_role_v2", role_id="ask_team_opinion", trait_id="opinion_mediation",
        mapping_rationale_draft="팀원들 의견을 모아 다음 방향을 정하는 행동이 직접 드러나 opinion_mediation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_cooperative_role_v2", role_id="explain_situation", trait_id=None,
        mapping_rationale_draft="상황을 설명하는 것은 일반적인 의사소통 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="game_backup_cooperative_role_v2", role_id="observe_team_first", trait_id=None,
        mapping_rationale_draft="팀원들을 지켜보는 것은 수동적 관찰이라 특정 성향을 단정할 근거로 보기 어렵다",
    ),
    BackupOptionRationale(
        question_id="game_backup_building_creation_v2", role_id="redesign_structure", trait_id="creative_ideation",
        mapping_rationale_draft="구조를 완전히 다르게 다시 구상하는 행동이 직접 드러나 creative_ideation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_building_creation_v2", role_id="try_again_same_way", trait_id="persistence_completion",
        mapping_rationale_draft="같은 방식으로 포기하지 않고 계속 시도하는 행동이 직접 드러나 persistence_completion 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_building_creation_v2", role_id="find_reference", trait_id="information_comparison",
        mapping_rationale_draft="다른 사람의 결과물을 찾아 참고하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_building_creation_v2", role_id="use_new_material", trait_id="tool_utilization",
        mapping_rationale_draft="새로운 재료·도구를 시도해 활용하는 행동이 직접 드러나 tool_utilization 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="game_backup_building_creation_v2", role_id="step_away_first", trait_id=None,
        mapping_rationale_draft="잠깐 손을 떼는 것은 일반적인 휴식 행동일 뿐, 특정 성향의 직접 근거는 아니다",
    ),
    BackupOptionRationale(
        question_id="media_backup_film_drama_v2", role_id="rewind_scene", trait_id="detail_orientation",
        mapping_rationale_draft="장면을 다시 돌려보며 세부를 확인하는 행동이 직접 드러나 detail_orientation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_film_drama_v2", role_id="guess_reason", trait_id="causal_analysis",
        mapping_rationale_draft="인물 선택의 이유를 능동적으로 따져보는 행동이 직접 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_film_drama_v2", role_id="imagine_ending", trait_id="creative_ideation",
        mapping_rationale_draft="이후 전개를 스스로 상상해보는 행동이 직접 드러나 creative_ideation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_film_drama_v2", role_id="tell_someone", trait_id=None,
        mapping_rationale_draft="옆 사람에게 바로 이야기하는 것은 일반적인 반응 공유 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="media_backup_film_drama_v2", role_id="keep_watching", trait_id=None,
        mapping_rationale_draft="별다른 행동 없이 계속 보는 것은 감상의 기본 행동이라 특정 성향의 근거가 되기 어렵다",
    ),
    BackupOptionRationale(
        question_id="media_backup_online_video_v2", role_id="pause_and_check", trait_id="detail_orientation",
        mapping_rationale_draft="영상을 멈추고 다시 확인하는 행동이 직접 드러나 detail_orientation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_online_video_v2", role_id="search_more_info", trait_id="information_comparison",
        mapping_rationale_draft="관련 정보를 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_online_video_v2", role_id="predict_next", trait_id="audience_response_prediction",
        mapping_rationale_draft="다음 내용을 스스로 예상해보는 행동이 직접 드러나 audience_response_prediction 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_online_video_v2", role_id="skip_ahead", trait_id=None,
        mapping_rationale_draft="지루한 부분을 건너뛰는 것은 일반적인 시청 습관일 뿐, 특정 성향의 직접 근거는 아니다",
    ),
    BackupOptionRationale(
        question_id="media_backup_online_video_v2", role_id="read_comments", trait_id=None,
        mapping_rationale_draft="댓글을 확인하는 것은 정보 확인 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="media_backup_animation_webcontent_v2", role_id="connect_to_world", trait_id="systems_thinking",
        mapping_rationale_draft="새 설정이 전체 세계관과 어떻게 연결되는지 스스로 짚어보는 행동이 직접 드러나 systems_thinking 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_animation_webcontent_v2", role_id="compare_similar_work", trait_id="information_comparison",
        mapping_rationale_draft="비슷한 다른 작품과 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_animation_webcontent_v2", role_id="imagine_backstory", trait_id="creative_ideation",
        mapping_rationale_draft="인물의 사연을 스스로 상상해보는 행동이 직접 드러나 creative_ideation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_animation_webcontent_v2", role_id="keep_reading", trait_id=None,
        mapping_rationale_draft="별다른 생각 없이 계속 보는 것은 감상의 기본 행동이라 특정 성향의 근거가 되기 어렵다",
    ),
    BackupOptionRationale(
        question_id="media_backup_animation_webcontent_v2", role_id="check_reactions", trait_id=None,
        mapping_rationale_draft="다른 사람 반응을 찾아보는 것은 정보 확인 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="media_backup_stage_performance_v2", role_id="notice_staging", trait_id="detail_orientation",
        mapping_rationale_draft="무대·조명 연출을 자세히 살펴보는 행동이 직접 드러나 detail_orientation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_stage_performance_v2", role_id="guess_actor_emotion", trait_id="emotional_interpretation",
        mapping_rationale_draft="배우의 감정을 헤아려보는 행동이 직접 드러나 emotional_interpretation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_stage_performance_v2", role_id="compare_other_performance", trait_id="information_comparison",
        mapping_rationale_draft="이전에 본 다른 공연과 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_stage_performance_v2", role_id="clap_or_react", trait_id=None,
        mapping_rationale_draft="박수·반응은 관람 예절에 가까운 일반적 행동이라 특정 성향의 근거로 보기 어렵다",
    ),
    BackupOptionRationale(
        question_id="media_backup_stage_performance_v2", role_id="keep_watching", trait_id=None,
        mapping_rationale_draft="별다른 행동 없이 계속 관람하는 것은 감상의 기본 행동이라 특정 성향의 근거가 되기 어렵다",
    ),
    BackupOptionRationale(
        question_id="media_backup_documentary_v2", role_id="question_evidence", trait_id="causal_analysis",
        mapping_rationale_draft="결론에 이른 근거를 능동적으로 따져보는 행동이 직접 드러나 causal_analysis 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_documentary_v2", role_id="compare_other_source", trait_id="information_comparison",
        mapping_rationale_draft="다른 자료의 설명과 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_documentary_v2", role_id="connect_bigger_picture", trait_id="systems_thinking",
        mapping_rationale_draft="내용을 전체 주제와 연결해보는 행동이 직접 드러나 systems_thinking 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="media_backup_documentary_v2", role_id="accept_as_is", trait_id=None,
        mapping_rationale_draft="의문 없이 그대로 받아들이는 것은 특정 성향보다는 수동적 시청 태도에 가깝다",
    ),
    BackupOptionRationale(
        question_id="media_backup_documentary_v2", role_id="share_with_someone", trait_id=None,
        mapping_rationale_draft="다른 사람에게 공유하는 것은 일반적인 소통 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_academic_study_v2", role_id="replan_schedule", trait_id="planning",
        mapping_rationale_draft="남은 시간과 순서를 다시 짜는 행동이 직접 드러나 planning 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_academic_study_v2", role_id="push_through", trait_id="persistence_completion",
        mapping_rationale_draft="원래 계획을 포기하지 않고 끝까지 밀어붙이는 행동이 직접 드러나 persistence_completion 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_academic_study_v2", role_id="cut_less_important", trait_id="change_adaptation",
        mapping_rationale_draft="덜 중요한 부분을 줄이며 방식을 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_academic_study_v2", role_id="ask_friend_progress", trait_id=None,
        mapping_rationale_draft="친구 진도를 묻는 것은 정보 확인 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_academic_study_v2", role_id="take_short_rest", trait_id=None,
        mapping_rationale_draft="잠깐 쉬는 것은 일반적인 컨디션 관리 행동일 뿐, 특정 성향의 직접 근거는 아니다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_assignment_evaluation_v2", role_id="prioritize_remaining", trait_id="planning",
        mapping_rationale_draft="남은 항목의 우선순위를 다시 정하는 행동이 직접 드러나 planning 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_assignment_evaluation_v2", role_id="finish_current_first", trait_id="persistence_completion",
        mapping_rationale_draft="하던 부분을 끝까지 마무리하려는 행동이 직접 드러나 persistence_completion 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_assignment_evaluation_v2", role_id="ask_teacher_extension", trait_id=None,
        mapping_rationale_draft="선생님께 상황을 말씀드리는 것은 상황 확인 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_assignment_evaluation_v2", role_id="simplify_remaining", trait_id="change_adaptation",
        mapping_rationale_draft="남은 방식을 간단하게 바꾸는 행동이 직접 드러나 change_adaptation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_assignment_evaluation_v2", role_id="check_requirements_again", trait_id="detail_orientation",
        mapping_rationale_draft="제출 조건을 하나하나 다시 확인하는 행동이 직접 드러나 detail_orientation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_course_career_v2", role_id="research_more_info", trait_id="information_comparison",
        mapping_rationale_draft="관련 정보를 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_course_career_v2", role_id="decide_with_current_info", trait_id="uncertainty_tolerance",
        mapping_rationale_draft="정보가 부족해도 확인된 것만으로 결정을 내리는 행동이 직접 드러나 uncertainty_tolerance 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_course_career_v2", role_id="ask_teacher_or_senior", trait_id=None,
        mapping_rationale_draft="선생님이나 선배에게 묻는 것은 정보 탐색 행동일 뿐, 특정 성향의 직접 근거로 보기는 약하다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_course_career_v2", role_id="list_pros_cons", trait_id="planning",
        mapping_rationale_draft="선택지별 장단점을 정리하는 행동이 직접 드러나 planning 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_course_career_v2", role_id="postpone_decision", trait_id=None,
        mapping_rationale_draft="결정을 미루는 것은 특정 성향의 적극적 근거로 보기보다 회피에 가깝다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_friendship_v2", role_id="explain_my_view", trait_id="opinion_expression",
        mapping_rationale_draft="내 생각을 분명하게 말하는 행동이 직접 드러나 opinion_expression 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_friendship_v2", role_id="find_common_ground", trait_id="opinion_mediation",
        mapping_rationale_draft="서로 받아들일 수 있는 지점을 찾는 행동이 직접 드러나 opinion_mediation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_friendship_v2", role_id="understand_friend_view", trait_id="emotional_interpretation",
        mapping_rationale_draft="친구의 생각을 먼저 이해해보려는 행동이 직접 드러나 emotional_interpretation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_friendship_v2", role_id="drop_the_topic", trait_id=None,
        mapping_rationale_draft="화제를 넘기는 것은 회피에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_friendship_v2", role_id="follow_friend_opinion", trait_id=None,
        mapping_rationale_draft="그대로 맞춰주는 것은 수동적 동조에 가까워 특정 성향의 적극적 근거로 보기 어렵다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_club_activity_v2", role_id="gather_opinions", trait_id="opinion_mediation",
        mapping_rationale_draft="부원들 의견을 모아 공통점을 찾는 행동이 직접 드러나 opinion_mediation 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_club_activity_v2", role_id="propose_own_idea", trait_id="opinion_expression",
        mapping_rationale_draft="내 생각을 먼저 제안하는 행동이 직접 드러나 opinion_expression 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_club_activity_v2", role_id="check_precedent", trait_id="information_comparison",
        mapping_rationale_draft="예전 사례를 찾아 비교하는 행동이 직접 드러나 information_comparison 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_club_activity_v2", role_id="assign_roles", trait_id="collaboration_preference",
        mapping_rationale_draft="역할을 나눠 함께 진행하는 행동이 직접 드러나 collaboration_preference 후보로 연결된다",
    ),
    BackupOptionRationale(
        question_id="school_life_backup_club_activity_v2", role_id="wait_for_decision", trait_id=None,
        mapping_rationale_draft="누군가 정해주길 기다리는 것은 특정 성향의 적극적 근거로 보기 어렵다",
    ),
]

ANCHOR_BACKUP_MAPPING_RATIONALE_BY_KEY: dict[tuple[str, str], BackupOptionRationale] = {
    (r.question_id, r.role_id): r for r in ANCHOR_BACKUP_MAPPING_RATIONALE
}


def _validate() -> None:
    keys = [(r.question_id, r.role_id) for r in ANCHOR_BACKUP_MAPPING_RATIONALE]
    if len(keys) != len(set(keys)):
        raise BackupOptionRationaleError(f"(question_id, role_id) 중복이 있다: {keys}")

    expected: dict[tuple[str, str], str | None] = {}
    for question in ANCHOR_BACKUP_QUESTIONS:
        for option in question.options:
            expected[(question.question_id, option.role_id)] = next(iter(option.primary_trait_delta), None)

    if set(keys) != set(expected.keys()):
        missing = set(expected.keys()) - set(keys)
        extra = set(keys) - set(expected.keys())
        raise BackupOptionRationaleError(
            f"Anchor Backup Mapping Rationale 집합이 실제 Option 목록과 다르다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    for rationale_entry in ANCHOR_BACKUP_MAPPING_RATIONALE:
        key = (rationale_entry.question_id, rationale_entry.role_id)
        if rationale_entry.trait_id != expected[key]:
            raise BackupOptionRationaleError(
                f"{key}: trait_id가 실제 Option Mapping과 다르다"
                f"(정본: {expected[key]!r}, 여기: {rationale_entry.trait_id!r})"
            )
        if not rationale_entry.mapping_rationale_draft.strip():
            raise BackupOptionRationaleError(f"{key}: Mapping Rationale Draft가 비어 있다")


_validate()
