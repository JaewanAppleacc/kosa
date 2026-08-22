"""Context × Trait Coverage 검토안 (작업자 C 소유) — 설계안 §6-5, C 지시서 §3.

"각 Context가 Shared Trait를 관찰할 수 있도록 Coverage를 확인한다"를 표로 만든다.
관찰 가능 여부는 추측이 아니라 **실제 Seed Question의 선택지에 그 Trait가 배정돼 있는지**로
판정한다 — 문서상 "관련 있어 보인다"와 실제 관찰 가능은 다르다.

세 가지 상태로 나눈다.

    OBSERVABLE  그 Context의 Seed Question 선택지에 해당 Trait가 실제로 배정돼 있다
    ABSENT      Seed Question은 있는데 그 Trait가 배정돼 있지 않다
    PENDING     그 Context의 Seed Question이 아직 없다 (A 담당 핵심 Context 중 미작성분)

출력:
    data/drafts/context_trait_reviews/coverage_matrix.json
    data/drafts/context_trait_reviews/coverage_matrix.md

실행:
    python scripts/career_build_context_trait_review.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS  # noqa: E402
from src.data.questions.vertical_slice_seed_questions import (  # noqa: E402
    VERTICAL_SLICE_SEED_QUESTIONS,
)
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.schemas.review import DraftEntry, DraftReviewStage  # noqa: E402

OUT_DIR = ROOT / "data" / "drafts" / "context_trait_reviews"
DRAFT_QUESTION_DIR = ROOT / "data" / "drafts" / "question_blueprints"
AUTHOR_ID = "worker_c"
AS_OF = date(2026, 8, 21)

OBSERVABLE, ABSENT, PENDING = "OBSERVABLE", "ABSENT", "PENDING"


def _traits_by_context() -> dict[str, set[str]]:
    """Context별로 Seed Question이 실제 배정한 Trait 집합. A 확정본 + C 초안을 함께 본다."""

    mapping: dict[str, set[str]] = {}
    for question in VERTICAL_SLICE_SEED_QUESTIONS.values():  # A 확정본 (핵심 Context 일부)
        traits = mapping.setdefault(question.context, set())
        for option in question.options:
            traits.update(option.primary_trait_delta)

    for path in sorted(DRAFT_QUESTION_DIR.glob("*.json")):  # C 초안 (비핵심 10개)
        payload = json.loads(path.read_text(encoding="utf-8"))
        traits = mapping.setdefault(payload["context_id"], set())
        for option in payload["seed_question"]["options"]:
            traits.update(option["primary_trait_delta"])
    return mapping


def build() -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_context = _traits_by_context()
    trait_ids = [t.trait_id for t in VERTICAL_SLICE_TRAITS]
    minimum_by_trait = {t.trait_id: t.minimum_context_count for t in VERTICAL_SLICE_TRAITS}

    matrix: dict[str, dict[str, str]] = {}
    for context in CONTEXT_DEFINITIONS:
        assigned = by_context.get(context.context_id)
        matrix[context.context_id] = {
            trait_id: (
                PENDING if assigned is None else (OBSERVABLE if trait_id in assigned else ABSENT)
            )
            for trait_id in trait_ids
        }

    observable_counts = {
        trait_id: sum(1 for row in matrix.values() if row[trait_id] == OBSERVABLE)
        for trait_id in trait_ids
    }
    gaps = {
        trait_id: minimum_by_trait[trait_id] - count
        for trait_id, count in observable_counts.items()
        if count < minimum_by_trait[trait_id]
    }
    pending_contexts = [
        context_id for context_id, row in matrix.items() if PENDING in row.values()
    ]

    entry = DraftEntry(
        draft_id="context_trait_review_coverage_matrix_v0.1",
        draft_type="context_trait_review",
        author_id=AUTHOR_ID,
        review_stage=DraftReviewStage.DRAFT,
        as_of_date=AS_OF,
        notes=(
            "관찰 가능 여부를 문서 판단이 아니라 실제 Seed Question 선택지 배정으로 판정했다. "
            "PENDING은 Seed Question이 아직 없는 Context다."
        ),
    )
    payload = {
        "draft_entry": json.loads(entry.model_dump_json()),
        "matrix": matrix,
        "observable_context_count": observable_counts,
        "minimum_context_count": minimum_by_trait,
        "coverage_gaps": gaps,
        "pending_contexts": pending_contexts,
    }
    (OUT_DIR / "coverage_matrix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    label_by_context = {c.context_id: c.label for c in CONTEXT_DEFINITIONS}
    lines = [
        "# Context × Trait Coverage 검토표 (C 초안)",
        "",
        f"작성 {AS_OF} · 작성자 {AUTHOR_ID} · 검토 단계 DRAFT",
        "",
        "판정 기준: 그 Context의 Seed Question 선택지에 해당 Trait가 실제로 배정돼 있는가.",
        "`O`=관찰 가능 · `-`=배정 없음 · `?`=Seed Question 미작성",
        "",
        "| Context | " + " | ".join(trait_ids) + " |",
        "|---" * (len(trait_ids) + 1) + "|",
    ]
    symbol = {OBSERVABLE: "O", ABSENT: "-", PENDING: "?"}
    for context in CONTEXT_DEFINITIONS:
        row = matrix[context.context_id]
        cells = " | ".join(symbol[row[trait_id]] for trait_id in trait_ids)
        lines.append(f"| {label_by_context[context.context_id]} | {cells} |")

    lines += [
        "",
        "## Trait별 관찰 가능 Context 수",
        "",
        "| trait_id | 관찰 가능 Context 수 | 최소 요구 | 부족분 |",
        "|---|---|---|---|",
    ]
    for trait_id in trait_ids:
        gap = gaps.get(trait_id, 0)
        lines.append(
            f"| {trait_id} | {observable_counts[trait_id]} | "
            f"{minimum_by_trait[trait_id]} | {gap if gap > 0 else '-'} |"
        )

    lines += [
        "",
        "## C가 A에게 확인 요청하는 것",
        "",
        f"1. Seed Question이 아직 없는 Context: {', '.join(pending_contexts) or '없음'}. "
        "A 지시서 §4가 핵심 Context 5개의 Seed Question을 A 책임으로 두므로 C가 대신 쓰지 않았다. "
        "작성되면 이 표를 다시 돌려야 한다.",
        "2. 이 표는 Seed Question 1개 기준이다. 꼬리질문(§7-2)까지 포함하면 관찰 가능 범위가 "
        "넓어지지만, 꼬리질문은 세션마다 달라져 사전 Coverage로 셀 수 없다. 사전 Coverage를 "
        "Seed 기준으로만 보는 게 맞는지 확인이 필요하다.",
        "3. `visual_expression`은 비핵심 10개 중 2개(미술·디자인, 패션·뷰티)에서만 관찰된다. "
        "domain_specific이라 최소 Context가 1개여서 규칙은 만족하지만, 이 Trait를 고른 학생이 "
        "적은 근거로 판정될 여지가 있다.",
    ]
    (OUT_DIR / "coverage_matrix.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


if __name__ == "__main__":
    use_utf8_stdout()
    result = build()
    print(f"Coverage 표 생성 — Context {len(result['matrix'])}개 × Trait {len(VERTICAL_SLICE_TRAITS)}개")
    if result["pending_contexts"]:
        print(f"  Seed Question 미작성 Context: {result['pending_contexts']}")
    if result["coverage_gaps"]:
        print(f"  최소 Context 수 미달 Trait: {result['coverage_gaps']}")
    else:
        print("  최소 Context 수 미달 Trait 없음")
