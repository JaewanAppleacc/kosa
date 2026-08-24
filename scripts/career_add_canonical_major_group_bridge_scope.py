"""Canonical Major Group Bridge에 Scope 필드 추가 — 2026-08-24 지시서
(a/canonical-major-bridge-scope) §2/§3.

`data/master/canonical_major_group_bridge.draft.jsonl`(44행)에 `scope_type`/
`included_small_series_codes`/`excluded_small_series_codes`/`scope_decision_reason`/
`scope_review_status` 5개 필드를 추가한다. **Additive 전용** — 기존 필드
(`mapping_status`/`evidence`/`decision_reason`/`boundary_notes`/`review_status`/
`reviewer_id`/`reviewed_at`)는 이름도 값도 절대 바꾸지 않는다. 각 행의 JSON 키
순서도 보존한다(기존 키 뒤에 새 필드만 덧붙인다) — 이 파일을 읽는 다른 도구가
행 순서·기존 필드 위치에 의존하고 있어도 깨지지 않는다.

이 스크립트가 좁히는 Scope는 지시서 §3에 명시된 REVISE 6건뿐이다(사람이 Review UI
에서 REVISE로 판정한 결과, `data/reviews/canonical_major_group_bridge_review_status.
json` — 이 스크립트는 그 파일을 읽지 않는다. 이 스크립트가 아는 REVISE 6건은
지시서 원문 그대로 하드코딩한 값이다). 나머지 38개 APPROVE 행은 기존
Mapping 판단(mapping_status/evidence/decision_reason)을 절대 재해석하지 않고,
`scope_type`만 mapping_status에서 결정론적으로 도출되는 기본값(EVIDENCED/
REVIEW_REQUIRED → FULL_GROUP, EXCLUDED_RECOMMENDATION → EXCLUDED_RECOMMENDATION,
UNMAPPED → None)으로 채운다.

`scope_review_status`는 44행 전부 "draft"로 남긴다 — 기존 Bridge Mapping의
reviewer_1_status(APPROVE/REVISE)가 무엇이든, 그 판정을 이 새 Scope 필드의 승인
상태로 자동 복사하지 않는다(지시서 §3, 안전 규칙 "사람의 APPROVE/REVISE 상태를
자동 변경하지 마세요"와 같은 이유 — 사람은 아직 이 Scope 값 자체를 검토한 적이
없다).

실행(멱등 — 이미 Scope 필드가 있는 행은 그대로 덮어써 결과가 항상 같다):
    PYTHONPATH=. python scripts/career_add_canonical_major_group_bridge_scope.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TypedDict

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.schemas.canonical_major_group_bridge import CanonicalMajorGroupBridgeEntry, ScopeType  # noqa: E402
from src.services.canonical_major_group_bridge_loader import (  # noqa: E402
    DEFAULT_BRIDGE_DRAFT_PATH,
    load_official_small_series_codes,
    validate_bridge_scope_row,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft  # noqa: E402


class ScopeOverride(TypedDict):
    scope_type: ScopeType
    included_small_series_codes: list[str]
    excluded_small_series_codes: list[str]
    scope_decision_reason: str


# 지시서 §3 REVISE 6건 — 소계열 코드는 `data/academyinfo_raw/2025/codes/
# getCodeBySmallSeries.jsonl.gz`(대학알리미 공식 158개 표)에서 직접 이름으로 찾은
# 값이다(추측 금지 원칙 — 코드 확인 방법은 completion report §3 참고).
#   033 경영학, 035 경영정보학, 041 비서, 151 금융·보험학, 152 회계·세무학
#   042 교육학, 043 언어교육, 046 초등교육, 154 유아교육, 155 특수교육
#   102 산업공학, 103 안전공학, 104 방재공학
#   078 기계공학, 080 조선·해양공학, 081 항공·우주공학, 082 철도공학, 083 자동차공학
REVISE_SCOPE_OVERRIDES: dict[tuple[str, str], ScopeOverride] = {
    ("bio_medical_engineering", "life_science"): {
        "scope_type": "DEPARTMENT_REVIEW_REQUIRED",
        "included_small_series_codes": [],
        "excluded_small_series_codes": [],
        "scope_decision_reason": (
            "생명과학(life_science, 기초과학)과 생명공학·의공학(이 Group)을 전공군 단위로 "
            "동일시하지 않는다. 생명공학은 개별 학과 교육과정을 봐야 life_science 후보로 "
            "적절한지 판단할 수 있고, 의공학은 응용 공학 성격이 뚜렷해 별도 전공 분야로 "
            "유지한다 — 소계열 코드 단위로도 자동 확정하지 않고 학과 단위 검토가 필요하다."
        ),
    },
    ("business", "business_administration"): {
        "scope_type": "INCLUDED_SMALL_SERIES_ONLY",
        "included_small_series_codes": ["033"],
        "excluded_small_series_codes": ["035", "041", "151", "152"],
        "scope_decision_reason": (
            "공식 소계열 '경영학'(033)만 business_administration 추천 학과 후보로 포함한다. "
            "이 Group의 나머지 소계열(경영정보학·비서·금융보험학·회계세무학)은 성격이 다른 "
            "세부 전공이라 제외한다 — Group 전체 1,424건을 그대로 경영학 추천 학과로 쓰지 않는다."
        ),
    },
    ("computer_science", "hci_ux"): {
        "scope_type": "DEPARTMENT_REVIEW_REQUIRED",
        "included_small_series_codes": [],
        "excluded_small_series_codes": [],
        "scope_decision_reason": (
            "컴퓨터과학 Group 전체를 HCI·UX로 연결하지 않는다. 대학알리미 158개 공식 소계열에 "
            "'HCI'·'UX'·'인터랙션'에 정확히 대응하는 코드가 없어(REVIEW_REQUIRED 근거 그대로) "
            "소계열 단위로도 범위를 확정할 수 없다 — 학과 공식 교육과정에서 HCI·UX·사용자 "
            "연구·인터랙션 설계 근거가 확인되는 개별 학과만 후속 검토한다. computer_science "
            "-> computer_science(같은 Group, 다른 Major) 연결에는 영향을 주지 않는다."
        ),
    },
    ("education", "education"): {
        "scope_type": "INCLUDED_SMALL_SERIES_ONLY",
        "included_small_series_codes": ["042"],
        "excluded_small_series_codes": ["043", "046", "154", "155"],
        "scope_decision_reason": (
            "공식 소계열 '교육학'(042)만 education 추천 학과 후보로 포함한다. 언어교육·"
            "초등교육·유아교육·특수교육은 교원양성 세부 분야로 성격이 달라 제외한다 — "
            "Group 전체 821건을 자동으로 education 추천 학과에 연결하지 않는다."
        ),
    },
    ("industrial_engineering", "industrial_engineering"): {
        "scope_type": "INCLUDED_SMALL_SERIES_ONLY",
        "included_small_series_codes": ["102"],
        "excluded_small_series_codes": ["103", "104"],
        "scope_decision_reason": (
            "공식 소계열 '산업공학'(102)만 industrial_engineering 추천 학과 후보로 포함한다. "
            "안전공학·방재공학은 제외한다 — Group 전체 343건을 그대로 산업공학 추천 학과로 "
            "쓰지 않는다."
        ),
    },
    ("mechanical_transport", "mechanical_engineering"): {
        "scope_type": "INCLUDED_SMALL_SERIES_ONLY",
        "included_small_series_codes": ["078"],
        "excluded_small_series_codes": ["080", "081", "082", "083"],
        "scope_decision_reason": (
            "공식 소계열 '기계공학'(078)만 mechanical_engineering 추천 학과 후보로 포함한다. "
            "조선·해양공학·항공·우주공학·철도공학·자동차공학은 별도 응용 분야로 제외한다 — "
            "Group 전체 1,112건을 자동으로 기계공학 추천 학과에 연결하지 않는다."
        ),
    },
}


def _default_scope_for(mapping_status: str) -> ScopeOverride | None:
    """REVISE 대상이 아닌 나머지 38개 APPROVE 행의 기본 Scope. 기존 Mapping 판단
    (mapping_status/evidence/decision_reason)은 절대 재해석하지 않는다 — mapping_status
    에서 기계적으로 결정되는 값만 채운다."""

    if mapping_status == "UNMAPPED":
        return None
    if mapping_status == "EXCLUDED_RECOMMENDATION":
        return {
            "scope_type": "EXCLUDED_RECOMMENDATION", "included_small_series_codes": [],
            "excluded_small_series_codes": [], "scope_decision_reason": "",
        }
    # EVIDENCED/REVIEW_REQUIRED이면서 REVISE 대상이 아닌 행 — 기존 evidence가 이미
    # Group 소계열 전체(또는 그 Group의 유일한 실질 소계열)와 직접 일치한다고 판단됐고,
    # 이번 REVISE 6건에도 포함되지 않았으므로 별도 범위 제한 없이 FULL_GROUP으로 둔다.
    return {
        "scope_type": "FULL_GROUP", "included_small_series_codes": [], "excluded_small_series_codes": [],
        "scope_decision_reason": (
            "REVISE 대상이 아니다(2026-08-24 사람 검수 결과 APPROVE) — 기존 evidence·"
            "decision_reason이 이미 Group과 Major의 연결을 근거로 뒷받침하며, 소계열 단위로 "
            "범위를 좁혀야 한다는 검토 의견이 없어 Group 전체를 그대로 범위로 유지한다."
        ),
    }


def _scope_for_row(row: dict) -> ScopeOverride | None:
    key = (row["canonical_major_group_id"], row["canonical_major_id"])
    if key in REVISE_SCOPE_OVERRIDES:
        return REVISE_SCOPE_OVERRIDES[key]
    return _default_scope_for(row["mapping_status"])


def build_scoped_rows(bridge_path: Path | None = None) -> list[dict]:
    resolved = bridge_path or DEFAULT_BRIDGE_DRAFT_PATH
    raw_rows = [
        json.loads(line) for line in resolved.read_text(encoding="utf-8").splitlines() if line.strip()
    ]

    out_rows: list[dict] = []
    for row in raw_rows:
        scope = _scope_for_row(row)
        # dict.update()는 기존 키 순서를 보존하고 새 키만 끝에 덧붙인다(Python 3.7+ 보장) —
        # 기존 7개 필드는 순서·값 그대로, 새 5개 필드만 추가된다.
        merged = dict(row)
        if scope is None:
            merged["scope_type"] = None
            merged["included_small_series_codes"] = []
            merged["excluded_small_series_codes"] = []
            merged["scope_decision_reason"] = ""
        else:
            merged["scope_type"] = scope["scope_type"]
            merged["included_small_series_codes"] = scope["included_small_series_codes"]
            merged["excluded_small_series_codes"] = scope["excluded_small_series_codes"]
            merged["scope_decision_reason"] = scope["scope_decision_reason"]
        # 사람이 아직 이 Scope 값 자체를 검토한 적이 없다 — 절대 "approved"로 자동 승격하지
        # 않는다(안전 규칙, 지시서 §3).
        merged["scope_review_status"] = "draft"
        out_rows.append(merged)
    return out_rows


def _verify(rows: list[dict]) -> None:
    """쓰기 전에 이 스크립트가 만든 값 자체가 Schema·Loader 검증을 통과하는지
    확인한다 — 검증 실패한 파일을 실수로 커밋하지 않기 위한 방어선이다."""

    groups = {g.canonical_major_id: g for g in load_canonical_major_groups_draft()}
    official_codes = load_official_small_series_codes()
    for row in rows:
        entry = CanonicalMajorGroupBridgeEntry.model_validate(row)
        group = groups[entry.canonical_major_group_id]
        validate_bridge_scope_row(
            entry, official_codes=official_codes,
            group_small_series_codes=frozenset(group.included_official_small_series_codes),
        )


def main() -> None:
    use_utf8_stdout()
    rows = build_scoped_rows()
    _verify(rows)

    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    DEFAULT_BRIDGE_DRAFT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {DEFAULT_BRIDGE_DRAFT_PATH} ({len(rows)}행, Scope 필드 추가)")


if __name__ == "__main__":
    main()
