"""Service Canonical Major v2 Catalog 생성 — 2026-08-25 지시서(a/service-major-
catalog-v2) §1/§2/§4, 2026-08-25 후속 보완(04096a4 후속) §1/§2/§3.

42개 Canonical Major Group(`data/canonical_major_groups.draft.jsonl`, 분류
Ontology 초안) 중 추천 제외 예체능 4개(fine_arts_design/music/
performing_media_arts/sports_dance)를 뺀 38개를 서비스 추천 후보 Major로 확정하고,
여기에 Group 기반이 아닌 특수 융합 Major 1개(hci_ux)를 더해 다음 두 파일을 만든다.

    - data/master/service_canonical_majors_v2.jsonl (39행 — FULL_GROUP 38 +
      DEPARTMENT_LEVEL_ONLY 1)
    - data/master/canonical_major_group_to_service_major_v2.jsonl (42행,
      Group 전부에 대한 Migration/Bridge — hci_ux는 어느 Group의 "기본 서비스
      Major"도 아니라 여기 없다, ACTIVE 38 + EXCLUDED_RECOMMENDATION 4는 그대로)

새로 만들어내는 값이 없다 — 모든 필드는 다음 네 정본에서만 가져온다.

    1. `data/canonical_major_groups.draft.jsonl` — Group label/description/
       included_official_small_series_codes(공식 소계열 코드) 그대로.
    2. `data/master/canonical_majors.jsonl`(기존 10개 Canonical Major) — Group ID가
       기존 Major와 겹치면(직접 동일 ID 또는 지시서가 명시한 business→
       business_administration/mechanical_transport→mechanical_engineering Bridge)
       그 Major의 label/description/aliases/keywords를 그대로 재사용한다(§1 "기존
       10개 ID·설명은 가능한 한 보존"). hci_ux도 이 파일에서 label/description/
       aliases/keywords를 완전히 그대로 재사용한다(04096a4 후속 §1).
    3. 대학알리미 공식 표준분류 소계열 코드표(`getCodeBySmallSeries`,
       `data/academyinfo_raw/2025/codes/getCodeBySmallSeries.jsonl.gz`) — 기존
       Major와 안 겹치는 30개 Group의 keywords는 그 Group에 실제로 속한 공식
       소계열 이름을 그대로 쓴다(임의로 지어내지 않는다).
    4. `data/master/canonical_major_group_bridge.draft.jsonl` — hci_ux의
       `source_group_ids`(computer_science/fine_arts_design)는 이 파일에 이미
       실제로 기록된 두 행(computer_science Group=REVIEW_REQUIRED·scope_type=
       DEPARTMENT_REVIEW_REQUIRED, fine_arts_design Group=EXCLUDED_RECOMMENDATION)
       에서 그대로 가져온다 — 둘 다 "Group 전체를 hci_ux에 넘긴다"는 근거가 아니라
       "학과 단위로만 검토 가능하다"는 근거다(04096a4 후속 §2, 아래
       `_build_hci_ux_entry()` 참고).

design(기존 10개 중 1개)은 이번 39개에 들어가지 않는다 — 추천 제외 Group
(fine_arts_design)에 해당하고, hci_ux처럼 학과 단위 예외를 둘 근거가 아직 없다.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.schemas.canonical_major_group import CanonicalMajorGroupDraft  # noqa: E402
from src.schemas.service_canonical_major_v2 import (  # noqa: E402
    EXCLUDED_RECOMMENDATION_GROUP_IDS,
    CanonicalMajorGroupServiceMajorBridgeV2,
    ServiceCanonicalMajorV2,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft  # noqa: E402

CANONICAL_MAJORS_PATH = ROOT / "data" / "master" / "canonical_majors.jsonl"
SMALL_SERIES_CODE_TABLE_PATH = ROOT / "data" / "academyinfo_raw" / "2025" / "codes" / "getCodeBySmallSeries.jsonl.gz"
OUTPUT_CATALOG_PATH = ROOT / "data" / "master" / "service_canonical_majors_v2.jsonl"
OUTPUT_BRIDGE_PATH = ROOT / "data" / "master" / "canonical_major_group_to_service_major_v2.jsonl"

CATALOG_VERSION = "service_canonical_major_v2.0"

# 지시서 §1이 명시한 유일한 이름 변경 Bridge — Group ID와 기존 Major ID 표기가
# 다른 2개뿐이다. 나머지 겹치는 4개(computer_science/media_communication/
# industrial_engineering/psychology/life_science/education)는 Group ID == 기존
# Major ID라 별도 Bridge가 필요 없다(직접 재사용).
RENAME_BRIDGE: dict[str, str] = {
    "business": "business_administration",
    "mechanical_transport": "mechanical_engineering",
}

# 04096a4 후속 보완 — hci_ux는 Group 기반이 아니라 특수 융합 Major다. 아래 두 Group
# 은 실제로 data/master/canonical_major_group_bridge.draft.jsonl에 hci_ux 후보로
# 기록돼 있지만 **둘 다 "Group 전체를 넘긴다"는 근거가 아니다** — computer_science는
# REVIEW_REQUIRED(공식 소계열 158개 중 HCI·UX·인터랙션에 정확히 대응하는 코드 없음),
# fine_arts_design은 그 자체가 추천 제외 Group이다. 참고용 출처로만 남긴다
# (source_group_ids) — 이 목록에 있다는 사실 자체가 그 Group 소속 학과를 자동으로
# hci_ux에 편입시키는 근거가 아니다.
HCI_UX_SOURCE_GROUP_IDS: list[str] = ["computer_science", "fine_arts_design"]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_small_series_code_names() -> dict[str, str]:
    with gzip.open(SMALL_SERIES_CODE_TABLE_PATH, "rt", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return {row["cdid"]: row["cdnm"].strip() for row in rows}


def _description_from_group(group: CanonicalMajorGroupDraft) -> str:
    """Group의 공식 description(예: "우리말과 한국문학을 읽고 쓰는 분야")을 학생
    화면 문장 관례("...전공 분야입니다.")로 그대로 옮긴다 — 내용 자체는 한 글자도
    지어내지 않는다."""

    text = group.description.strip()
    if text.endswith("분야"):
        text = text[: -len("분야")].rstrip()
    return f"{text} 전공 분야입니다."


def _aliases_from_label(label: str) -> list[str]:
    parts = [p.strip() for p in label.split("·") if p.strip()]
    # 원 label 전체도 한 표기로 포함한다(예: "산업디자인" 같은 검색어가 label
    # 부분과 다를 수 있는 경우를 대비 — 여기서는 label 자체·구성 조각만 쓴다).
    ordered = list(dict.fromkeys([*parts, label.strip()]))
    return ordered


def _build_new_entry(
    group: CanonicalMajorGroupDraft, code_names: dict[str, str],
) -> dict[str, Any]:
    keywords = [code_names[c] for c in group.included_official_small_series_codes if c in code_names]
    return {
        "major_id": group.canonical_major_id,
        "label": group.label,
        "description": _description_from_group(group),
        "aliases": _aliases_from_label(group.label),
        "keywords": keywords,
        "canonical_major_group_id": group.canonical_major_id,
        "source_group_ids": [],
        "mapping_scope": "FULL_GROUP",
        "recommendation_status": "ACTIVE",
        "official_source_urls": list(group.official_source_urls),
        "catalog_version": CATALOG_VERSION,
    }


def _build_carried_over_entry(
    group: CanonicalMajorGroupDraft, old_major: dict[str, Any],
) -> dict[str, Any]:
    """기존 10개 Canonical Major와 겹치는 Group — label/description/aliases/
    keywords를 전부 그대로 보존한다(§1). official_source_urls만 Group의 공식
    출처(data.go.kr OpenAPI + academyinfo.go.kr)와 기존 Major의 career.go.kr
    출처를 합쳐 더 넓힌다 — 둘 다 실제로 존재하는 공식 출처이기 때문이다."""

    merged_urls = list(dict.fromkeys([*group.official_source_urls, old_major["source_url"]]))
    return {
        "major_id": old_major["major_id"],
        "label": old_major["label"],
        "description": old_major["description"],
        "aliases": list(old_major["aliases"]),
        "keywords": list(old_major["keywords"]),
        "canonical_major_group_id": group.canonical_major_id,
        "source_group_ids": [],
        "mapping_scope": "FULL_GROUP",
        "recommendation_status": "ACTIVE",
        "official_source_urls": merged_urls,
        "catalog_version": CATALOG_VERSION,
    }


def _build_hci_ux_entry(old_major: dict[str, Any]) -> dict[str, Any]:
    """04096a4 후속 보완 §1/§2 — hci_ux를 ACTIVE 서비스 Major로 복구하되, 어느
    Group에도 통째로 속하지 않는다는 사실을 Schema에 명시적으로 남긴다
    (mapping_scope=DEPARTMENT_LEVEL_ONLY, canonical_major_group_id=None). label/
    description/aliases/keywords는 기존 canonical_majors.jsonl에서 완전히 그대로
    가져온다(§1 "완전 보존") — 이 함수는 한 글자도 새로 짓지 않는다."""

    return {
        "major_id": old_major["major_id"],
        "label": old_major["label"],
        "description": old_major["description"],
        "aliases": list(old_major["aliases"]),
        "keywords": list(old_major["keywords"]),
        "canonical_major_group_id": None,
        "source_group_ids": list(HCI_UX_SOURCE_GROUP_IDS),
        "mapping_scope": "DEPARTMENT_LEVEL_ONLY",
        "recommendation_status": "ACTIVE",
        "official_source_urls": [old_major["source_url"]],
        "catalog_version": CATALOG_VERSION,
    }


def build_catalog_and_bridge(
    groups: list[CanonicalMajorGroupDraft], old_majors: list[dict[str, Any]], code_names: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    old_majors_by_id = {m["major_id"]: m for m in old_majors}

    catalog_rows: list[dict[str, Any]] = []
    bridge_rows: list[dict[str, Any]] = []

    for group in groups:
        group_id = group.canonical_major_id

        if group_id in EXCLUDED_RECOMMENDATION_GROUP_IDS:
            bridge_rows.append(
                {
                    "canonical_major_group_id": group_id,
                    "service_major_id": None,
                    "recommendation_status": "EXCLUDED_RECOMMENDATION",
                    "decision_reason": (
                        f"공식 예체능 계열 Group({group.label}) — 분류 Ontology·관심 Context에서는 "
                        "그대로 유지하되 전공 추천 후보에서는 제외한다(2026-08-25 지시서 목표)."
                    ),
                }
            )
            continue

        if group_id in RENAME_BRIDGE:
            service_major_id = RENAME_BRIDGE[group_id]
            old_major = old_majors_by_id[service_major_id]
            catalog_rows.append(_build_carried_over_entry(group, old_major))
            decision_reason = (
                f"기존 Canonical Major '{service_major_id}'({old_major['label']})를 그대로 재사용한다 — "
                f"Group ID 표기('{group_id}')만 다를 뿐 같은 전공 분야를 가리킨다(2026-08-25 지시서 §1 "
                "명시 Bridge)."
            )
        elif group_id in old_majors_by_id:
            service_major_id = group_id
            old_major = old_majors_by_id[group_id]
            catalog_rows.append(_build_carried_over_entry(group, old_major))
            decision_reason = (
                f"기존 Canonical Major '{service_major_id}'와 Group ID가 동일하다 — 그대로 재사용한다"
                "(2026-08-25 지시서 §1 \"기존 10개 ID·설명은 가능한 한 보존\")."
            )
        else:
            service_major_id = group_id
            catalog_rows.append(_build_new_entry(group, code_names))
            decision_reason = (
                f"기존 10개 Canonical Major와 겹치지 않는 Group({group.label}) — 공식 소계열 "
                f"{group.included_official_small_series_codes}을 근거로 새 서비스 Major를 명시적으로 "
                "생성한다(2026-08-25 지시서 §1)."
            )

        bridge_rows.append(
            {
                "canonical_major_group_id": group_id,
                "service_major_id": service_major_id,
                "recommendation_status": "ACTIVE",
                "decision_reason": decision_reason,
            }
        )

    # 04096a4 후속 보완 §1/§2 — hci_ux는 42개 Group 순회 결과가 아니다(어느
    # Group도 이 Major를 통째로 넘기지 않았다). Bridge에는 추가하지 않는다 — Group의
    # "기본 서비스 Major"가 아니기 때문이다(§2 "computer_science Group의 기본
    # 서비스 Major는 computer_science 유지").
    catalog_rows.append(_build_hci_ux_entry(old_majors_by_id["hci_ux"]))

    _remove_ambiguous_cross_major_aliases(catalog_rows)

    catalog_rows.sort(key=lambda r: r["major_id"])
    bridge_rows.sort(key=lambda r: r["canonical_major_group_id"])
    return catalog_rows, bridge_rows


def _remove_ambiguous_cross_major_aliases(catalog_rows: list[dict[str, Any]]) -> None:
    """`_aliases_from_label()`이 label을 "·"로 쪼개다 보면(예: "건축·토목·환경" →
    "환경") 서로 다른 Group의 label에 우연히 같은 조각 단어가 나타날 수 있다(실측:
    "환경"이 civil_architecture·earth_environment 양쪽에 나온다) — 그런 alias는
    어느 Major를 가리키는지 모호하므로, 그 alias 하나만 두 Major 모두에서 뺀다(전체
    label 자체는 `_aliases_from_label()`이 항상 마지막에 별도로 넣어 두므로 목록이
    비지 않는다). Loader의 별칭 중복 감사(§3)가 실제로 이 문제를 잡아서 여기서
    고친다 — 감사 자체를 느슨하게 만들지 않는다."""

    owner_count: dict[str, set[str]] = {}
    for row in catalog_rows:
        for alias in row["aliases"]:
            owner_count.setdefault(alias, set()).add(row["major_id"])

    ambiguous = {alias for alias, owners in owner_count.items() if len(owners) > 1}
    if not ambiguous:
        return
    for row in catalog_rows:
        row["aliases"] = [a for a in row["aliases"] if a not in ambiguous]


def _canonical_dumps(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(_canonical_dumps(row) + "\n")
    tmp.replace(path)


def validate_invariants(
    catalog_rows: list[dict[str, Any]], bridge_rows: list[dict[str, Any]], groups: list[CanonicalMajorGroupDraft],
) -> None:
    """§2 불변식 — 하나라도 깨지면 아무 파일도 쓰지 않는다(Fail-Fast)."""

    group_ids = {g.canonical_major_id for g in groups}
    if len(groups) != 42:
        raise ValueError(f"Group 총 개수가 42가 아니다: {len(groups)}")

    bridge_group_ids = [r["canonical_major_group_id"] for r in bridge_rows]
    if set(bridge_group_ids) != group_ids:
        missing = group_ids - set(bridge_group_ids)
        extra = set(bridge_group_ids) - group_ids
        raise ValueError(f"Bridge Group 목록이 실제 42개와 다르다 — 누락: {missing}, 알 수 없는 값: {extra}")
    if len(bridge_group_ids) != len(set(bridge_group_ids)):
        raise ValueError("Bridge에 Group 중복 연결이 있다")

    active_bridge = [r for r in bridge_rows if r["recommendation_status"] == "ACTIVE"]
    excluded_bridge = [r for r in bridge_rows if r["recommendation_status"] == "EXCLUDED_RECOMMENDATION"]
    if len(active_bridge) != 38:
        raise ValueError(f"ACTIVE Group 수가 38이 아니다: {len(active_bridge)}")
    if len(excluded_bridge) != 4:
        raise ValueError(f"EXCLUDED_RECOMMENDATION Group 수가 4가 아니다: {len(excluded_bridge)}")
    if {r["canonical_major_group_id"] for r in excluded_bridge} != EXCLUDED_RECOMMENDATION_GROUP_IDS:
        raise ValueError("EXCLUDED_RECOMMENDATION Group 목록이 지시서 4개와 다르다")

    catalog_major_ids = [r["major_id"] for r in catalog_rows]
    if len(catalog_rows) != 39:
        raise ValueError(f"서비스 Major 총 개수가 39가 아니다: {len(catalog_rows)}")
    if len(catalog_major_ids) != len(set(catalog_major_ids)):
        raise ValueError("서비스 Major ID 중복이 있다")

    full_group_rows = [r for r in catalog_rows if r["mapping_scope"] == "FULL_GROUP"]
    department_level_rows = [r for r in catalog_rows if r["mapping_scope"] == "DEPARTMENT_LEVEL_ONLY"]
    if len(full_group_rows) != 38:
        raise ValueError(f"FULL_GROUP 서비스 Major 수가 38이 아니다: {len(full_group_rows)}")
    if len(department_level_rows) != 1:
        raise ValueError(f"DEPARTMENT_LEVEL_ONLY 서비스 Major 수가 1이 아니다: {len(department_level_rows)}")
    if department_level_rows[0]["major_id"] != "hci_ux":
        raise ValueError(f"DEPARTMENT_LEVEL_ONLY Major가 hci_ux가 아니다: {department_level_rows[0]['major_id']}")

    # 04096a4 후속 §2 — hci_ux는 어느 Group의 "기본 서비스 Major"도 아니다. Bridge의
    # ACTIVE service_major_id 집합은 FULL_GROUP Catalog 행과 정확히 같아야 하고
    # (부분집합이 아니라 동일 집합 — computer_science는 여전히 computer_science
    # 자신에게만 연결된다), hci_ux는 그 집합에 나타나면 안 된다.
    bridge_active_major_ids = {r["service_major_id"] for r in active_bridge}
    full_group_major_ids = {r["major_id"] for r in full_group_rows}
    if bridge_active_major_ids != full_group_major_ids:
        raise ValueError("Bridge의 ACTIVE service_major_id 집합과 Catalog의 FULL_GROUP major_id 집합이 다르다")
    if "hci_ux" in bridge_active_major_ids:
        raise ValueError("hci_ux가 Bridge에 어느 Group의 ACTIVE service_major_id로도 등장하면 안 된다")

    # Pydantic Schema로 다시 한번 전체를 검증한다 — 여기서 실패하면 원인이 그대로 전파된다.
    for row in catalog_rows:
        ServiceCanonicalMajorV2.model_validate(row)
    for row in bridge_rows:
        CanonicalMajorGroupServiceMajorBridgeV2.model_validate(row)


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()

    groups = load_canonical_major_groups_draft()
    old_majors = _read_jsonl(CANONICAL_MAJORS_PATH)
    code_names = _load_small_series_code_names()

    catalog_rows, bridge_rows = build_catalog_and_bridge(groups, old_majors, code_names)
    validate_invariants(catalog_rows, bridge_rows, groups)

    _write_jsonl_atomic(OUTPUT_CATALOG_PATH, catalog_rows)
    _write_jsonl_atomic(OUTPUT_BRIDGE_PATH, bridge_rows)

    preserved = [
        r["major_id"] for r in catalog_rows
        if r["major_id"] in {m["major_id"] for m in old_majors}
    ]
    full_group_count = sum(1 for r in catalog_rows if r["mapping_scope"] == "FULL_GROUP")
    department_level_count = sum(1 for r in catalog_rows if r["mapping_scope"] == "DEPARTMENT_LEVEL_ONLY")
    print("Service Canonical Major v2 Catalog 생성 완료")
    print(f"  서비스 Major(ACTIVE) 전체: {len(catalog_rows)}건")
    print(f"    Group 기반(FULL_GROUP): {full_group_count}건")
    print(f"    특수 융합(DEPARTMENT_LEVEL_ONLY): {department_level_count}건")
    print(f"  추천 제외(EXCLUDED_RECOMMENDATION) Group: {sum(1 for r in bridge_rows if r['recommendation_status'] == 'EXCLUDED_RECOMMENDATION')}건")
    print(f"  기존 10개 중 보존됨: {sorted(preserved)} ({len(preserved)}개)")
    print(f"  기존 10개 중 미포함(design 예상): {sorted(set(m['major_id'] for m in old_majors) - set(preserved))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
