"""V2 Direct Probe Question Review Worksheet 생성 — 2026-08-23 Trait Ontology v2
(2.1단계 §10, 2.2단계 §15).

14개 Blueprint × 5개 Option = 70행을 담은 검수 Worksheet를 만든다. "행동-Trait 직접
일치 여부"/"인접 Trait 혼동 위험"/"사회적 바람직성 편향"/"Trade-off 균형"/"문장
자연스러움"·수정 전/후 문구는 A(작업자)가 §7~§9에서 실제로 검토한 판단을 코드에 데이터로
남긴 것이다 — 이 판단 자체는 사람 검토를 "대신"하지 않는다: "1차 사람 검토"/"2차 사람
검토"/"최종 상태"는 항상 TBD/draft로만 채운다(A가 스스로 완료 처리하지 않는다).

2.2단계 §15: mapping_type(TRAIT_SIGNAL/NO_SIGNAL)·no_signal_reason 열을 추가했다 —
70개 Option 중 14개는 이번 라운드에 "정보만 물어보는" 패턴 등 근거가 약한 매핑을
NO_SIGNAL로 바꿨다(mapped_trait_id는 그 14개 행에서 "-"다).

실행: PYTHONPATH=. ./.venv/bin/python scripts/generate_v2_direct_probe_question_review.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS  # noqa: E402
from src.engines.v2_direct_probe_quality_checks import worksheet_row_flags  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "reviews" / "v2_direct_probe_question_review.md"

_NO_TRADE_OFF = "해당 없음(Target Option 아님)"
_TARGET_NO_EDIT = "이번 라운드에 별도 Trade-off 문구를 추가하지 않음(2차 검토 시 필요 여부 확인)"

# (blueprint_id, role_id) -> 사람이 직접 남긴 검토 메모. 없는 조합은 아래 DEFAULT_NOTE를 쓴다.
# "before"/"after"가 채워진 항목은 §7~§9(2.1단계) 또는 §7~§9(2.2단계)에서 실제로 문구를
# 바꾼 자리다 — 가장 최근 라운드의 직전 문구를 before로, 최종 문구를 after로 남긴다.
_NOTES: dict[tuple[str, str], dict[str, str]] = {
    # --- systems_thinking_game_v1 ---
    ("systems_thinking_game_v1", "st_ripple_check"): {
        "behavior_trait_match": "예 — '다른 아이템·전략에 미치는 영향'을 직접 살펴보는 행동으로 요소 간 상호작용을 명시함",
        "adjacent_risk": "중간 — causal_analysis(원인 하나를 깊게 봄)와 구분되지만, '영향'이라는 단어가 causal과 겹쳐 보일 수 있어 2차 검토 필요",
        "desirability_bias": "낮음 — 다른 옵션도 각자 합리적인 행동으로 서술됨",
        "trade_off_balance": _TARGET_NO_EDIT,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_reason_first"): {
        "behavior_trait_match": "예 — causal_analysis(이유부터 생각)와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_try_it"): {
        "behavior_trait_match": "예 — immediate_execution과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_compare_items"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_game_v1", "st_ask_team"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '어떻게 쓸지 물어본다'는 정보 확인 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- systems_thinking_school_life_v1 ---
    ("systems_thinking_school_life_v1", "st_map_impact"): {
        "behavior_trait_match": "예 — '역할과 서로 얽혀 영향을 주는지'로 요소 간 상호작용을 명시, planning(일정 재조정)과 구분되게 수정함(2.1단계)",
        "adjacent_risk": "낮음(수정 후) — planning 옵션과 '전체를 다시 본다'는 표현이 겹치던 문제를 문구 수정으로 해소",
        "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("systems_thinking_school_life_v1", "st_replan"): {
        "behavior_trait_match": "예 — planning과 직접 일치, '일정·순서를 다시 짠다'는 스케줄링 행동으로만 한정",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_school_life_v1", "st_adapt_now"): {
        "behavior_trait_match": "예 — change_adaptation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_school_life_v1", "st_check_mood"): {
        "behavior_trait_match": "예 — emotional_interpretation과 직접 일치",
        "adjacent_risk": "낮음",
        "desirability_bias": "중간 — '친구 기분을 먼저 살핀다'가 배려로 읽혀 다른 선택지보다 약간 더 바람직해 보일 수 있음(참고용 표시)",
        "trade_off_balance": _NO_TRADE_OFF, "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("systems_thinking_school_life_v1", "st_state_view"): {
        "behavior_trait_match": "예 — opinion_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- detail_orientation_media_v1 ---
    ("detail_orientation_media_v1", "do_scan_errors"): {
        "behavior_trait_match": "예 — '오탈자·어긋난 부분까지 하나하나' 세부 정확성을 직접 표현",
        "adjacent_risk": "낮음 — information_comparison(비교)과 구분됨", "desirability_bias": "낮음",
        "trade_off_balance": "예(2.2단계 추가) — '시간이 더 들더라도'를 붙여 확인에 드는 비용을 명시함",
        "naturalness": "자연스러움",
        "before": "작은 오탈자나 어긋난 부분까지 하나하나 짚어본다",
        "after": "시간이 더 들더라도 작은 오탈자나 어긋난 부분까지 하나하나 짚어본다",
    },
    ("detail_orientation_media_v1", "do_overall_flow"): {
        "behavior_trait_match": "예(수정 후, 2.1단계) — '반복되는 편집 패턴'으로 pattern_finding의 핵심 행동(반복 규칙 탐색)을 명확히 함",
        "adjacent_risk": "낮음(수정 후) — 수정 전에는 '전체 흐름을 훑어본다'가 detail_orientation과 크게 다르지 않아 보여 재검토함",
        "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("detail_orientation_media_v1", "do_ask_feedback"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '보여주고 의견을 듣는다'는 반응 확인 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("detail_orientation_media_v1", "do_visual_check"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '화면 구성을 다시 살펴본다'는 확인 행동일 뿐, 새로운 시각 요소를 만들어내는 창작·표현 행동이라는 근거가 약함(과거 visual_expression 매핑은 억지 매핑이었음)",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("detail_orientation_media_v1", "do_compare_ref"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- detail_orientation_school_life_v1 ---
    ("detail_orientation_school_life_v1", "do_check_conditions"): {
        "behavior_trait_match": "예 — '제출 조건 하나하나'로 세부 정확성을 직접 표현, planning(우선순위)과 구분됨",
        "adjacent_risk": "낮음",
        "trade_off_balance": "예(2.2단계 추가) — '시간이 촉박해도'를 붙여 확인에 드는 비용을 명시함",
        "desirability_bias": "낮음", "naturalness": "자연스러움",
        "before": "제출 조건을 하나하나 놓치지 않았는지 세세히 확인한다",
        "after": "시간이 촉박해도 제출 조건을 하나하나 놓치지 않았는지 세세히 확인한다",
    },
    ("detail_orientation_school_life_v1", "do_finish_first"): {
        "behavior_trait_match": "예 — persistence_completion과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_priority_pick"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_quick_submit"): {
        "behavior_trait_match": "예 — immediate_execution과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("detail_orientation_school_life_v1", "do_ask_help"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '확인을 부탁한다'는 도움 요청 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- persistence_completion_game_v1 ---
    ("persistence_completion_game_v1", "pc_keep_going"): {
        "behavior_trait_match": "예(2.1단계 수정) — '목표는 그대로 두고 끝까지'만 표현, 방법 변경 언급을 제거해 change_adaptation과 분리",
        "adjacent_risk": "낮음(수정 후)",
        "trade_off_balance": "예(2.2단계 추가) — '다른 목표를 시작할 시간이 늦어져도'로 기회비용을 명시해 무조건 좋은 답처럼 보이지 않게 함",
        "desirability_bias": "낮음(2.2단계 Trade-off 추가로 완화)", "naturalness": "자연스러움",
        "before": "결과가 잘 안 나와도 그 목표는 그대로 두고 끝까지 시도를 이어간다",
        "after": "결과가 잘 안 나오고 다른 목표를 시작할 시간이 늦어져도, 지금 목표는 그대로 두고 끝까지 시도를 이어간다",
    },
    ("persistence_completion_game_v1", "pc_analyze_fail"): {
        "behavior_trait_match": "예 — causal_analysis와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("persistence_completion_game_v1", "pc_take_break"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '다른 목표로 바꾼다'는 단순한 목표 포기·교체이지, 상황에 맞춰 방식을 능동적으로 바꾸는 change_adaptation의 직접 근거로 보기엔 약함(2.1단계에는 change_adaptation으로 유지했었음)",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("persistence_completion_game_v1", "pc_watch_others"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("persistence_completion_game_v1", "pc_ask_help"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '도움을 요청한다'는 도움 요청 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- persistence_completion_school_life_v1 ---
    ("persistence_completion_school_life_v1", "pc_finish_through"): {
        "behavior_trait_match": "예 — '지루해도 끝까지 마무리'로 persistence_completion과 직접 일치",
        "adjacent_risk": "낮음",
        "trade_off_balance": "예(2.2단계 추가) — '다른 일에 쓸 시간이 줄어들어도'로 기회비용을 명시함",
        "desirability_bias": "낮음(2.2단계 Trade-off 추가로 완화)", "naturalness": "자연스러움",
        "before": "지루해도 끝까지 마무리하는 데 가장 오래 매달린다",
        "after": "다른 일에 쓸 시간이 줄어들어도, 지루한 과제를 끝까지 마무리하는 데 가장 오래 매달린다",
    },
    ("persistence_completion_school_life_v1", "pc_plan_stage"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_detail_stage"): {
        "behavior_trait_match": "예 — detail_orientation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_creative_stage"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치(적극적으로 꾸미는 창작 행동)",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("persistence_completion_school_life_v1", "pc_team_stage"): {
        "behavior_trait_match": "예(2.2단계 재확인) — '팀원과 역할을 맞춘다'는 역할 분담·조율이 드러나 협업 선호 근거가 강함(단순 질문형과 달리 유지)",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "팀원과 맞추는 데 가장 오래 매달린다", "after": "팀원과 역할을 맞추는 데 가장 오래 매달린다",
    },
    # --- uncertainty_tolerance_game_v1 ---
    ("uncertainty_tolerance_game_v1", "ut_proceed_calm"): {
        "behavior_trait_match": "예(2.1단계 수정) — '몰라도 되는 상태를 그대로 받아들인다'로 감내(tolerance)를 직접 표현, 속도 언급 제거",
        "adjacent_risk": "낮음(수정 후) — 수정 전 '진행한다'는 immediate_execution과 속도 축에서 겹쳐 보여 재검토함",
        "desirability_bias": "낮음", "trade_off_balance": _TARGET_NO_EDIT, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("uncertainty_tolerance_game_v1", "ut_try_now"): {
        "behavior_trait_match": "예(2.1단계 수정) — '정보가 충분히 모이기 전이라도 지금 바로'로 정보 충분성과 무관한 속도를 직접 표현",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_game_v1", "ut_research_first"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_game_v1", "ut_ask_others"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '의견을 먼저 들어본다'는 의견 확인 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_game_v1", "ut_plan_ahead"): {
        "behavior_trait_match": "예(2.2단계 재작성) — '여러 경우를 미리 따져보고 계획을 세운다'로 순수 계획 행동만 남김. 이전 문구('예상할 수 있는 익숙한 방법')는 불확실성 회피 프레이밍이 섞여 있어 uncertainty_tolerance에 대한 암묵적 반대 근거로 읽힐 위험이 있었음",
        "adjacent_risk": "낮음(재작성 후) — planning 고유 행동만 남음", "desirability_bias": "낮음",
        "trade_off_balance": _NO_TRADE_OFF, "naturalness": "자연스러움",
        "before": "결과를 예상할 수 있는 익숙한 방법을 미리 계획해서 고른다",
        "after": "선택하기 전에 여러 경우를 미리 따져보고 계획을 세운다",
    },
    # --- uncertainty_tolerance_school_life_v1 ---
    ("uncertainty_tolerance_school_life_v1", "ut_decide_now"): {
        "behavior_trait_match": "예 — '확실하지 않아도 불안해하지 않고'로 감내를 직접 표현",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _TARGET_NO_EDIT,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_wait_more"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '결정을 미룬다'는 유보 행동일 뿐, 일정을 짜거나 순서를 정하는 실제 계획 행동이 드러나지 않아 planning의 직접 근거로 보기 어려움(2.1단계에는 planning으로 유지했었음)",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_ask_teacher"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '먼저 물어본다'는 정보 확인 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_pick_safe"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("uncertainty_tolerance_school_life_v1", "ut_voice_concern"): {
        "behavior_trait_match": "예 — opinion_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- opinion_expression_media_v1 ---
    ("opinion_expression_media_v1", "oe_state_view"): {
        "behavior_trait_match": "예 — '내 생각을 먼저 분명하게 말한다'로 opinion_expression과 직접 일치",
        "adjacent_risk": "중간 — opinion_mediation과 같은 상황(의견 충돌)이라 2차 검토 시 함께 비교 필요",
        "trade_off_balance": "예(2.2단계 추가) — '분위기가 어색해질 수 있어도'로 사회적 비용을 명시함",
        "desirability_bias": "낮음(2.2단계 Trade-off 추가로 완화)", "naturalness": "자연스러움",
        "before": "내 생각을 먼저 분명하게 말한다", "after": "분위기가 어색해질 수 있어도 내 생각을 먼저 분명하게 말한다",
    },
    ("opinion_expression_media_v1", "oe_mediate"): {
        "behavior_trait_match": "예 — opinion_mediation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_gather_data"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_follow_majority"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '다수가 원하는 방향을 따른다'는 순응·갈등 회피일 수 있어 협업 선호의 직접 근거로 보기 어려움",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_media_v1", "oe_read_mood"): {
        "behavior_trait_match": "예 — emotional_interpretation과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- opinion_expression_school_life_v1 ---
    ("opinion_expression_school_life_v1", "oe_speak_role"): {
        "behavior_trait_match": "예 — '내 생각을 먼저 말한다'는 실제 행동으로 opinion_expression과 직접 일치(2.1단계에 역할 선호형에서 재작성함)",
        "adjacent_risk": "낮음",
        "trade_off_balance": "예(2.2단계 추가) — '다른 사람들 반응이 걱정되더라도'로 사회적 비용을 명시함",
        "desirability_bias": "낮음(2.2단계 Trade-off 추가로 완화)", "naturalness": "자연스러움",
        "before": "내 생각을 먼저 분명하게 말한다", "after": "다른 사람들 반응이 걱정되더라도 내 생각을 먼저 분명하게 말한다",
    },
    ("opinion_expression_school_life_v1", "oe_listen_role"): {
        "behavior_trait_match": "예(2.1단계 재작성) — emotional_interpretation과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_school_life_v1", "oe_organize_role"): {
        "behavior_trait_match": "예(2.1단계 재작성) — planning과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_school_life_v1", "oe_bridge_role"): {
        "behavior_trait_match": "예(2.1단계 재작성) — opinion_mediation과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("opinion_expression_school_life_v1", "oe_support_role"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '다수가 정한 방향에 맞춘다'는 순응일 수 있어 협업 선호의 직접 근거로 보기 어려움(2.1단계에는 collaboration_preference로 유지했었음)",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- creative_ideation_media_v1 ---
    ("creative_ideation_media_v1", "ci_new_format"): {
        "behavior_trait_match": "예 — '새로운 구성·방식을 스스로 떠올려본다'로 매체 무관 발상을 직접 표현",
        "adjacent_risk": "낮음 — visual_expression(화면 꾸미기)과 구분됨", "desirability_bias": "낮음",
        "trade_off_balance": _TARGET_NO_EDIT, "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_visual_first"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_research_trend"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_plan_steps"): {
        "behavior_trait_match": "예 — planning과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_media_v1", "ci_ask_team"): {
        "behavior_trait_match": "예(2.2단계 재확인) — '아이디어를 같이 나눈다'는 공동 발상 행동이 드러나 협업 선호 근거가 강함(단순 질문형과 달리 유지)",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- creative_ideation_game_v1 ---
    ("creative_ideation_game_v1", "ci_invent_rule"): {
        "behavior_trait_match": "예(2.1단계 수정) — '여러 요소를 새롭게 엮어서'로 조합·생성 행동을 직접 표현, novelty_seeking(새것 선호)과 분리",
        "adjacent_risk": "낮음(수정 후) — 수정 전 '아무도 안 써본'은 novelty_seeking과 극단 표현이 겹쳐 재검토함. pattern_finding 옵션과 문두가 겹치던 문제도 재검토로 해소",
        "desirability_bias": "낮음", "trade_off_balance": _TARGET_NO_EDIT, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_improve_existing"): {
        "behavior_trait_match": "예 — pattern_finding과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_test_it"): {
        "behavior_trait_match": "예 — immediate_execution과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_visual_design"): {
        "behavior_trait_match": "예 — visual_expression과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("creative_ideation_game_v1", "ci_get_feedback"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '아이디어를 먼저 물어본다'는 의견 확인 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- independent_judgment_game_v1 ---
    ("independent_judgment_game_v1", "ij_own_call"): {
        "behavior_trait_match": "예 — '다른 사람 의견과 달라도 내가 판단한 방식대로'로 판단 주체를 직접 표현",
        "adjacent_risk": "낮음 — opinion_expression(표현 여부)과 구분됨(이건 판단의 주체를 묻지, 표현 여부를 묻지 않음)",
        "desirability_bias": "낮음", "trade_off_balance": _TARGET_NO_EDIT, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_follow_guide"): {
        "behavior_trait_match": "예 — information_comparison과 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_ask_more"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '다른 사람들에게 더 물어본다'는 정보 확인 행동이지, 역할을 나눠 함께 해결하는 협업 행동이라는 근거가 약함",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_say_thoughts"): {
        "behavior_trait_match": "예 — opinion_expression과 직접 일치(판단이 아니라 '말한다'는 표현 행동)",
        "adjacent_risk": "중간 — Target(ij_own_call)과 같은 상황에서 나와 1차 검토 시 함께 비교 필요",
        "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("independent_judgment_game_v1", "ij_stay_calm"): {
        "behavior_trait_match": "예 — uncertainty_tolerance와 직접 일치",
        "adjacent_risk": "낮음", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    # --- independent_judgment_school_life_v1 ---
    ("independent_judgment_school_life_v1", "ij_set_own_standard"): {
        "behavior_trait_match": "예(2.1단계 재작성) — '스스로 판단한 기준으로 정한다'는 실제 판단 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _TARGET_NO_EDIT,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_school_life_v1", "ij_ask_clarify"): {
        "behavior_trait_match": "NO_SIGNAL(2.2단계 재검토) — '먼저 물어보고 기준을 맞춘다'는 확인 행동이지, 협업 선호가 직접 드러난다고 보기는 어려움(2.1단계에는 collaboration_preference로 유지했었음)",
        "adjacent_risk": "해당 없음(NO_SIGNAL)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_school_life_v1", "ij_plan_role"): {
        "behavior_trait_match": "예(2.1단계 재작성) — planning과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
    ("independent_judgment_school_life_v1", "ij_speak_role"): {
        "behavior_trait_match": "예(2.1단계 재작성) — opinion_expression과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "중간 — Target(ij_set_own_standard)과 같은 상황이라 1차 검토 시 함께 비교 필요",
        "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF, "naturalness": "자연스러움",
        "before": "", "after": "",
    },
    ("independent_judgment_school_life_v1", "ij_adapt_role"): {
        "behavior_trait_match": "예(2.1단계 재작성) — change_adaptation과 직접 일치하는 행동으로 재작성",
        "adjacent_risk": "낮음(수정 후)", "desirability_bias": "낮음", "trade_off_balance": _NO_TRADE_OFF,
        "naturalness": "자연스러움", "before": "", "after": "",
    },
}

DEFAULT_NOTE = {
    "behavior_trait_match": "TBD", "adjacent_risk": "TBD", "desirability_bias": "TBD",
    "trade_off_balance": "TBD", "naturalness": "TBD", "before": "", "after": "",
}


def _rows() -> list[dict]:
    rows = []
    for bp in V2_DIRECT_PROBE_BLUEPRINTS:
        blueprint_id = bp.blueprint_id
        context_id = bp.base_question.context
        frame_id = bp.base_question.frame_id
        question_text = bp.base_question.question_text
        for option in bp.base_question.options:
            mapping = bp.mapping_by_role(option.role_id)
            note = _NOTES.get((blueprint_id, option.role_id), DEFAULT_NOTE)
            is_target = mapping.mapping_type == "TRAIT_SIGNAL" and mapping.primary_trait_id == bp.trait_id
            auto_flags = worksheet_row_flags(bp, option)
            rows.append({
                "trait_id": bp.trait_id, "blueprint_id": blueprint_id, "context_id": context_id,
                "frame_id": frame_id, "question_text": question_text, "role_id": option.role_id,
                "option_text": option.text,
                "mapping_type": mapping.mapping_type,
                "mapped_trait_id": mapping.primary_trait_id or "-",
                "no_signal_reason": mapping.no_signal_reason or "-",
                "is_target": "예" if is_target else "아니오",
                "behavior_trait_match": note["behavior_trait_match"],
                "adjacent_risk": note["adjacent_risk"],
                "desirability_bias": note["desirability_bias"],
                "trade_off_balance": note.get("trade_off_balance", "TBD"),
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
        "option_text", "mapping_type", "mapped_trait_id", "no_signal_reason", "target_option",
        "행동-Trait 직접 일치", "인접 Trait 혼동 위험", "사회적 바람직성 편향", "Trade-off 균형",
        "문장 자연스러움", "수정 전 문구", "수정 후 문구", "자동 검수 결과",
        "1차 사람 검토", "2차 사람 검토", "최종 상태",
    ]
    no_signal_count = sum(1 for r in rows if r["mapping_type"] == "NO_SIGNAL")
    lines = [
        "# V2 Direct Probe Question Review Worksheet",
        "",
        "2026-08-23 Trait Ontology v2(2.1단계 §10, 2.2단계 §15). 14개 Blueprint × 5개 "
        f"Option = {len(rows)}행(그중 NO_SIGNAL {no_signal_count}행). '1차 사람 검토'/'2차 사람 "
        "검토'/'최종 상태'는 항상 TBD/draft다 — A가 스스로 완료 처리하지 않는다. 나머지 판단 "
        "열은 A가 §7~§9에서 실제로 검토한 내용을 데이터로 남긴 것이며, 사람 검토를 대신하지 "
        "않는다. NO_SIGNAL 행은 '이 선택지는 이번 질문에서 특정 Core Trait를 직접 확인할 만큼 "
        "근거가 명확하지 않다'는 뜻일 뿐 Target Trait가 낮다거나 반대 Trait가 강하다는 뜻이 "
        "아니다.",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "---|" * len(header),
    ]
    for row in rows:
        cells = [
            row["trait_id"], row["blueprint_id"], row["context_id"], row["frame_id"],
            _escape(row["question_text"]), row["role_id"], _escape(row["option_text"]),
            row["mapping_type"], row["mapped_trait_id"], _escape(row["no_signal_reason"]),
            row["is_target"], row["behavior_trait_match"], row["adjacent_risk"],
            row["desirability_bias"], row["trade_off_balance"], row["naturalness"],
            _escape(row["before"]), _escape(row["after"]), row["auto_result"],
            row["review_1"], row["review_2"], row["final_status"],
        ]
        lines.append("| " + " | ".join(cells) + " |")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH} ({len(rows)} rows, {no_signal_count} NO_SIGNAL)")


if __name__ == "__main__":
    main()
