"""V2 Direct Probe Question Review Worksheet 생성 — 2026-08-23 Trait Ontology v2(2.1단계) §10.

14개 Blueprint × 5개 Option = 70행을 담은 검수 Worksheet를 만든다. "행동-Trait 직접
일치 여부"/"인접 Trait 혼동 위험"/"사회적 바람직성 편향"/"문장 자연스러움"·수정 전/후
문구는 A(작업자)가 §7~§9에서 실제로 검토한 판단을 코드에 데이터로 남긴 것이다 — 이
판단 자체는 사람 검토를 "대신"하지 않는다: "1차 사람 검토"/"2차 사람 검토"/"최종 상태"는
항상 TBD/draft로만 채운다(§10 "Claude가 스스로 완료로 처리하면 안 된다").

실행: PYTHONPATH=. ./.venv/bin/python scripts/generate_v2_direct_probe_question_review.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS  # noqa: E402
from src.engines.v2_direct_probe_quality_checks import worksheet_row_flags  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "reviews" / "v2_direct_probe_question_review.md"

# (blueprint_id, role_id) -> 사람이 직접 남긴 검토 메모. 없는 조합은 아래 DEFAULT_NOTE를 쓴다.
# "revised" 항목은 §8/§9에서 실제로 문구를 바꾼 자리 — 수정 전 문구를 그대로 남긴다.
_NOTES: dict[tuple[str, str], dict[str, str]] = {
    # --- systems_thinking_game_v1 ---
    ("systems_thinking_game_v1", "st_ripple_check"): {
        "behavior_trait_match": "예 — '다른 아이템·전략에 미치는 영향'을 직접 살펴보는 행동으로 요소 간 상호작용을 명시함",
        "adjacent_risk": "중간 — causal_analysis(원인 하나를 깊게 봄)와 구분되지만, '영향'이라는 단어가 causal과 겹쳐 보일 수 있어 2차 검토 필요",
        "desirability_bias": "낮음 — 다른 옵션도 각자 합리적인 행동으로 서술됨",
        "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_reason_first"): {
        "behavior_trait_match": "예 — causal_analysis(이유부터 생각)와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_try_it"): {
        "behavior_trait_match": "예 — immediate_execution과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_compare_items"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_ask_team"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- systems_thinking_school_life_v1 ---
    ("systems_thinking_school_life_v1", "st_map_impact"): {
        "behavior_trait_match": "예 — '역할과 서로 얽혀 영향을 주는지'로 요소 간 상호작용을 명시, planning(일정 재조정)과 구분되게 수정함",
        "adjacent_risk": "낮음(수정 후) — planning 옵션과 '전체를 다시 본다'는 표현이 겹치던 문제를 문구 수정으로 해소",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "이 변화가 다른 역할이나 전체 일정에 어떻게 이어질지 짚어본다",
        "after": "이 변화가 다른 사람의 역할과 어떻게 서로 얽혀 영향을 주는지 짚어본다",
    },
    ("systems_thinking_school_life_v1", "st_replan"): {
        "behavior_trait_match": "예 — planning과 직접 일치, '일정·순서를 다시 짠다'는 스케줄링 행동으로만 한정",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "전체 일정을 다시 짠다", "after": "남은 일정과 순서를 처음부터 다시 짠다",
    },
    ("systems_thinking_school_life_v1", "st_adapt_now"): {
        "behavior_trait_match": "예 — change_adaptation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("systems_thinking_school_life_v1", "st_check_mood"): {
        "behavior_trait_match": "예 — emotional_interpretation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "중간 — '친구 기분을 먼저 살핀다'가 배려로 읽혀 다른 선택지보다 약간 더 바람직해 보일 수 있음(참고용 표시)",
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_school_life_v1", "st_state_view"): {
        "behavior_trait_match": "예 — opinion_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- detail_orientation_media_v1 ---
    ("detail_orientation_media_v1", "do_scan_errors"): {
        "behavior_trait_match": "예 — '오탈자·어긋난 부분까지 하나하나' 세부 정확성을 직접 표현",
        "adjacent_risk": "낮음 — information_comparison(비교)과 구분됨", "desirability_bias": "낮음",
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("detail_orientation_media_v1", "do_overall_flow"): {
        "behavior_trait_match": "예(수정 후) — '반복되는 편집 패턴'으로 pattern_finding의 핵심 행동(반복 규칙 탐색)을 명확히 함",
        "adjacent_risk": "낮음(수정 후) — 수정 전에는 '전체 흐름을 훑어본다'가 detail_orientation과 크게 다르지 않아 보여 재검토함",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "전체 흐름이 자연스러운지 훑어본다", "after": "예전에 만들었던 것과 비슷하게 반복되는 편집 패턴이 있는지 확인한다",
    },
    ("detail_orientation_media_v1", "do_ask_feedback"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_media_v1", "do_visual_check"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_media_v1", "do_compare_ref"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- detail_orientation_school_life_v1 ---
    ("detail_orientation_school_life_v1", "do_check_conditions"): {
        "behavior_trait_match": "예 — '제출 조건 하나하나'로 세부 정확성을 직접 표현, planning(우선순위)과 구분됨",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_finish_first"): {
        "behavior_trait_match": "예 — persistence_completion과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_priority_pick"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_quick_submit"): {
        "behavior_trait_match": "예 — immediate_execution과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_ask_help"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- persistence_completion_game_v1 ---
    ("persistence_completion_game_v1", "pc_keep_going"): {
        "behavior_trait_match": "예(수정 후) — '목표는 그대로 두고 끝까지'만 표현, 방법 변경 언급을 제거해 change_adaptation과 분리",
        "adjacent_risk": "낮음(수정 후) — 수정 전 '방법을 바꿔가며'가 change_adaptation과 혼재돼 재검토함",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "포기하지 않고 방법을 바꿔가며 계속 도전한다", "after": "결과가 잘 안 나와도 그 목표는 그대로 두고 끝까지 시도를 이어간다",
    },
    ("persistence_completion_game_v1", "pc_analyze_fail"): {
        "behavior_trait_match": "예 — causal_analysis와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("persistence_completion_game_v1", "pc_take_break"): {
        "behavior_trait_match": "예(수정 후) — '목표 자체를 바꾼다'로 change_adaptation을 명확히 함",
        "adjacent_risk": "낮음(수정 후) — 수정 전 '잠깐 쉬었다 돌아온다'는 장기적으로 지속·완수로도 읽힐 수 있어 재검토함",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "잠깐 다른 걸 하다가 다시 돌아온다", "after": "그 목표 대신 지금 상황에 맞는 다른 목표로 바꾼다",
    },
    ("persistence_completion_game_v1", "pc_watch_others"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("persistence_completion_game_v1", "pc_ask_help"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- persistence_completion_school_life_v1 ---
    ("persistence_completion_school_life_v1", "pc_finish_through"): {
        "behavior_trait_match": "예 — '지루해도 끝까지 마무리'로 persistence_completion과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_plan_stage"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_detail_stage"): {
        "behavior_trait_match": "예 — detail_orientation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_creative_stage"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_team_stage"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- uncertainty_tolerance_game_v1 ---
    ("uncertainty_tolerance_game_v1", "ut_proceed_calm"): {
        "behavior_trait_match": "예(수정 후) — '몰라도 되는 상태를 그대로 받아들인다'로 감내(tolerance)를 직접 표현, 속도 언급 제거",
        "adjacent_risk": "낮음(수정 후) — 수정 전 '진행한다'는 immediate_execution과 속도 축에서 겹쳐 보여 재검토함",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "결과를 몰라도 크게 신경 쓰지 않고 진행한다", "after": "결과가 어떻게 나올지 몰라도 그 상태를 그대로 받아들이고 계속 진행한다",
    },
    ("uncertainty_tolerance_game_v1", "ut_try_now"): {
        "behavior_trait_match": "예(수정 후) — '정보가 충분히 모이기 전이라도 지금 바로'로 정보 충분성과 무관한 속도를 직접 표현",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "일단 빠르게 시도해본다", "after": "정보가 충분히 모이기 전이라도 일단 지금 바로 움직인다",
    },
    ("uncertainty_tolerance_game_v1", "ut_research_first"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_game_v1", "ut_ask_others"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_game_v1", "ut_plan_ahead"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- uncertainty_tolerance_school_life_v1 ---
    ("uncertainty_tolerance_school_life_v1", "ut_decide_now"): {
        "behavior_trait_match": "예 — '확실하지 않아도 불안해하지 않고'로 감내를 직접 표현",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_wait_more"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_ask_teacher"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_pick_safe"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_voice_concern"): {
        "behavior_trait_match": "예 — opinion_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- opinion_expression_media_v1 ---
    ("opinion_expression_media_v1", "oe_state_view"): {
        "behavior_trait_match": "예 — '내 생각을 먼저 분명하게 말한다'로 opinion_expression과 직접 일치",
        "adjacent_risk": "중간 — opinion_mediation과 같은 상황(의견 충돌)이라 2차 검토 시 함께 비교 필요",
        "desirability_bias": "낮음", "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_mediate"): {
        "behavior_trait_match": "예 — opinion_mediation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_gather_data"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_follow_majority"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_read_mood"): {
        "behavior_trait_match": "예 — emotional_interpretation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- opinion_expression_school_life_v1 (질문 전체 재작성) ---
    ("opinion_expression_school_life_v1", "oe_speak_role"): {
        "behavior_trait_match": "예(수정 후) — 역할 선호가 아니라 '내 생각을 먼저 말한다'는 실제 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "생각이 있으면 먼저 나서서 말하는 역할을 맡는다", "after": "내 생각을 먼저 분명하게 말한다",
    },
    ("opinion_expression_school_life_v1", "oe_listen_role"): {
        "behavior_trait_match": "예(수정 후) — emotional_interpretation과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "다른 사람 의견을 듣고 이해하는 역할을 맡는다", "after": "다른 사람이 왜 그렇게 생각하는지 먼저 들어본다",
    },
    ("opinion_expression_school_life_v1", "oe_organize_role"): {
        "behavior_trait_match": "예(수정 후) — planning과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "전체 진행을 정리하는 역할을 맡는다", "after": "전체 의견을 정리해서 다음 단계를 계획한다",
    },
    ("opinion_expression_school_life_v1", "oe_bridge_role"): {
        "behavior_trait_match": "예(수정 후) — opinion_mediation과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "의견을 조율하는 역할을 맡는다", "after": "서로 다른 의견을 절충할 지점을 찾는다",
    },
    ("opinion_expression_school_life_v1", "oe_support_role"): {
        "behavior_trait_match": "예(수정 후) — collaboration_preference와 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "정해진 방향에 맞춰 지원하는 역할을 맡는다", "after": "일단 다수가 정한 방향에 맞춘다",
    },
    # --- creative_ideation_media_v1 ---
    ("creative_ideation_media_v1", "ci_new_format"): {
        "behavior_trait_match": "예 — '새로운 구성·방식을 스스로 떠올려본다'로 매체 무관 발상을 직접 표현",
        "adjacent_risk": "낮음 — visual_expression(화면 꾸미기)과 구분됨", "desirability_bias": "낮음",
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_visual_first"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_research_trend"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_plan_steps"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_ask_team"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- creative_ideation_game_v1 ---
    ("creative_ideation_game_v1", "ci_invent_rule"): {
        "behavior_trait_match": "예(수정 후) — '여러 요소를 새롭게 엮어서'로 조합·생성 행동을 직접 표현, novelty_seeking(새것 선호)과 분리",
        "adjacent_risk": "낮음(수정 후) — 수정 전 '아무도 안 써본'은 novelty_seeking과 극단 표현이 겹쳐 재검토함. pattern_finding 옵션과 문두가 겹치던 문제도 재검토로 해소",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "아직 아무도 안 써본 새로운 규칙을 스스로 떠올려본다", "after": "여러 요소를 새롭게 엮어서 지금까지와 다른 방식을 스스로 만들어본다",
    },
    ("creative_ideation_game_v1", "ci_improve_existing"): {
        "behavior_trait_match": "예 — pattern_finding과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_test_it"): {
        "behavior_trait_match": "예 — immediate_execution과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_visual_design"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_get_feedback"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- independent_judgment_game_v1 ---
    ("independent_judgment_game_v1", "ij_own_call"): {
        "behavior_trait_match": "예 — '다른 사람 의견과 달라도 내가 판단한 방식대로'로 판단 주체를 직접 표현",
        "adjacent_risk": "낮음 — opinion_expression(표현 여부)과 구분됨(이건 판단의 주체를 묻지, 표현 여부를 묻지 않음)",
        "desirability_bias": "낮음", "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_follow_guide"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_ask_more"): {
        "behavior_trait_match": "예 — collaboration_preference와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_say_thoughts"): {
        "behavior_trait_match": "예 — opinion_expression과 직접 일치(판단이 아니라 '말한다'는 표현 행동)",
        "adjacent_risk": "중간 — Target(ij_own_call)과 같은 상황에서 나와 1차 검토 시 함께 비교 필요",
        "desirability_bias": "낮음", "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_stay_calm"): {
        "behavior_trait_match": "예 — uncertainty_tolerance와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    # --- independent_judgment_school_life_v1 (질문 전체 재작성) ---
    ("independent_judgment_school_life_v1", "ij_set_own_standard"): {
        "behavior_trait_match": "예(수정 후) — 역할 선호가 아니라 '스스로 판단한 기준으로 정한다'는 실제 판단 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "스스로 기준을 세워서 판단하고 진행하는 역할을 맡는다", "after": "스스로 판단한 기준으로 다음 행동을 정한다",
    },
    ("independent_judgment_school_life_v1", "ij_ask_clarify"): {
        "behavior_trait_match": "예(수정 후) — collaboration_preference와 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "먼저 다른 사람에게 물어보고 맞추는 역할을 맡는다", "after": "다른 사람에게 먼저 물어보고 기준을 맞춘다",
    },
    ("independent_judgment_school_life_v1", "ij_plan_role"): {
        "behavior_trait_match": "예(수정 후) — planning과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "전체 순서를 계획하는 역할을 맡는다", "after": "전체 일정과 순서부터 다시 계획한다",
    },
    ("independent_judgment_school_life_v1", "ij_speak_role"): {
        "behavior_trait_match": "예(수정 후) — opinion_expression과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "중간 — Target(ij_set_own_standard)과 같은 상황이라 1차 검토 시 함께 비교 필요",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "내 생각을 적극적으로 말하는 역할을 맡는다", "after": "내가 생각한 기준을 다른 사람들에게 먼저 말한다",
    },
    ("independent_judgment_school_life_v1", "ij_adapt_role"): {
        "behavior_trait_match": "예(수정 후) — change_adaptation과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "상황이 바뀌면 바로 맞춰서 조정하는 역할을 맡는다", "after": "상황이 바뀌면 그때그때 기준을 바꾼다",
    },
}

DEFAULT_NOTE = {
    "behavior_trait_match": "TBD", "adjacent_risk": "TBD", "desirability_bias": "TBD",
    "naturalness": "TBD", "before": "", "after": "",
}


def _rows() -> list[dict]:
    rows = []
    for bp in V2_DIRECT_PROBE_BLUEPRINTS:
        blueprint_id = bp.blueprint.blueprint_id
        context_id = bp.base_question.context
        frame_id = bp.base_question.frame_id
        question_text = bp.base_question.question_text
        for option in bp.base_question.options:
            note = _NOTES.get((blueprint_id, option.role_id), DEFAULT_NOTE)
            is_target = bp.trait_id in option.primary_trait_delta
            mapped_trait_id = next(iter(option.primary_trait_delta))
            auto_flags = worksheet_row_flags(bp, option)
            rows.append({
                "trait_id": bp.trait_id, "blueprint_id": blueprint_id, "context_id": context_id,
                "frame_id": frame_id, "question_text": question_text, "role_id": option.role_id,
                "option_text": option.text, "mapped_trait_id": mapped_trait_id,
                "is_target": "예" if is_target else "아니오",
                "behavior_trait_match": note["behavior_trait_match"],
                "adjacent_risk": note["adjacent_risk"],
                "desirability_bias": note["desirability_bias"],
                "naturalness": note["naturalness"],
                "before": note["before"] or "-", "after": note["after"] or "-",
                "auto_result": "; ".join(auto_flags) if auto_flags else "이상 없음",
                "review_1": "TBD", "review_2": "TBD", "final_status": "draft",
            })
    return rows


def _escape(value: str) -> str:
    return value.replace("|", "\\|")


def main() -> None:
    rows = _rows()
    header = [
        "trait_id", "blueprint_id", "context_id", "frame_id", "question_text", "role_id",
        "option_text", "mapped_trait_id", "target_option", "행동-Trait 직접 일치",
        "인접 Trait 혼동 위험", "사회적 바람직성 편향", "문장 자연스러움", "수정 전 문구",
        "수정 후 문구", "자동 검수 결과", "1차 사람 검토", "2차 사람 검토", "최종 상태",
    ]
    lines = [
        "# V2 Direct Probe Question Review Worksheet",
        "",
        "2026-08-23 Trait Ontology v2(2.1단계) §10. 14개 Blueprint × 5개 Option = "
        f"{len(rows)}행. '1차 사람 검토'/'2차 사람 검토'/'최종 상태'는 항상 TBD/draft다 — ",
        "A가 스스로 완료 처리하지 않는다. 나머지 판단 열은 A가 §7~§9에서 실제로 검토한",
        "내용을 데이터로 남긴 것이며, 사람 검토를 대신하지 않는다.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for row in rows:
        cells = [
            row["trait_id"], row["blueprint_id"], row["context_id"], row["frame_id"],
            _escape(row["question_text"]), row["role_id"], _escape(row["option_text"]),
            row["mapped_trait_id"], row["is_target"], row["behavior_trait_match"],
            row["adjacent_risk"], row["desirability_bias"], row["naturalness"],
            _escape(row["before"]), _escape(row["after"]), row["auto_result"],
            row["review_1"], row["review_2"], row["final_status"],
        ]
        lines.append("| " + " | ".join(cells) + " |")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
