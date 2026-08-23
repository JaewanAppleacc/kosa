"""Question Quality Gate — 설계안 §11 Code Check. 매 질문 생성 후 LLM 문구를 검사한다.

§11: "Validator는 심리측정학적 타당성을 보증하는 모듈이 아니다. 생성 형식과 설계 규칙
준수 여부를 검사하는 Quality Gate다." 여기서 다루는 건 그 Code Check뿐이고, Semantic
Check(유도성·자연스러움 등, §11)는 Offline Semantic Evaluation(§26 Evaluation Harness,
배치)의 몫이라 이 모듈에는 넣지 않는다.

Code Check 목록 중 Pydantic Schema가 이미 구조적으로 보장하는 항목(JSON Schema 만족,
선택지 정확히 5개, Role ID 서로 다름, 빈 선택지 없음)과 finalize_question()이 이미
거부하는 항목(허용된 Role ID만 사용)은 여기서 다시 검사하지 않는다 — 이 모듈은 그 외
런타임에서만 확인 가능한 규칙(길이 제한, 금지 표현, 문항 반복)을 담당한다.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.schemas.question import FinalizedQuestion

MAX_QUESTION_TEXT_LENGTH = 120
MAX_OPTION_TEXT_LENGTH = 80

# §10 생성 원칙: "직업명과 학과명을 직접 언급하지 않는다", "능력의 자기평가를 요구하지
# 않는다". 아래는 그 원칙을 코드로 확인하기 위한 시작 단계의 금지어 목록이며 완전하지
# 않다 — 팀 검토로 계속 보강해야 한다(Offline Semantic Evaluation이 더 폭넓게 다룬다).
FORBIDDEN_PHRASES: tuple[str, ...] = (
    # 현재 Mock 데이터에 등장하는 대표 전공/직업 명칭 직접 언급 금지
    "미디어커뮤니케이션",
    "산업공학",
    "HCI",
    "UX 디자이너",
    "개발자",
    "프로그래머",
    "디자이너",
    "PD",
    "기자",
    # 능력 자기평가를 직접 요구하는 표현 금지
    "잘하니",
    "잘하는 편인가",
    "재능이 있",
    "능력이 뛰어나",
    "적성에 맞",
    # 2026-08-23 2.1단계 §11 — "~한 편인가요?", "어떤 사람인가요?" 같은 성향 자기평가
    # 문항 일반을 넓게 잡는다("잘하는 편인가"보다 더 넓은 패턴 — 어떤 형용사가 와도
    # "편인가요"로 끝나면 자기평가 질문이다).
    "편인가요",
    "어떤 사람인가요",
)

# 2026-08-23 Trait Ontology v2(2단계) §14 — Direct Probe 질문은 Trait Label을 문장에
# 직접 노출하는 자기평가 문항이면 안 된다(§6 "당신은 구조적으로 사고하는 편인가요?" 같은
# 나쁜 예 금지). run_quality_gate()의 `forbidden_trait_label_phrases`로 넘겨 검사한다 —
# 팀 검토로 계속 보강해야 하는 시작 단계 목록이다(FORBIDDEN_PHRASES와 같은 성격).
V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES: tuple[str, ...] = (
    "구조적 사고", "구조적으로 사고", "체계적으로 사고", "시스템적으로 사고",
    "세부 지향", "detail_orientation",
    "지속력", "완수력", "끈기 있게",
    "불확실성 감내", "uncertainty_tolerance",
    "의견 표명", "opinion_expression",
    "창의적 발상", "creative_ideation",
    "독립적 판단", "독립적으로 판단하는 편", "independent_judgment",
    "systems_thinking", "persistence_completion",
)


class QuestionQualityGateResult(BaseModel):
    passed: bool
    failures: list[str] = []


def run_quality_gate(
    question: FinalizedQuestion,
    previous_question_texts: list[str] | None = None,
    forbidden_trait_label_phrases: tuple[str, ...] | None = None,
    forbidden_anchor_assumption_phrases: tuple[str, ...] | None = None,
) -> QuestionQualityGateResult:
    """2026-08-23 Trait Ontology v2(2.5.1단계) §6: `forbidden_anchor_assumption_phrases`는
    호출자가 현재 Context Anchor의 `forbidden_assumptions`를 그대로 넘길 때만 검사한다
    (Anchor가 없으면 이 검사는 그냥 건너뛴다) — Anchor 자체가 Trait를 결정하지 않으므로
    이 목록은 Trait Mapping과 무관하게 "이 Anchor를 고른 학생에게 전제하면 안 되는 상황"
    만 다룬다."""

    failures: list[str] = []
    previous_question_texts = previous_question_texts or []

    if len(question.question_text) > MAX_QUESTION_TEXT_LENGTH:
        failures.append(
            f"질문 길이 제한 초과: {len(question.question_text)}자 "
            f"(최대 {MAX_QUESTION_TEXT_LENGTH}자)"
        )

    for option in question.options:
        if len(option.text) > MAX_OPTION_TEXT_LENGTH:
            failures.append(
                f"선택지 길이 제한 초과 ({option.role_id}): {len(option.text)}자 "
                f"(최대 {MAX_OPTION_TEXT_LENGTH}자)"
            )

    all_text = question.question_text + " " + " ".join(o.text for o in question.options)
    for phrase in FORBIDDEN_PHRASES:
        if phrase in all_text:
            failures.append(f"금지 표현 포함: {phrase!r}")
    for phrase in forbidden_trait_label_phrases or ():
        if phrase in all_text:
            failures.append(f"Trait Label 직접 노출: {phrase!r}")
    for phrase in forbidden_anchor_assumption_phrases or ():
        if phrase in all_text:
            failures.append(f"Anchor 금지 전제 포함: {phrase!r}")

    if question.question_text.strip() in {t.strip() for t in previous_question_texts}:
        failures.append("이전 질문과 문구가 동일함(반복 금지, §10 생성 원칙)")

    # 선택지가 질문 문장을 그대로 반복하는 사고를 코드로 잡는다 — 실제로 LLM이 5개
    # 선택지를 전부 "~하는 편인가요?" 식 완결된 의문문으로 써서 질문과 한 선택지가
    # 완전히 같은 문장이 된 사례가 있었다(2026-08-21 리뷰 피드백).
    question_text_stripped = question.question_text.strip()
    for option in question.options:
        option_text_stripped = option.text.strip()
        if option_text_stripped == question_text_stripped:
            failures.append(f"선택지({option.role_id})가 질문 문장과 완전히 동일함")
        if option_text_stripped.endswith("?"):
            failures.append(f"선택지({option.role_id})가 의문문 형태임 — 행동 서술형으로 써야 함")

    return QuestionQualityGateResult(passed=not failures, failures=failures)
