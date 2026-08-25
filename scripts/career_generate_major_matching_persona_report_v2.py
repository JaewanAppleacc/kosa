"""39개 Service Major v2 — 고정 Persona 회귀 진단 리포트 생성 — 2026-08-25
지시서(a/major-profiles-v2-38) §4/§6.

`eval/major_matching_persona_diagnostics_v2.py`의 Persona 48개(자기 전공형 39
+ 인접 혼동/대조군 9)를 실제 39개 Service Major v2 Profile에 대해 돌려서,
`outputs/evaluation/major_matching_persona_report_v2.md`(사람이 읽는 표)와
`.json`(테스트가 재검증하는 정본 수치)을 결정론적으로 만든다.

매칭 공식(src/engines/matching_engine_v2.py)은 이 스크립트가 절대 수정하지
않는다 — 있는 그대로 호출한 결과를 사실 그대로 기록만 한다.

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_generate_major_matching_persona_report_v2.py
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from eval.major_matching_persona_diagnostics_v2 import (  # noqa: E402
    PersonaDiagnosticResultV2,
    all_personas,
    diagnose_persona_v2,
)
from src.data.majors.service_major_profiles_v2 import SERVICE_MAJOR_PROFILES_V2  # noqa: E402

JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "major_matching_persona_report_v2.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "major_matching_persona_report_v2.md"


def _format_score(score: float | None) -> str:
    return f"{score:.4f}" if score is not None else "—"


def build_report() -> dict[str, Any]:
    personas = all_personas()
    results: list[PersonaDiagnosticResultV2] = [diagnose_persona_v2(p) for p in personas]

    all_major_ids = {m.major_id for m in SERVICE_MAJOR_PROFILES_V2}
    appearance_counter: Counter[str] = Counter()
    ever_appeared: set[str] = set()
    self_hits = 0
    self_targeted = 0
    for r in results:
        for mid in r.relevant_major_ids + r.explore_together_major_ids:
            appearance_counter[mid] += 1
            ever_appeared.add(mid)
        if r.persona.target_major_ids:
            self_targeted += 1
            if r.self_major_in_relevant:
                self_hits += 1

    never_appeared = sorted(all_major_ids - ever_appeared)
    total_appearances = sum(appearance_counter.values())
    top3 = appearance_counter.most_common(3)
    top3_share = (sum(c for _, c in top3) / total_appearances) if total_appearances else 0.0

    persona_summaries = [
        {
            "persona_id": r.persona.persona_id, "label": r.persona.label, "rationale": r.persona.rationale,
            "strong_trait_ids": list(r.persona.strong_trait_ids), "target_major_ids": list(r.persona.target_major_ids),
            "relevant_major_ids": r.relevant_major_ids, "explore_together_major_ids": r.explore_together_major_ids,
            "self_major_in_relevant": r.self_major_in_relevant,
            "insufficient_evidence_message": r.insufficient_evidence_message,
        }
        for r in results
    ]

    return {
        "persona_count": len(personas),
        "total_major_count": len(all_major_ids),
        "coverage_appeared_major_count": len(ever_appeared),
        "coverage_never_appeared_major_ids": never_appeared,
        "self_major_top3_hit_count": self_hits,
        "self_major_top3_targeted_count": self_targeted,
        "appearance_counts_by_major_id": dict(sorted(appearance_counter.items())),
        "top3_most_frequent_majors": [{"major_id": mid, "count": c} for mid, c in top3],
        "top3_share_of_all_appearances": round(top3_share, 4),
        "personas": persona_summaries,
    }


def _write_json_report(report: dict[str, Any]) -> None:
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {JSON_OUTPUT_PATH}")


def _write_markdown_report(report: dict[str, Any]) -> None:
    lines = [
        "# 39개 Service Major v2 — 고정 Persona 회귀 진단",
        "",
        "브랜치 `a/major-profiles-v2-38`. `matching_engine_v2.py`의 공식·가중치·최소",
        "Evidence 기준은 전혀 수정하지 않았다 — 있는 그대로 호출한 결과를 그대로 기록한다.",
        "",
        "## 1. 요약",
        "",
        "| 항목 | 값 |",
        "|---|---:|",
        f"| Persona 수 | {report['persona_count']} |",
        f"| 전체 Major 수 | {report['total_major_count']} |",
        f"| 최소 1회 추천 후보가 된 Major 수 | {report['coverage_appeared_major_count']} |",
        f"| 한 번도 후보가 안 된 Major | {', '.join(report['coverage_never_appeared_major_ids']) or '(없음)'} |",
        f"| 자기 전공 Top-3 적중 | {report['self_major_top3_hit_count']} / {report['self_major_top3_targeted_count']} |",
        f"| 상위 3개 Major의 전체 노출 점유율 | {report['top3_share_of_all_appearances']:.1%} |",
        "",
        "## 2. 가장 자주 노출된 Major 3개",
        "",
        "| major_id | 노출 횟수 |",
        "|---|---:|",
    ]
    for row in report["top3_most_frequent_majors"]:
        lines.append(f"| {row['major_id']} | {row['count']} |")

    lines += ["", "## 3. Persona별 상세", "", "| persona_id | target | self 적중 | 관련성 높음 | 함께 탐색 |", "|---|---|---|---|---|"]
    for p in report["personas"]:
        lines.append(
            f"| {p['persona_id']} | {', '.join(p['target_major_ids']) or '(대조군)'} | "
            f"{p['self_major_in_relevant'] if p['self_major_in_relevant'] is not None else '—'} | "
            f"{', '.join(p['relevant_major_ids']) or '(없음)'} | "
            f"{', '.join(p['explore_together_major_ids']) or '(없음)'} |"
        )
    lines.append("")
    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    report = build_report()
    _write_json_report(report)
    _write_markdown_report(report)


if __name__ == "__main__":
    use_utf8_stdout()
    main()
