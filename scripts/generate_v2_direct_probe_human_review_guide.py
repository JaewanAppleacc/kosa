"""V2 Direct Probe Human Review Guide 생성 — 2026-08-23 Trait Ontology v2(2.2단계) §17.

70행짜리 Worksheet(`v2_direct_probe_question_review.md`)와 별도로, 사람 두 명이
빠르게 훑어보고 승인/수정/보류를 표시할 수 있는 요약 문서를 만든다. Trait별 정의·
인접 Trait와의 차이·질문 2개(각 5개 선택지, Mapping, NO_SIGNAL 이유)·검토자 확인
질문·체크란을 담는다. 체크란은 전부 미선택(TBD) 상태로 둔다 — 이 스크립트가 스스로
승인 처리하지 않는다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/generate_v2_direct_probe_human_review_guide.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT  # noqa: E402

OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / "outputs" / "reviews" / "v2_direct_probe_human_review_guide.md"
)

# trait_id -> (정의, 인접 Trait와의 차이, 검토자가 확인할 질문 2~3개)
_TRAIT_GUIDE: dict[str, dict[str, object]] = {
    "systems_thinking": {
        "definition": "어떤 요소 하나가 바뀌었을 때, 그 변화가 다른 요소·역할과 어떻게 서로 얽혀 영향을 "
        "주는지 살펴보는 성향. 원인 하나를 깊게 파는 것(causal_analysis)이 아니라 '여러 요소 사이의 "
        "관계'를 본다.",
        "adjacent": [
            "causal_analysis: '왜 이 일이 일어났는가'(원인 하나)에 집중 — systems_thinking은 '이 변화가 "
            "다른 곳에 어떤 영향을 주는가'(관계망)에 집중한다.",
            "planning: '앞으로 어떻게 할지 순서를 짠다'는 행동이지, 요소 간 영향 관계를 짚어보는 행동이 "
            "아니다.",
            "pattern_finding: '반복되는 규칙'을 찾는 행동이지, '지금 이 변화의 파급 효과'를 보는 행동이 "
            "아니다.",
        ],
        "reviewer_questions": [
            "Target 선택지가 '영향을 주고받는 관계'를 실제로 묻고 있는가, 아니면 단순히 '전체를 본다'는 "
            "막연한 표현에 그치는가?",
            "distractor 중 planning/causal_analysis로 매핑된 선택지가 실제로 systems_thinking으로도 "
            "읽힐 만큼 표현이 겹치지는 않는가?",
        ],
    },
    "detail_orientation": {
        "definition": "작은 오류·조건·차이까지 하나하나 확인하는 성향. '전체적으로 훑어본다'가 아니라 "
        "'세부 하나하나를 놓치지 않는다'는 행동으로 드러난다.",
        "adjacent": [
            "information_comparison: 여러 정보를 비교하는 행동이지, 하나의 결과물 안에서 세부 오류를 "
            "찾는 행동과는 다르다.",
            "planning: 우선순위를 정하는 행동이지, 세부 정확성을 확인하는 행동이 아니다.",
            "pattern_finding: '반복되는 패턴'을 찾는 것과 '세부 오류'를 찾는 것은 둘 다 '자세히 본다'는 "
            "인상을 주지만 목적이 다르다 — 전자는 규칙성, 후자는 정확성이다.",
        ],
        "reviewer_questions": [
            "Target 선택지가 '시간이 더 들어도'/'촉박해도' 같은 Trade-off를 포함해 무조건 좋은 답처럼 "
            "보이지 않는가?",
            "NO_SIGNAL로 바뀐 선택지(예: do_visual_check)가 정말 detail_orientation도 visual_expression도 "
            "아닌 애매한 확인 행동으로 읽히는가, 아니면 실제로는 다른 Trait가 강하게 느껴지는가?",
        ],
    },
    "persistence_completion": {
        "definition": "결과가 잘 안 나와도 같은 목표를 포기하지 않고 끝까지 이어가는 성향. '방법을 "
        "바꾼다'가 아니라 '목표 자체를 그대로 유지한 채 시도를 계속한다'는 행동이다.",
        "adjacent": [
            "planning: 계획을 세우는 행동과 그 계획을 끝까지 밀어붙이는 행동은 다르다.",
            "change_adaptation: persistence_completion의 반대 방향처럼 보일 수 있지만, 이 두 Trait를 "
            "직접 대립시키는 문항은 만들지 않는다(단순 목표 포기는 NO_SIGNAL로 처리했다).",
        ],
        "reviewer_questions": [
            "Target 선택지('결과가 잘 안 나오고... 시간이 늦어져도')가 여전히 자연스러운 한국어 문장으로 "
            "읽히는가, Trade-off 문구가 어색하게 붙지는 않았는가?",
            "pc_take_break(NO_SIGNAL)이 실제로 change_adaptation의 근거가 되기엔 약하다는 판단에 "
            "동의하는가?",
        ],
    },
    "uncertainty_tolerance": {
        "definition": "결과를 예측할 수 없는 상태 자체를 크게 불안해하지 않고 받아들이며 진행하는 성향. "
        "'일단 빠르게 시도한다'(속도, immediate_execution)와는 다른 축이다.",
        "adjacent": [
            "immediate_execution: '정보가 부족해도 빠르게 움직인다'는 속도의 문제이지, '결과를 몰라도 "
            "괜찮다'는 감내의 문제와는 다르다.",
            "change_adaptation: 상황이 바뀐 뒤 대응하는 행동이지, 애초에 불확실한 상태를 받아들이는 "
            "행동과는 다르다.",
        ],
        "reviewer_questions": [
            "ut_plan_ahead(재작성 후 '여러 경우를 미리 따져보고 계획을 세운다')가 순수한 planning 행동으로 "
            "읽히는가, 여전히 불확실성 회피처럼 읽히지는 않는가?",
            "ut_wait_more(NO_SIGNAL)이 실제로는 계획 행동(planning)에 더 가깝다고 보이지는 않는가?",
        ],
    },
    "opinion_expression": {
        "definition": "생각이 다를 때 자신의 의견을 분명하게 말로 표현하는 성향. '표현 여부'를 보는 것이지 "
        "'그 판단이 옳은가'를 보지 않는다.",
        "adjacent": [
            "opinion_mediation: 서로 다른 의견 사이에서 절충점을 찾는 행동이지, 자기 의견을 표명하는 "
            "행동과는 다르다.",
            "independent_judgment: '스스로 판단의 기준을 정하는가'를 보는 Trait이고, opinion_expression은 "
            "'그 생각을 실제로 말로 표현하는가'를 본다 — 판단과 표현은 별개다.",
        ],
        "reviewer_questions": [
            "Target 선택지에 추가한 Trade-off('분위기가 어색해질 수 있어도' 등)가 다른 선택지보다 지나치게 "
            "길거나 튀어 보이지 않는가?",
            "oe_follow_majority/oe_support_role(NO_SIGNAL)이 실제로는 collaboration_preference의 근거로 "
            "쓸 수 있다고 보이지는 않는가(단순 순응과 협업 선호의 경계 판단)?",
        ],
    },
    "creative_ideation": {
        "definition": "기존 요소들을 새롭게 조합하거나 새로운 아이디어를 스스로 만들어내는 성향. "
        "'새로운 것을 좋아한다'(novelty_seeking, 선호)가 아니라 '새로운 것을 만든다'(생성 행동)는 "
        "차이가 있다.",
        "adjacent": [
            "novelty_seeking: 새로운 것을 '선호'하는 태도이지, 직접 '만들어내는' 행동이 아니다 — 이번 "
            "라운드에서 Target 문구를 '조합·생성'으로 명확히 좁혔다.",
            "pattern_finding: 기존 규칙에서 반복을 찾아 다듬는 행동이지, 새로운 조합을 스스로 "
            "만들어내는 행동과는 다르다.",
        ],
        "reviewer_questions": [
            "ci_invent_rule Target 문구('여러 요소를 새롭게 엮어서')가 pattern_finding(ci_improve_existing, "
            "'반복되는 부분을 찾아 다듬는다')과 충분히 구분되는가?",
            "ci_get_feedback(NO_SIGNAL)이 실제로 collaboration_preference에 가깝다고 보이지는 않는가?",
        ],
    },
    "independent_judgment": {
        "definition": "지시나 다른 사람의 의견이 모호하거나 자신과 다를 때, 스스로 판단 기준을 세워 "
        "행동을 결정하는 성향. '의견을 말하는가'(opinion_expression)가 아니라 '누구의 판단을 따르는가'를 "
        "본다.",
        "adjacent": [
            "opinion_expression: 판단 기준을 세우는 것과 그 생각을 말로 표현하는 것은 다른 행동이다 — "
            "같은 상황에서 둘 다 나올 수 있어 2차 검토 시 특히 비교가 필요하다.",
            "collaboration_preference: 다른 사람에게 묻고 맞추는 행동은 판단의 주체가 자신이 아니라는 "
            "뜻이라 independent_judgment와 반대 방향에 가깝다 — 이번 라운드에 이런 선택지는 "
            "collaboration_preference로 억지로 매핑하지 않고 NO_SIGNAL로 처리했다.",
        ],
        "reviewer_questions": [
            "ij_own_call/ij_set_own_standard(Target)와 ij_say_thoughts/ij_speak_role(opinion_expression) "
            "이 실제로 다른 행동으로 구분돼 읽히는가?",
            "ij_ask_more/ij_ask_clarify(NO_SIGNAL)를 collaboration_preference로 되돌려야 한다고 보이는 "
            "지점이 있는가?",
        ],
    },
}

_TRAIT_LABELS = {
    "systems_thinking": "구조적 사고", "detail_orientation": "세부 주의",
    "persistence_completion": "지속·완수", "uncertainty_tolerance": "불확실성 감내",
    "opinion_expression": "의견 표명", "creative_ideation": "아이디어 발상",
    "independent_judgment": "독립적 판단",
}


def _question_block(bp) -> list[str]:
    lines = [
        f"**{bp.blueprint_id}** (Context: {bp.base_question.context}, Frame: {bp.question_frame_id})",
        "",
        f"> {bp.base_question.question_text}",
        "",
        "| role_id | 선택지 | Mapping | NO_SIGNAL 이유 |",
        "|---|---|---|---|",
    ]
    for option in bp.base_question.options:
        mapping = bp.mapping_by_role(option.role_id)
        is_target = mapping.mapping_type == "TRAIT_SIGNAL" and mapping.primary_trait_id == bp.trait_id
        mapping_label = (
            f"**TARGET({mapping.primary_trait_id})**" if is_target
            else f"{mapping.mapping_type}({mapping.primary_trait_id})" if mapping.mapping_type == "TRAIT_SIGNAL"
            else "NO_SIGNAL"
        )
        reason = mapping.no_signal_reason or "-"
        lines.append(f"| {option.role_id} | {option.text} | {mapping_label} | {reason} |")
    lines.append("")
    return lines


def main() -> None:
    lines = [
        "# V2 Direct Probe Human Review Guide",
        "",
        "2026-08-23 Trait Ontology v2(2.2단계) §17. 70행 Worksheet"
        "(`v2_direct_probe_question_review.md`)를 대신하지 않는다 — 그 Worksheet는 Option 단위로 더 "
        "세밀하게 검토할 때 쓰고, 이 문서는 Trait 단위로 빠르게 훑어보는 용도다. 아래 체크란은 전부 "
        "미선택(TBD) 상태다 — 팀원 두 명이 각자 검토한 뒤 표시해야 한다. 두 명 모두 승인한 문항만 "
        "`team_reviewed`로 승격하고, 그다음에만 v2 Career Profile 표시를 진행한다.",
        "",
    ]
    for trait_id, blueprints in V2_DIRECT_PROBE_BLUEPRINTS_BY_TRAIT.items():
        guide = _TRAIT_GUIDE[trait_id]
        lines.extend([
            f"## {trait_id} ({_TRAIT_LABELS[trait_id]})",
            "",
            f"**정의**: {guide['definition']}",
            "",
            "**인접 Trait와의 차이**:",
        ])
        for note in guide["adjacent"]:
            lines.append(f"- {note}")
        lines.append("")
        lines.append("**질문 2개**:")
        lines.append("")
        for bp in blueprints:
            lines.extend(_question_block(bp))
        lines.append("**검토자가 확인할 질문**:")
        for q in guide["reviewer_questions"]:
            lines.append(f"- {q}")
        lines.append("")
        lines.append("**승인/수정/보류 체크란** (각 Blueprint당 1행, 미선택):")
        lines.append("")
        lines.append("| blueprint_id | 1차 검토자 | 승인 | 수정 필요 | 보류 | 비고 |")
        lines.append("|---|---|---|---|---|---|")
        for bp in blueprints:
            lines.append(f"| {bp.blueprint_id} | TBD | ☐ | ☐ | ☐ | |")
        lines.append("")
        lines.append("| blueprint_id | 2차 검토자 | 승인 | 수정 필요 | 보류 | 비고 |")
        lines.append("|---|---|---|---|---|---|")
        for bp in blueprints:
            lines.append(f"| {bp.blueprint_id} | TBD | ☐ | ☐ | ☐ | |")
        lines.append("")
        lines.append("---")
        lines.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
