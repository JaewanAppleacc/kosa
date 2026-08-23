"""ContextPack Context별 질문 Runtime Report 생성 — 2026-08-23 Trait Ontology
v2(2.9단계) §12.

`저장된 질문 은행 수`(Routing/Seed/Adaptive Blueprint/Backup 후보 전체)와 `학생이
실제로 응답하는 질문 수`(선택한 Anchor 하나·검수 승인 상태 기준)를 명확히 구분해서
기록한다. 학생 공개 API에는 이 값을 노출하지 않는다 — 이 파일은 내부 Evaluation
전용이다.

`ENABLE_CONTEXT_PACK_RUNTIME`가 꺼져 있어도, 이 스크립트는 Registry를 직접 만들어
읽기만 하므로 실제 서비스 상태와 무관하게 항상 계산할 수 있다. "실제 현재 상태"
열은 지금 커밋된 실제 검수 상태 파일(`data/reviews/context_packs/*.json`,
`data/reviews/context_pack_shared_probes_review_status.json`)을 그대로 읽는다 —
이 스크립트가 검수 상태를 대신 채우거나 승인하지 않는다.

실행:
    PYTHONPATH=. python scripts/career_generate_context_pack_question_runtime_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS  # noqa: E402
from src.data.contexts.context_definitions import CONTEXT_DEFINITIONS, CONTEXT_IDS  # noqa: E402
from src.data.questions.context_pack_shared_probe_blueprints import (  # noqa: E402
    CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS,
)
from src.services.context_pack_registry import ContextPackRegistry  # noqa: E402
from src.services.context_trait_coverage import compute_context_trait_coverage  # noqa: E402
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "context_pack_question_runtime_report.md"
_CONTEXT_LABEL_BY_ID = {c.context_id: c.label for c in CONTEXT_DEFINITIONS}


def _count_no_signal_options(pack) -> int:
    count = 0
    for seed in pack.seed_anchor_variants:
        count += sum(1 for o in seed.question.options if not o.primary_trait_delta)
    for backup in pack.anchor_backup_questions:
        count += sum(1 for o in backup.question.options if not o.primary_trait_delta)
    for probe in pack.direct_probe_candidates:
        count += sum(1 for m in probe.option_mappings if m.mapping_type == "NO_SIGNAL")
    return count


def _min_max_response_question_count(seed_present: bool, adaptive_bank: int, backup_present: bool) -> tuple[int, int]:
    """§4/§7 정책을 그대로 반영한 산술 — 실제 Runtime의 `decide_stop_or_continue`
    호출 없이도 "이 은행 크기로 낼 수 있는 범위"를 정적으로 계산한다. Seed가 없으면
    Context 자체가 서빙되지 않으므로 (0, 0).

    최소: Seed(1) + min(4, adaptive_bank + (1 if backup_present else 0)).
    최대: Seed(1) + min(6, adaptive_bank + (1 if backup_present else 0))."""

    if not seed_present:
        return (0, 0)
    reachable = adaptive_bank + (1 if backup_present else 0)
    return (1 + min(4, reachable), 1 + min(6, reachable))


def build_report() -> str:
    registry = ContextPackRegistry(known_context_ids=frozenset(CONTEXT_IDS))
    trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
    known_trait_ids = set(trait_definitions)

    lines: list[str] = []
    lines.append("# ContextPack Context별 질문 Runtime Report")
    lines.append("")
    lines.append(
        "2026-08-23 Trait Ontology v2(2.9단계) §12 — `PYTHONPATH=. python "
        "scripts/career_generate_context_pack_question_runtime_report.py`로 재생성한다. "
        "`저장된 질문 은행 수`는 Context 제작 에이전트가 채운 전체 후보 수이고, "
        "`실제 최소·최대 응답 질문 수`는 학생 한 명이 Anchor 하나를 고른 뒤 실제로 "
        "답하는 개수다(Routing 1개는 어느 쪽에도 포함하지 않는다 — Trait Evidence를 "
        "만들지 않기 때문이다)."
    )
    lines.append("")
    lines.append(
        "| Context | Routing 은행 | Seed 은행 | Adaptive Blueprint 은행(자체+공용) | "
        "Backup 은행 | 최소 응답(설계상) | 최대 응답(설계상) | 현재 실제 최소·최대(검수 상태 반영) | "
        "PRIMARY Trait 수 | RELATED-only 수 | NO_SIGNAL 수 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")

    if registry.discovery_errors() or registry.ontology_errors():
        lines.append("")
        lines.append("**구조·Ontology 오류로 제외된 Pack**")
        for name, err in {**registry.discovery_errors(), **registry.ontology_errors()}.items():
            lines.append(f"- `{name}`: {err}")
        lines.append("")

    for context_id in sorted(ALL_BATCH_CONTEXT_IDS):
        pack = registry.get_pack(context_id)
        label = _CONTEXT_LABEL_BY_ID.get(context_id, context_id)
        if pack is None:
            lines.append(f"| {label}({context_id}) | — | — | — | — | — | — | Pack 미발견/구조 오류 | — | — | — |")
            continue

        coverage = compute_context_trait_coverage(pack, known_trait_ids)
        shared_for_context = [bp for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS if context_id in bp.allowed_context_ids]
        adaptive_bank_design = len(pack.direct_probe_candidates) + len(shared_for_context)

        design_min, design_max = _min_max_response_question_count(
            seed_present=bool(pack.seed_anchor_variants), adaptive_bank=adaptive_bank_design,
            backup_present=bool(pack.anchor_backup_questions),
        )

        actual_shared = registry.shared_probe_blueprints_for_context(context_id)
        actual_adaptive_bank = len(pack.direct_probe_candidates) + len(actual_shared)  # 자체 direct_probe_candidates는 별도 검수 게이트가 없다(§6 한계로 별도 보고).
        is_pack_approved = registry.is_pack_review_approved(context_id)
        if not is_pack_approved:
            actual_min, actual_max = (0, 0)
            actual_note = "미승인(Fail-Closed) — 서빙 안 됨"
        else:
            actual_min, actual_max = _min_max_response_question_count(
                seed_present=True, adaptive_bank=actual_adaptive_bank, backup_present=True,
            )
            actual_note = f"{actual_min}~{actual_max}"

        related_only = coverage.related_trait_ids - coverage.primary_trait_ids
        no_signal_count = _count_no_signal_options(pack)

        lines.append(
            f"| {label}({context_id}) | 1 | {coverage.seed_question_count} | "
            f"{len(pack.direct_probe_candidates)}+{len(shared_for_context)} | {coverage.backup_question_count} | "
            f"{design_min} | {design_max} | {actual_note} | "
            f"{len(coverage.primary_trait_ids)} | {len(related_only)} | {no_signal_count} |"
        )

    lines.append("")
    lines.append("## 공용 Adaptive Probe Blueprint 은행")
    lines.append("")
    lines.append(
        f"- 전체 {len(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS)}개, 신규 12개 Context 전부에 "
        "`allowed_context_ids`로 노출됨(§5 — 12개 Context × 개별 Blueprint를 새로 만들지 "
        "않고 공유한다)."
    )
    lines.append(
        f"- 현재 reviewer_1 APPROVED: {len(registry.shared_probe_blueprints_for_context(sorted(ALL_BATCH_CONTEXT_IDS)[0]))}개"
        "(모든 신규 Context에 공통 적용되므로 어느 Context 기준으로 세도 같다)."
    )
    lines.append("")
    lines.append(
        "## 참고: 저장된 질문 은행 수 ≠ 학생 응답 수\n\n"
        "예를 들어 Seed 은행 5개는 Anchor 5개 각각 전용이라 학생 한 명은 그중 정확히 "
        "1개만 받는다. Adaptive Blueprint 은행도 마찬가지로 전체 후보 목록이고, 실제로는 "
        "그중 최소 4개·최대 6개만 그 학생에게 순차적으로 제시된다(§4 최소·최대 정책, "
        "`evidence_engine.decide_stop_or_continue` 재사용)."
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    use_utf8_stdout()
    report = build_report()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
