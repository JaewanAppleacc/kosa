"""Vertical Slice Contrast Pair Registry — 설계안 §12-1, 초안 근거: outputs/trait_ontology_draft.md §3.

2인 교차검토 전 DRAFT다(다른 Vertical Slice 데이터와 동일 상태). Vertical Slice 12개 Trait
중 명시적 반대 쌍으로 설계된 건 planning ↔ immediate_execution 하나뿐이다 — CLAUDE.md
"독립 작업과 협업 선호처럼 동시에 존재할 수 있는 특성은 Contrast Pair로 만들지 않는다"에
따라 나머지 Trait들은 의도적으로 Contrast Pair가 없다.

role_id는 실제 코드의 두 소스에서 그대로 가져왔다(자리표시자 아님):
- Seed Question(vertical_slice_seed_questions.py): task_planning(school_life),
  quick_execution(game)
- Tail Option Blueprint(tail_option_blueprints.py): advance_planning
  (planning_and_execution_v1), direct_trial(problem_response_v1)

comparable_frame_ids=["new_tool"]는 "새로운 도구가 주어지면 어떻게 접근하는가?" Frame이다
(question_frames/frame_role_map.py) — "미리 계획을 세우는지 vs 바로 시도하는지"가 같은
상황에서 직접 대조되는 유일한 Frame이라 trait_ontology_draft.md §3이 이 Frame 하나만
지정했다. 다른 Frame(예: limited_time_priority)에서 나온 반대 Evidence는 "제한된 시간"이라는
다른 조건이 섞여 있어 곧바로 상충으로 볼 수 없다 — CONTEXT_DEPENDENT로 남는다.
"""

from __future__ import annotations

from src.schemas.evidence import ContrastDefinition

PLANNING_VS_EXECUTION = ContrastDefinition(
    contrast_id="planning_vs_execution",
    construct_id="approach_timing",
    positive_role_ids=["task_planning", "advance_planning"],
    opposite_role_ids=["quick_execution", "direct_trial"],
    comparable_frame_ids=["new_tool"],
    condition_scope="새로운 도구·과제가 주어진 상황",
    minimum_evidence_each_side=2,
    description="같은 '새로운 상황' 조건에서 미리 계획하는지 바로 시도하는지가 갈리는 경우",
)

VERTICAL_SLICE_CONTRAST_DEFINITIONS: list[ContrastDefinition] = [
    PLANNING_VS_EXECUTION,
]
