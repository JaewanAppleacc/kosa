"""비핵심 Context 10개의 Seed Question·Option Blueprint 초안 (작업자 C 소유).

C 지시서 §3: "A가 담당하는 핵심 Context 5개를 제외한 나머지 Context의 Seed Question과
Option Blueprint 초안을 작성한다."

핵심 5개(game / media / school_life / business / making)는 A 소유라 여기서 만들지 않는다.
이 경계는 문서가 아니라 검사로 강제한다 — 핵심 Context가 들어오면 아래 `CORE_CONTEXT_IDS`
검사에서 바로 멈춘다.

작성한 초안은 `src/data/`(A의 확정 데이터)를 건드리지 않고
`data/drafts/question_blueprints/<context_id>.json`에 둔다. 각 파일은 A의
`SeedQuestion` Schema로 만들어져 §9-1 Lint(선택지 5개, Role ID 중복 금지, 한 문항에 같은
Trait 중복 배정 금지, trait_delta는 전부 1)를 통과한 상태로 저장된다.

Trait 배정 근거와 작성자는 `trait_rationale` / `draft_entry.author_id`에 남긴다
(지시서 §3 "Question-Trait Mapping에 근거와 작성자를 기록한다").

실행:
    python scripts/career_build_question_blueprints.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS  # noqa: E402
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.ids import generate_option_id, generate_question_id  # noqa: E402
from src.schemas.question import SeedOption, SeedQuestion, seed_question_to_blueprint  # noqa: E402
from src.schemas.review import DraftEntry, DraftReviewStage  # noqa: E402

OUT_DIR = ROOT / "data" / "drafts" / "question_blueprints"
AUTHOR_ID = "worker_c"
AS_OF = date(2026, 8, 21)
SOURCE_URL = None  # 창작 문항이라 외부 출처가 없다. 근거는 Context Definition Table이다.

CORE_CONTEXT_IDS = {c.context_id for c in CONTEXT_DEFINITIONS if c.is_core}
KNOWN_TRAIT_IDS = {t.trait_id for t in VERTICAL_SLICE_TRAITS}

# context_id -> (질문 문구, [(role_id, 선택지 문구, trait_id, next_probe, preferred_frames)])
QUESTIONS: dict[str, tuple[str, list[tuple[str, str, str, str, list[str]]]]] = {
    "volunteer": (
        "봉사나 사회참여 활동을 할 때, 어떤 순간이 가장 기억에 남나요?",
        [
            ("teamwork_with_others", "여러 사람과 역할을 나눠 같이 해낼 때", "collaboration_preference",
             "함께 하는 활동에서 어떤 역할을 맡을 때 편한지 확인", ["team_role", "conflicting_opinions"]),
            ("reading_others_need", "도움받는 사람이 실제로 뭘 필요로 하는지 알아챌 때", "emotional_interpretation",
             "상대의 상태를 어떻게 읽는지 구체적 상황으로 확인", ["others_reaction", "team_role"]),
            ("activity_planning", "활동 순서와 준비물을 미리 짜 두고 그대로 돌아갈 때", "planning",
             "제한된 시간에 무엇을 먼저 잡는지 확인", ["limited_time_priority", "first_action"]),
            ("just_start_helping", "복잡하게 생각하지 않고 일단 몸으로 돕기 시작할 때", "immediate_execution",
             "먼저 움직이는 편인지, 준비를 먼저 하는 편인지 확인", ["first_action", "unexpected_result"]),
            ("settling_disagreement", "의견이 갈릴 때 서로 받아들일 만한 선을 찾아낼 때", "opinion_mediation",
             "충돌 상황에서 무엇을 기준으로 정하는지 확인", ["conflicting_opinions", "others_reaction"]),
        ],
    ),
    "sports": (
        "운동을 하거나 경기를 볼 때, 어떤 쪽에 더 관심이 가나요?",
        [
            ("reading_the_game", "반복되는 흐름이나 팀의 패턴을 찾아내는 것", "pattern_finding",
             "여러 경기를 비교해 규칙을 찾는 편인지 확인", ["longest_focus", "problem_check"]),
            ("body_first", "일단 몸으로 부딪혀 보면서 감을 잡는 것", "immediate_execution",
             "새로운 종목을 만났을 때 먼저 하는 행동 확인", ["first_action", "new_tool"]),
            ("playing_together", "팀원과 호흡을 맞춰 같이 만들어 가는 것", "collaboration_preference",
             "팀에서 맡고 싶은 역할 확인", ["team_role", "conflicting_opinions"]),
            ("why_we_lost", "진 경기에서 무엇 때문에 그렇게 됐는지 짚어보는 것", "causal_analysis",
             "결과가 나빴을 때 무엇부터 확인하는지 확인", ["problem_check", "unexpected_result"]),
            ("switching_tactics", "상대가 달라지면 전술을 바꿔 맞추는 것", "change_adaptation",
             "상황이 바뀔 때 어떻게 대응하는지 확인", ["unexpected_result", "new_tool"]),
        ],
    ),
    "science": (
        "과학 실험이나 관찰 활동에서 가장 재미있는 부분은 무엇인가요?",
        [
            ("finding_the_cause", "왜 그런 결과가 나왔는지 원인을 밝히는 것", "causal_analysis",
             "예상과 다른 결과가 나왔을 때의 행동 확인", ["problem_check", "unexpected_result"]),
            ("spotting_regularity", "여러 번 관찰한 자료에서 규칙을 찾아내는 것", "pattern_finding",
             "자료를 어떻게 정리하는지 확인", ["longest_focus", "problem_check"]),
            ("handling_equipment", "실험 기구나 장비를 직접 다루는 것", "tool_utilization",
             "새 장비를 만났을 때 접근 방식 확인", ["new_tool", "first_action"]),
            ("checking_sources", "자료를 여러 곳에서 찾아 비교해 보는 것", "information_comparison",
             "정보가 엇갈릴 때 무엇을 믿는지 확인", ["limited_time_priority", "conflicting_opinions"]),
            ("designing_procedure", "실험 절차를 미리 설계해 두는 것", "planning",
             "시간이 부족할 때 절차를 어떻게 줄이는지 확인", ["limited_time_priority", "first_action"]),
        ],
    ),
    "writing": (
        "글을 읽거나 쓸 때, 어떤 작업에 가장 오래 머무르게 되나요?",
        [
            ("cross_reading", "같은 주제를 다룬 다른 글들과 견줘 보는 것", "information_comparison",
             "자료가 서로 다를 때 무엇을 기준으로 고르는지 확인", ["limited_time_priority", "conflicting_opinions"]),
            ("imagining_reader", "읽는 사람이 어떻게 받아들일지 떠올려 보는 것", "audience_response_prediction",
             "반응이 예상과 다를 때의 행동 확인", ["others_reaction", "unexpected_result"]),
            ("character_feeling", "인물의 감정선이 왜 그렇게 흐르는지 따라가는 것", "emotional_interpretation",
             "타인의 감정을 어떻게 읽는지 확인", ["others_reaction", "team_role"]),
            ("argument_structure", "주장이 어떤 근거에서 나왔는지 구조를 뜯어보는 것", "causal_analysis",
             "근거가 부실할 때 무엇부터 확인하는지 확인", ["problem_check", "longest_focus"]),
            ("outline_first", "쓰기 전에 전체 얼개를 먼저 잡아 두는 것", "planning",
             "마감이 촉박할 때 무엇을 먼저 하는지 확인", ["limited_time_priority", "first_action"]),
        ],
    ),
    "art_design": (
        "그림을 그리거나 무언가를 꾸밀 때, 어떤 순간이 가장 즐거운가요?",
        [
            ("visual_making", "머릿속 이미지를 눈에 보이게 만들어 낼 때", "visual_expression",
             "표현 방식을 고를 때 무엇을 먼저 정하는지 확인", ["first_action", "longest_focus"]),
            ("viewer_reaction", "보는 사람이 어떻게 느낄지 맞춰 볼 때", "audience_response_prediction",
             "반응이 갈릴 때의 행동 확인", ["others_reaction", "unexpected_result"]),
            ("trying_materials", "새로운 재료나 프로그램을 써 볼 때", "tool_utilization",
             "낯선 도구를 다루는 방식 확인", ["new_tool", "first_action"]),
            ("reworking", "처음 방향이 안 맞으면 방식을 바꿔 다시 잡을 때", "change_adaptation",
             "중간에 방향을 바꾸는 기준 확인", ["unexpected_result", "new_tool"]),
            ("scheduling_work", "완성까지 단계를 나눠 계획대로 진행할 때", "planning",
             "제한된 시간에 무엇을 남기는지 확인", ["limited_time_priority", "first_action"]),
        ],
    ),
    "travel": (
        "여행이나 답사를 준비할 때, 어떤 부분에 가장 공을 들이나요?",
        [
            ("route_planning", "동선과 일정을 미리 촘촘히 짜 두는 것", "planning",
             "일정이 어긋났을 때의 대응 확인", ["limited_time_priority", "unexpected_result"]),
            ("comparing_options", "여러 후보지를 찾아 비교해 고르는 것", "information_comparison",
             "정보가 엇갈릴 때의 판단 기준 확인", ["conflicting_opinions", "limited_time_priority"]),
            ("rolling_with_it", "계획이 틀어져도 그 자리에서 바꿔 가는 것", "change_adaptation",
             "예상 밖 상황에서의 행동 확인", ["unexpected_result", "new_tool"]),
            ("meeting_people", "현지 사람들의 생활과 분위기를 느껴 보는 것", "emotional_interpretation",
             "낯선 사람과의 상호작용 방식 확인", ["others_reaction", "team_role"]),
            ("just_go", "많이 알아보지 않고 일단 가서 부딪히는 것", "immediate_execution",
             "준비 없이 시작할 때 먼저 하는 일 확인", ["first_action", "problem_check"]),
        ],
    ),
    "cooking": (
        "요리를 할 때, 어떤 과정이 가장 재미있나요?",
        [
            ("handling_tools", "칼질이나 조리 기구를 다루는 과정", "tool_utilization",
             "새 조리 도구를 만났을 때의 접근 확인", ["new_tool", "longest_focus"]),
            ("cook_right_away", "레시피를 끝까지 안 보고 일단 시작하는 것", "immediate_execution",
             "중간에 막혔을 때의 행동 확인", ["first_action", "problem_check"]),
            ("recipe_patterns", "여러 레시피에서 공통되는 원리를 찾아내는 것", "pattern_finding",
             "규칙을 어떻게 정리하는지 확인", ["longest_focus", "problem_check"]),
            ("guest_taste", "먹는 사람 입맛에 맞을지 미리 가늠해 보는 것", "audience_response_prediction",
             "반응이 예상과 달랐을 때의 행동 확인", ["others_reaction", "unexpected_result"]),
            ("prep_order", "재료 손질 순서와 시간을 미리 배분하는 것", "planning",
             "시간이 모자랄 때 무엇을 줄이는지 확인", ["limited_time_priority", "first_action"]),
        ],
    ),
    "fashion_beauty": (
        "옷차림이나 스타일을 정할 때, 어떤 쪽에 더 신경이 쓰이나요?",
        [
            ("styling_myself", "색과 형태를 조합해 보이는 결과를 만드는 것", "visual_expression",
             "조합을 정할 때 먼저 보는 기준 확인", ["first_action", "longest_focus"]),
            ("how_others_see", "다른 사람 눈에 어떻게 비칠지 가늠하는 것", "audience_response_prediction",
             "반응이 갈릴 때의 행동 확인", ["others_reaction", "unexpected_result"]),
            ("trend_checking", "여러 스타일을 찾아보고 견줘 보는 것", "information_comparison",
             "정보가 많을 때 고르는 기준 확인", ["limited_time_priority", "conflicting_opinions"]),
            ("switching_style", "상황이나 계절이 바뀌면 방식을 바꾸는 것", "change_adaptation",
             "조건이 달라졌을 때의 대응 확인", ["unexpected_result", "new_tool"]),
            ("styling_with_friends", "친구와 서로 봐 주며 같이 정하는 것", "collaboration_preference",
             "같이 정할 때 맡는 역할 확인", ["team_role", "conflicting_opinions"]),
        ],
    ),
    "history_humanities": (
        "역사나 인문학 주제를 볼 때, 어떤 질문이 먼저 떠오르나요?",
        [
            ("why_it_happened", "그 일이 왜 그렇게 흘러갔는지", "causal_analysis",
             "설명이 엇갈릴 때 무엇부터 확인하는지 확인", ["problem_check", "conflicting_opinions"]),
            ("comparing_records", "다른 기록은 뭐라고 하는지", "information_comparison",
             "자료가 상충할 때의 판단 기준 확인", ["conflicting_opinions", "limited_time_priority"]),
            ("recurring_patterns", "비슷한 일이 다른 시대에도 있었는지", "pattern_finding",
             "사례를 어떻게 묶는지 확인", ["longest_focus", "problem_check"]),
            ("people_of_the_time", "그때 사람들은 어떤 심정이었는지", "emotional_interpretation",
             "타인의 입장을 어떻게 추론하는지 확인", ["others_reaction", "team_role"]),
            ("both_sides", "대립하던 양쪽 주장을 어떻게 조율했는지", "opinion_mediation",
             "충돌 상황의 판단 기준 확인", ["conflicting_opinions", "others_reaction"]),
        ],
    ),
    "law_politics": (
        "사회 이슈나 시사 문제를 볼 때, 무엇을 먼저 하게 되나요?",
        [
            ("tracing_cause", "문제가 생긴 원인을 따져 본다", "causal_analysis",
             "원인이 여러 개일 때 무엇부터 보는지 확인", ["problem_check", "longest_focus"]),
            ("finding_middle", "대립하는 주장 사이에서 접점을 찾아본다", "opinion_mediation",
             "합의가 안 될 때의 기준 확인", ["conflicting_opinions", "others_reaction"]),
            ("checking_facts", "여러 매체의 보도를 찾아 견줘 본다", "information_comparison",
             "보도가 엇갈릴 때의 판단 기준 확인", ["conflicting_opinions", "limited_time_priority"]),
            ("discussing_it", "친구들과 이야기하며 생각을 정리한다", "collaboration_preference",
             "토론에서 맡는 역할 확인", ["team_role", "conflicting_opinions"]),
            ("watching_it_shift", "상황이 어떻게 바뀌는지 계속 지켜본다", "change_adaptation",
             "국면이 바뀔 때의 대응 확인", ["unexpected_result", "new_tool"]),
        ],
    ),
}

TRAIT_RATIONALE_NOTE = (
    "각 선택지는 Trait Definition의 positive_indicators에 해당하는 행동 하나만 담도록 "
    "썼다. 한 선택지가 두 Trait를 동시에 가리키면 어느 쪽 근거인지 사후에 가릴 수 없다."
)


def build() -> list[SeedQuestion]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    context_by_id = {c.context_id: c for c in CONTEXT_DEFINITIONS}
    questions: list[SeedQuestion] = []

    for context_id, (question_text, rows) in QUESTIONS.items():
        if context_id in CORE_CONTEXT_IDS:
            raise SystemExit(
                f"{context_id}는 핵심 Context라 A 소유다 — C 초안에 넣지 않는다 (A 지시서 §4)"
            )
        if context_id not in context_by_id:
            raise SystemExit(f"Context Definition에 없는 context_id: {context_id}")

        question_id = generate_question_id(context_id, "seed", 1)
        options: list[SeedOption] = []
        for index, (role_id, text, trait_id, next_probe, frames) in enumerate(rows, start=1):
            if trait_id not in KNOWN_TRAIT_IDS:
                raise SystemExit(f"{context_id}: Ontology에 없는 trait_id {trait_id}")
            options.append(
                SeedOption(
                    option_id=generate_option_id(question_id, index),
                    text=text,
                    role_id=role_id,
                    primary_trait_delta={trait_id: 1},
                    next_probe=next_probe,
                    preferred_frames=frames,
                )
            )

        # SeedQuestion 생성 자체가 §9-1 Lint다 — 5개/Role 중복/Trait 중복을 여기서 검사한다.
        question = SeedQuestion(
            question_id=question_id,
            context=context_id,
            question_text=question_text,
            options=options,
        )
        questions.append(question)

        entry = DraftEntry(
            draft_id=f"question_blueprint_{question_id}",
            draft_type="question_blueprint",
            author_id=AUTHOR_ID,
            review_stage=DraftReviewStage.DRAFT,
            source_url=SOURCE_URL,
            as_of_date=AS_OF,
            notes=TRAIT_RATIONALE_NOTE,
        )
        payload = {
            "draft_entry": json.loads(entry.model_dump_json()),
            "context_id": context_id,
            "context_label": context_by_id[context_id].label,
            "seed_question": json.loads(question.model_dump_json()),
            "option_blueprint": json.loads(seed_question_to_blueprint(question).model_dump_json()),
            "trait_rationale": {
                option.role_id: {
                    "trait_id": next(iter(option.primary_trait_delta)),
                    "why": option.text,
                }
                for option in question.options
            },
        }
        (OUT_DIR / f"{context_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    return questions


def coverage(questions: list[SeedQuestion]) -> Counter[str]:
    counter: Counter[str] = Counter()
    for question in questions:
        for option in question.options:
            counter.update(option.primary_trait_delta.keys())
    return counter


if __name__ == "__main__":
    built = build()
    non_core = {c.context_id for c in CONTEXT_DEFINITIONS if not c.is_core}
    missing = non_core - set(QUESTIONS)
    print(f"Seed Question 초안 {len(built)}개 (비핵심 Context {len(non_core)}개 중)")
    if missing:
        print(f"  아직 안 쓴 Context: {sorted(missing)}")

    counts = coverage(built)
    uncovered = sorted(KNOWN_TRAIT_IDS - set(counts))
    print("Trait별 관찰 가능 Context 수:")
    for trait_id, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {trait_id:30s} {count}")
    if uncovered:
        raise SystemExit(f"이 10개 Context에서 한 번도 관찰되지 않는 Trait: {uncovered}")
