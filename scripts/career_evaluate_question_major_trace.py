"""질문 선택 → Trait 근거 → 전공 점수 경로를 소수 전공 draft까지 추적한다.

공개 Master와 Matching Engine은 수정하지 않는다. 관광·호텔 Profile은 평가 가설이며
REVIEW_REQUIRED 상태로만 사용한다.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eval.major_matching_persona_diagnostics import MatchingPersona, PersonaTraitSpec, diagnose_persona  # noqa: E402
from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES  # noqa: E402
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.schemas.major import MajorProfile  # noqa: E402

BLUEPRINT_DIR = ROOT / "data" / "drafts" / "question_blueprints"
OUTPUT = ROOT / "outputs" / "evaluation" / "question_to_minor_major_trace.md"

# 독립적으로 먼저 정한 학생 답변 시나리오. 결과를 본 뒤 선택지를 바꾸지 않는다.
HOTEL_SCENARIO = (
    ("travel", "route_planning"),
    ("cooking", "prep_order"),
    ("fashion_beauty", "how_others_see"),
    ("writing", "imagining_reader"),
    ("science", "checking_sources"),
    ("law_politics", "checking_facts"),
    ("history_humanities", "people_of_the_time"),
    ("volunteer", "reading_others_need"),
)


def load_blueprints() -> dict[str, dict]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(BLUEPRINT_DIR.glob("*.json"))
    }


def trace_answers(scenario=HOTEL_SCENARIO) -> tuple[list[dict], dict[str, int], dict[str, int]]:
    blueprints = load_blueprints()
    rows: list[dict] = []
    supports: Counter[str] = Counter()
    contexts: dict[str, set[str]] = defaultdict(set)
    for context, role_id in scenario:
        payload = blueprints[context]
        role = next(r for r in payload["option_blueprint"]["roles"] if r["role_id"] == role_id)
        option = next(o for o in payload["seed_question"]["options"] if o["role_id"] == role_id)
        trait_id = next(iter(role["primary_trait_delta"]))
        supports[trait_id] += 1
        contexts[trait_id].add(context)
        rows.append({
            "context": context,
            "question": payload["seed_question"]["question_text"],
            "selected_answer": option["text"],
            "trait_id": trait_id,
            "delta": role["primary_trait_delta"][trait_id],
        })
    return rows, dict(supports), {k: len(v) for k, v in contexts.items()}


def tourism_draft_profile() -> MajorProfile:
    return MajorProfile(
        major_id="tourism_hotel_evaluation_draft",
        label="관광·호텔(평가용 draft)",
        interest_vector={"audience_response_prediction": 1.0, "emotional_interpretation": 0.67},
        cognitive_vector={"information_comparison": 0.67},
        work_style_vector={"planning": 1.0, "collaboration_preference": 0.67},
        environment_vector={"change_adaptation": 0.67},
        source_ids=["academyinfo_small_series_039", "evaluation_hypothesis_not_official_curriculum"],
        extraction_method="manual",
        review_status="REVIEW_REQUIRED",
        profile_version="minor_major_evaluation_draft_v1",
        updated_at=datetime(2026, 8, 24, tzinfo=timezone.utc),
    )


def evaluate() -> tuple[list[dict], dict, object]:
    trace, supports, context_counts = trace_answers()
    usable = {trait for trait, count in supports.items() if count >= 2 and context_counts[trait] >= 2}
    persona = MatchingPersona(
        persona_id="hotel_operations_interest_draft",
        label="호텔 운영·고객 경험 관심",
        rationale="질문 선택을 먼저 고정하고 같은 Trait가 서로 다른 Context에서 두 번 관찰된 경우만 사용",
        trait_spec=PersonaTraitSpec(moderate=usable),
    )
    majors = [*VERTICAL_SLICE_MAJOR_PROFILES, tourism_draft_profile()]
    result = diagnose_persona(persona, majors, {t.trait_id: t for t in VERTICAL_SLICE_TRAITS})
    return trace, {"support_count": supports, "context_count": context_counts, "usable_traits": sorted(usable)}, result


def render() -> str:
    trace, evidence, result = evaluate()
    lines = [
        "# 질문 → Trait → 소수 전공 매칭 추적",
        "",
        "이 평가는 A의 질문 생성·종료 로직과 Matching Engine을 수정하지 않는다. C가 만든 고정 "
        "질문에서 답변을 먼저 선택하고, 그 선택이 만든 Trait만 현재 엔진에 넣었다. 관광·호텔 "
        "Profile은 공개 Master가 아닌 `REVIEW_REQUIRED` 평가 가설이다.",
        "",
        "## 1. 질문과 답변이 어떤 Trait 근거가 되는가",
        "",
        "| Context | 질문 | 선택 답변 | 연결 Trait |",
        "|---|---|---|---|",
    ]
    for row in trace:
        lines.append(f"| {row['context']} | {row['question']} | {row['selected_answer']} | `{row['trait_id']}` |")
    lines += ["", "같은 Trait가 서로 다른 Context에서 두 번 이상 관찰된 경우만 매칭 입력으로 사용했다.", ""]
    for trait in evidence["usable_traits"]:
        lines.append(f"- `{trait}`: support {evidence['support_count'][trait]}회 / context {evidence['context_count'][trait]}개")
    lines += [
        "",
        "## 2. 현재 Matching Engine 결과",
        "",
        "| 전공 | 상태 | 내부 진단 점수 | 사용 Trait 수 | 사용 Vector 그룹 수 |",
        "|---|---|---:|---:|---:|",
    ]
    for row in result.majors:
        score = "—" if row.score is None else f"{row.score:.4f}"
        lines.append(f"| {row.label} | {row.status} | {score} | {row.usable_trait_count} | {row.usable_vector_group_count} |")
    lines += [
        "",
        "## 3. 이 결과가 증명하는 것과 남은 Gate",
        "",
        "- 질문 선택에서 전공 점수까지 어떤 Trait가 사용됐는지 행 단위로 추적할 수 있다.",
        "- 대표 전공 목록에 관광·호텔 Profile이 없으면 해당 학생은 구조적으로 그 결과를 받을 수 없다.",
        "- 평가용 Profile을 넣으면 기존 엔진이 소수 전공도 계산할 수 있어 기술적 확장 경로는 확인된다.",
        "- 이 시나리오에서는 관광·호텔과 미디어·커뮤니케이션이 0.6700으로 동점이다. 후보 추가만으로 분야 간 변별력이 생기지는 않으며 경계 Persona 평가가 필요하다.",
        "- 점수는 후보 정렬 진단값이지 학생 적합 확률이 아니다.",
        "- 관광·호텔 Vector는 공식 교육과정으로 검수되지 않았으므로 공개·Master 승격은 금지한다.",
        "",
        "**승격 Gate:** 서로 다른 대학 5개 이상의 공식 교육과정으로 Trait 근거를 대조하고, 호텔/관광·경영·무역 물류 경계 Persona를 블라인드 평가한 뒤 reviewer 승인을 받아야 한다.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
