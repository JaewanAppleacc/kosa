"""V2 Direct Probe 자동 품질 검사(Advisory) — 2026-08-23 Trait Ontology v2(2.1단계) §11.

여기 있는 검사는 "완벽한 타당성 판정이 아니라 검토 후보를 표시하는 용도"다(§11) —
전부 통과해도 `review_status`를 자동으로 `team_reviewed`로 바꾸지 않는다. 하드 실패
(LLM이 생성한 질문을 그 자리에서 거부하는 것)는 여전히
`question_quality_gate.run_quality_gate()`가 담당한다 — 이 모듈은 그 함수를 그대로
재사용(base_question에도 동일하게 적용)한 뒤, 이 파일에서만 다루는 추가 휴리스틱
(극단 표현·길이 편차·역할 선호 문구 등)을 얹는다."""

from __future__ import annotations

from src.engines.question_quality_gate import (
    V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES,
    run_quality_gate,
)
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint

# §11: "항상", "무조건", "절대", "아무도 안 해본" 같은 극단 표현 — 실제로 그 정도로
# 단정적인 학생 행동은 드물어서, 선택지를 사회적으로 유일하게 옳은 답처럼 보이게
# 만들 위험이 있다.
EXTREME_PHRASES: tuple[str, ...] = ("항상", "무조건", "절대", "아무도 안 해본", "누구나 다")

ROLE_PREFERENCE_PHRASES: tuple[str, ...] = ("역할을 맡고 싶", "무슨 역할을",)

# 옵션 길이 편차가 이 값(글자 수)을 넘으면 검토 후보로 표시한다 — 하드 기준이 아니라
# 사람이 다시 볼 만한 지점을 표시하는 용도라 다소 여유 있게 잡았다.
OPTION_LENGTH_VARIANCE_THRESHOLD = 15
TARGET_OPTION_LENGTH_OUTLIER_MARGIN = 10


def _target_option(blueprint: V2DirectProbeBlueprint):
    return next(o for o in blueprint.base_question.options if blueprint.trait_id in o.primary_trait_delta)


def question_level_flags(blueprint: V2DirectProbeBlueprint) -> list[str]:
    """질문 전체(문항 + 5개 선택지)에 대한 검토 후보 사유 목록. 빈 리스트면 자동 검사가
    걸어낸 문제가 없다는 뜻이지, 사람 검토가 필요 없다는 뜻이 아니다."""

    flags: list[str] = []
    question = blueprint.base_question
    all_text = question.question_text + " " + " ".join(o.text for o in question.options)

    gate_result = run_quality_gate(question, forbidden_trait_label_phrases=V2_DIRECT_PROBE_TRAIT_LABEL_PHRASES)
    flags.extend(f"Quality Gate: {failure}" for failure in gate_result.failures)

    for phrase in ROLE_PREFERENCE_PHRASES:
        if phrase in question.question_text:
            flags.append(f"역할 선호 질문 패턴 검토 대상: {phrase!r}")

    for phrase in EXTREME_PHRASES:
        if phrase in all_text:
            flags.append(f"극단 표현 포함: {phrase!r}")

    lengths = [len(o.text) for o in question.options]
    if max(lengths) - min(lengths) > OPTION_LENGTH_VARIANCE_THRESHOLD:
        flags.append(f"선택지 길이 편차 큼(최대 {max(lengths)}자, 최소 {min(lengths)}자)")

    target = _target_option(blueprint)
    other_lengths = [len(o.text) for o in question.options if o.role_id != target.role_id]
    if other_lengths and len(target.text) > max(other_lengths) + TARGET_OPTION_LENGTH_OUTLIER_MARGIN:
        flags.append("Target Option이 다른 선택지보다 지나치게 김(구체성 편중 의심)")

    # 동일 행동을 말만 바꿔 반복하는지에 대한 약한 신호 — 두 선택지의 앞 6글자가
    # 우연히 같으면(예: 둘 다 "다른 사람에게" 로 시작) 검토 후보로만 표시한다.
    prefixes = [o.text[:6] for o in question.options]
    if len(set(prefixes)) < len(prefixes):
        flags.append("선택지 문두가 겹치는 쌍이 있음(표현만 바뀐 반복 의심)")

    return flags


def worksheet_row_flags(blueprint: V2DirectProbeBlueprint, option) -> list[str]:  # noqa: ANN001
    """Worksheet 한 행(Option 하나)에 대한 자동 검수 결과."""

    flags: list[str] = []
    for phrase in EXTREME_PHRASES:
        if phrase in option.text:
            flags.append(f"극단 표현: {phrase!r}")
    if option.text.strip().endswith("?"):
        flags.append("의문문 형태")
    is_target = blueprint.trait_id in option.primary_trait_delta
    if is_target and len(option.text) > 60:
        flags.append("Target Option 문장이 김(구체성 편중 검토)")
    return flags
