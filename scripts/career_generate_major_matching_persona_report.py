"""고정 Persona 매칭 진단 리포트 생성 — 2026-08-23 13차 리뷰 §4.

`eval/major_matching_persona_diagnostics.py`의 고정 Persona 7개를 실제 Vertical Slice
대표 전공 3개(media_communication/hci_ux/industrial_engineering) MajorProfile에 대해
돌려서, `outputs/evaluation/major_matching_persona_report.md`를 결정론적으로 만든다.

매칭 공식(src/engines/matching_engine.py)은 이 스크립트가 절대 수정하지 않는다 — 있는
그대로 호출한 결과를 사실 그대로 기록만 한다. 동점·넓은 Vector로 인한 과도한 공동 추천
가능성은 "버그"로 단정하지 않고, 공유 Trait 충족도만 계산하는 현재 공식의 구조적 결과로
분석해 기록한다.

실행:
    PYTHONPATH=. python scripts/career_generate_major_matching_persona_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from eval.major_matching_persona_diagnostics import (  # noqa: E402
    PERSONAS,
    PersonaDiagnosticResult,
    diagnose_persona,
)
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES  # noqa: E402
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402

OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "major_matching_persona_report.md"

_STATUS_KO = {"computed": "computed", "insufficient": "insufficient"}


def _format_score(score: float | None) -> str:
    return f"{score:.4f}" if score is not None else "—"


def _persona_table(result: PersonaDiagnosticResult) -> str:
    lines = [
        "| major_id | status | score | usable_trait_count | usable_vector_group_count | evidence_sufficiency | relevance_label |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in result.majors:
        lines.append(
            f"| {row.major_id} | {row.status} | {_format_score(row.score)} | "
            f"{row.usable_trait_count} | {row.usable_vector_group_count} | "
            f"{row.evidence_sufficiency or '—'} | {row.relevance_label or '—'} |"
        )
    return "\n".join(lines)


def render_report(results: list[PersonaDiagnosticResult]) -> str:
    lines: list[str] = []
    lines.append("# 고정 Persona 매칭 진단 리포트")
    lines.append("")
    lines.append(
        "이 리포트는 `src/engines/matching_engine.py`의 매칭 공식을 **수정하지 않고 있는 "
        "그대로 호출**한 결과를 기록한다. 2026-08-22 12차 리뷰로 대표 전공 3개의 Trait "
        "Vector가 실제 학과 공식 자료 근거로 바뀐 뒤, 고정 Persona 7개에 대해 각 전공이 "
        "computed/insufficient 중 어느 쪽인지, 동점이 발생하는지를 사실 그대로 관찰한다. "
        "결과를 원하는 방향으로 만들기 위해 Persona나 가중치를 거꾸로 조정하지 않았다."
    )
    lines.append("")
    lines.append(
        "재현 방법: `PYTHONPATH=. python scripts/career_generate_major_matching_persona_report.py` "
        "— 같은 입력(Vertical Slice MajorProfile 3개 + 아래 Persona 정의)이면 항상 같은 "
        "리포트가 나온다(결정론적, LLM 호출 없음)."
    )
    lines.append("")
    lines.append("## 대표 전공 Trait Vector (참고용, 매칭 공식이 실제로 읽는 값)")
    lines.append("")
    for major in VERTICAL_SLICE_MAJOR_PROFILES:
        merged = {
            **major.interest_vector,
            **major.cognitive_vector,
            **major.work_style_vector,
            **major.environment_vector,
        }
        rendered = ", ".join(f"{k}={v}" for k, v in merged.items())
        lines.append(f"- **{major.major_id}**({major.label}): {rendered}")
    lines.append("")

    lines.append("## Persona별 결과")
    lines.append("")
    for result in results:
        persona = result.persona
        lines.append(f"### {persona.persona_id} — {persona.label}")
        lines.append("")
        lines.append(f"**설계 근거**: {persona.rationale}")
        lines.append("")
        spec = persona.trait_spec
        if spec.strong:
            lines.append(f"- STRONG 입력: {sorted(spec.strong)}")
        if spec.moderate:
            lines.append(f"- MODERATE 입력: {sorted(spec.moderate)}")
        if spec.limited:
            lines.append(f"- LIMITED 입력: {sorted(spec.limited)}")
        if spec.unresolved_conflict:
            lines.append(f"- 미해결 Conflict(CONFLICTING Mask) 입력: {sorted(spec.unresolved_conflict)}")
        lines.append("")
        lines.append(_persona_table(result))
        lines.append("")
        lines.append(f"- 관련성 높음 전공: {result.relevant_major_ids or '없음'}")
        lines.append(f"- 공동 1위(동점) 여부: {'예' if result.is_tied_for_first else '아니오'}")
        if result.insufficient_evidence_message:
            lines.append(f"- 전체 안내 메시지: {result.insufficient_evidence_message}")
        lines.append("")

    lines.append("## 관찰된 현상 분류")
    lines.append("")
    lines.append("### 1. 정상적인 복수 전공 추천")
    lines.append(
        "- `all_limited` Persona: 12개 Trait 전부 LIMITED(0.33)로만 관찰되면 세 전공 모두 "
        "`computed`이지만 점수가 똑같이 0.33으로 나온다. 가중 충족도 공식은 입력값이 전부 "
        "같으면 가중치 분포와 무관하게 같은 결과를 낸다는 성질(가중평균) 때문이며, "
        "MINIMUM_SCORE_FOR_HIGH_RELEVANCE(0.6) 미만이라 셋 다 '관련성 높음'이 아니라 "
        "'함께 탐색해볼 분야'로 내려간다 — 사용자에게는 '아직 뚜렷한 강점 Trait가 없다'는 "
        "정직한 신호로 정상 동작이다."
    )
    lines.append("")
    lines.append("### 2. Trait Vector가 넓어서 발생하는 과도한 공동 추천 가능성")
    lines.append(
        "- `analytical` Persona: industrial_engineering과 media_communication이 둘 다 "
        "score=1.0000으로 동점 1위. media_communication Vector가 causal_analysis/"
        "pattern_finding/planning/information_comparison을 industrial_engineering과 "
        "동일하거나 인접한 가중치로 전부 포함하기 때문이다(§14가 사전에 지적한 "
        "'분석 Trait가 강하면 industrial_engineering과 media_communication이 동점 가능')."
    )
    lines.append(
        "- `visual_user_facing` Persona: hci_ux와 media_communication이 둘 다 "
        "score=1.0000으로 동점 1위. hci_ux Vector 3개(visual_expression/"
        "audience_response_prediction/tool_utilization)가 media_communication Vector에 "
        "**완전히 같은 가중치(0.67/1.00/0.67)로 그대로 포함**돼 있어, 이 3개 Trait만 관찰된 "
        "학생에게는 두 전공이 수학적으로 구분 불가능하다(§14 '동점 가능' 사전 지적과 일치)."
    )
    lines.append(
        "- **구조적 원인 분석**: 두 경우 모두 매칭 공식 버그가 아니라, 현재 공식이 "
        "'전공이 중요하게 보는 Trait 중 학생이 충족하는 비율'만 계산하고 **'그 전공만의 "
        "고유한 Trait 조합인가'는 전혀 고려하지 않기 때문에** 생기는 구조적 결과다. "
        "media_communication은 실제 학과 공식 자료상 hci_ux·industrial_engineering 두 전공의 "
        "핵심 Trait를 모두 포함하는 폭넓은 커리큘럼(데이터 분석 + UX/시각 + 캠페인 기획)을 "
        "갖고 있어, 이 구조적 결과 자체가 근거 데이터를 정직하게 반영한 것이다(예전 손으로 "
        "채운 값에서는 이런 겹침이 우연히 가려져 있었을 뿐이다)."
    )
    lines.append("")
    lines.append("### 3. 전공 근거 부족으로 판단할 수 없는 경우")
    lines.append(
        "- `tool_only`(Trait 1개만 강함), `sparse_partial`(Trait 2개만 관찰), "
        "`unresolved_conflict`(핵심 Trait 중 하나가 Mask돼 usable_vector_group_count가 "
        "1로 떨어짐) 세 Persona 모두 세 전공 전부 `insufficient`로 나온다. "
        "MINIMUM_USABLE_TRAITS(3)·MINIMUM_USABLE_VECTOR_GROUPS(2) 요건이 정상적으로 "
        "'아직 판단하기엔 근거가 부족하다'는 상태를 걸러낸 것이지, 대표 전공 3개 자체의 "
        "결함이 아니다."
    )
    lines.append(
        "- `planning_collaboration` Persona는 media_communication이 유리할 만한 Trait 조합"
        "(계획+협업 선호)을 답했는데도, 그 2개 Trait가 media_communication Vector에서 "
        "work_style 그룹 하나에 몰려 있어(usable_vector_group_count=1) usable_trait_count=2로 "
        "여전히 insufficient가 나온다 — '전공에 유리한 Trait를 답했다'와 '그 전공을 계산할 "
        "만큼 답했다'가 다를 수 있음을 보여주는 경계 사례다."
    )
    lines.append("")
    lines.append("### 4. 추가 Trait가 필요한 문제인지")
    lines.append(
        "아니다. 위 동점 현상은 Trait 개수·정의 부족 때문이 아니라, hci_ux·"
        "industrial_engineering의 핵심 Trait가 이미 media_communication 안에 실제로(공식 "
        "커리큘럼상) 포함돼 있기 때문이다. Trait를 더 쪼갠다고 이 구조적 겹침이 사라지지 "
        "않는다 — 이번 라운드 범위(§ '기존 12개 trait_id... 임의로 변경하지 마세요')에서도 "
        "다루지 않았다."
    )
    lines.append("")
    lines.append("### 5. 매칭 공식 보완이 필요한 문제인지")
    lines.append(
        "판단을 유보한다. 이번 라운드는 '가중치나 Fixture를 억지로 조정해 원하는 순서를 "
        "만들지 않는다'는 제약이 있어 공식을 고치지 않았다. 다만 관찰된 사실은 다음과 같이 "
        "정리할 수 있다: 현재 공식은 '전공 A의 Trait 충족도'만 독립적으로 계산하고 '학생의 "
        "Trait 조합이 전공 A에만 있는 고유한 조합인지, 전공 B와도 겹치는 조합인지'는 계산에 "
        "안 들어간다. 동점을 구조적으로 줄이려면(공식을 바꾼다면) 전공 간 Trait 겹침을 "
        "패널티로 반영하는 방식이 후보가 될 수 있지만, 이는 §16 '검증된 값이 아니라 MVP "
        "초기 휴리스틱'이라는 기존 가중치 체계 자체를 다시 설계하는 작업이라 이번 라운드 "
        "범위를 벗어난다 — 다음 라운드에서 별도로 판단이 필요한 항목으로 남긴다."
    )
    lines.append("")

    lines.append("## 회귀 관찰 요약 (다음 라운드에서 벡터가 바뀌면 이 표도 다시 생성해서 비교)")
    lines.append("")
    lines.append("| 현상 | Persona | 관찰 결과 |")
    lines.append("|---|---|---|")
    lines.append(
        "| HCI 관련 Trait 강함 → hci_ux/media_communication 동점 | visual_user_facing | "
        f"{'동점 확인' if any(r.persona.persona_id == 'visual_user_facing' and r.is_tied_for_first for r in results) else '동점 아님(재확인 필요)'} |"
    )
    lines.append(
        "| 분석 Trait 강함 → industrial_engineering/media_communication 동점 | analytical | "
        f"{'동점 확인' if any(r.persona.persona_id == 'analytical' and r.is_tied_for_first for r in results) else '동점 아님(재확인 필요)'} |"
    )
    lines.append("")

    lines.append("## 12개 Trait ID (참고 — 이번 라운드에서 변경 없음)")
    lines.append("")
    lines.append(", ".join(t.trait_id for t in VERTICAL_SLICE_TRAITS))
    lines.append("")

    return "\n".join(lines) + "\n"


def main() -> None:
    trait_defs = {t.trait_id: t for t in VERTICAL_SLICE_TRAITS}
    results = [
        diagnose_persona(persona, VERTICAL_SLICE_MAJOR_PROFILES, trait_defs) for persona in PERSONAS
    ]
    report = render_report(results)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
