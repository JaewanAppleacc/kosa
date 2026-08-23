"""V2 Direct Probe 2인 Human Review 상태 Validator CLI — 2026-08-23 Trait Ontology
v2(2.3단계) §4.

`data/reviews/v2_direct_probe_question_review_status.json`/
`v2_direct_probe_option_review_status.json`이 실제 Blueprint 구조와 일치하는지,
`team_reviewed`로 승격된 항목이 있다면 그 승격이 실제 두 검토자 상태와 모순되지
않는지 확인한다. 이 스크립트는 검토 상태를 스스로 채우거나 승격시키지 않는다 —
읽기 전용 검증만 한다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/validate_v2_direct_probe_review_status.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from src.services.v2_direct_probe_review_store import (  # noqa: E402
    ReviewStatusValidationError,
    load_option_review_entries,
    load_question_review_entries,
    validate_review_status_files,
)


def main() -> int:
    try:
        validate_review_status_files()
    except ReviewStatusValidationError as exc:
        print(f"[FAIL] {exc}")
        return 1

    questions = load_question_review_entries()
    options = load_option_review_entries()
    q_counts: dict[str, int] = {}
    o_counts: dict[str, int] = {}
    for e in questions:
        q_counts[e.final_status] = q_counts.get(e.final_status, 0) + 1
    for e in options:
        o_counts[e.final_status] = o_counts.get(e.final_status, 0) + 1

    print("[OK] 검토 상태 파일 구조 정상, team_reviewed 승격 불일치 없음.")
    print(f"질문 단위(14개) 상태 분포: {q_counts}")
    print(f"선택지 단위(70개) 상태 분포: {o_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
