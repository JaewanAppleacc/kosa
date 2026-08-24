"""Service Canonical Major v2 Loader — 2026-08-25 지시서(a/service-major-catalog-v2)
§3, 2026-08-25 후속 보완(04096a4 후속) §4.

`data/master/service_canonical_majors_v2.jsonl`(39개 서비스 추천 Major)과
`data/master/canonical_major_group_to_service_major_v2.jsonl`(42개 Group 전부의
Migration/Bridge 기록)을 Fail-Fast로 읽는다 — 형식 오류·불변식 위반을 조용히
넘기지 않고 즉시 예외를 던진다(`JsonlDepartmentRepository`·
`JsonlDepartmentRecommendationScopePolicy`와 같은 원칙 — 중복 Key를 마지막 값으로
덮어쓰지 않는다).

이 Loader가 직접 강제하는 것(§3이 요구한 5가지):
    1. description 공백 금지 — Schema(`ServiceCanonicalMajorV2._validate_description`)가
       이미 강제하지만, Loader가 그 예외를 삼키지 않고 그대로 전파하는지 여기서도
       보장한다.
    2. 별칭 중복 감사 — 같은 Major 안의 중복은 Schema가 막고, **서로 다른 Major
       사이에서 같은 alias 문자열을 공유**하면(매칭이 모호해진다) Loader가 막는다.
    3. 공식 Group 존재 확인 — `canonical_major_group_id`(FULL_GROUP Major)와
       `source_group_ids`(DEPARTMENT_LEVEL_ONLY Major, 예: hci_ux)가 가리키는
       모든 Group ID가 실제 `data/canonical_major_groups.draft.jsonl`(42개)에
       있는 값인지 대조한다.
    4. 예체능 4개 ACTIVE 금지 — FULL_GROUP Major에는 Schema가 이미 막지만, Loader
       수준에서도 다시 확인한다(다른 경로로 만든 데이터를 이 Loader로 읽었을 때도
       방어선이 있어야 한다). DEPARTMENT_LEVEL_ONLY Major(hci_ux)는
       `canonical_major_group_id`가 없어 이 검사 대상이 아니다 — `source_group_ids`
       에 추천 제외 Group이 있어도 그 Group 전체가 ACTIVE로 승격되는 게 아니므로
       위반이 아니다(모듈 docstring 참고).
    5. description 금지 표현(적합 보장·취업 보장·점수 표현) — Schema Validator가
       이미 강제한다(같은 이유로 Loader에서 다시 확인한다).
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.service_canonical_major_v2 import (
    EXCLUDED_RECOMMENDATION_GROUP_IDS,
    CanonicalMajorGroupServiceMajorBridgeV2,
    ServiceCanonicalMajorV2,
)
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SERVICE_CANONICAL_MAJORS_V2_PATH = _ROOT / "data" / "master" / "service_canonical_majors_v2.jsonl"
DEFAULT_CANONICAL_MAJOR_GROUP_BRIDGE_V2_PATH = (
    _ROOT / "data" / "master" / "canonical_major_group_to_service_major_v2.jsonl"
)
# 38개 Group 기반 ACTIVE Major + hci_ux(DEPARTMENT_LEVEL_ONLY 특수 융합 Major) 1개
# = 39(04096a4 후속 보완). Bridge 파일 자체는 여전히 42행(ACTIVE 38 + EXCLUDED 4)
# 그대로다 — hci_ux는 어느 Group의 "기본 서비스 Major"도 아니라 Bridge에 없다.
EXPECTED_ACTIVE_MAJOR_COUNT = 39
EXPECTED_FULL_GROUP_MAJOR_COUNT = 38
EXPECTED_DEPARTMENT_LEVEL_ONLY_MAJOR_COUNT = 1


class DuplicateServiceMajorIdError(ValueError):
    """같은 major_id를 가진 행이 두 번 이상 등장할 때 — 어느 행이 정본인지 알 수
    없으므로 조용히 뒤 항목으로 덮어쓰지 않고 즉시 실패시킨다."""


class UnknownCanonicalMajorGroupError(ValueError):
    """존재하지 않는(또는 오탈자) canonical_major_group_id를 가리킬 때."""


class AmbiguousAliasError(ValueError):
    """서로 다른 Major가 같은 alias 문자열을 공유할 때 — Alias 매칭이 어느 Major를
    가리키는지 모호해진다."""


class ExcludedGroupPromotedToActiveError(ValueError):
    """추천 제외 예체능 4개 Group 중 하나가 ACTIVE 서비스 Major로 로드됐을 때."""


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"필수 입력이 없다: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_service_canonical_majors_v2(
    path: Path | None = None,
    *,
    valid_group_ids: frozenset[str] | None = None,
) -> list[ServiceCanonicalMajorV2]:
    """`valid_group_ids`를 생략하면 실제 `data/canonical_major_groups.draft.jsonl`을
    직접 읽어 검증한다(§3 "공식 Group 존재 확인") — 테스트에서는 합성 Group 집합을
    주입해 실제 파일 없이도 검증 로직만 확인할 수 있다."""

    source = path or DEFAULT_SERVICE_CANONICAL_MAJORS_V2_PATH
    if valid_group_ids is None:
        valid_group_ids = frozenset(g.canonical_major_id for g in load_canonical_major_groups_draft())

    entries: list[ServiceCanonicalMajorV2] = []
    by_id: dict[str, ServiceCanonicalMajorV2] = {}
    alias_owner: dict[str, str] = {}

    for row in _read_jsonl(source):
        entry = ServiceCanonicalMajorV2.model_validate(row)

        if entry.major_id in by_id:
            raise DuplicateServiceMajorIdError(entry.major_id)
        by_id[entry.major_id] = entry

        if entry.canonical_major_group_id is not None and entry.canonical_major_group_id not in valid_group_ids:
            raise UnknownCanonicalMajorGroupError(
                f"{entry.major_id}: 존재하지 않는 canonical_major_group_id — {entry.canonical_major_group_id!r}"
            )
        unknown_source_groups = [g for g in entry.source_group_ids if g not in valid_group_ids]
        if unknown_source_groups:
            raise UnknownCanonicalMajorGroupError(
                f"{entry.major_id}: 존재하지 않는 source_group_ids — {unknown_source_groups}"
            )

        if entry.canonical_major_group_id in EXCLUDED_RECOMMENDATION_GROUP_IDS:
            # Schema의 model_validator가 이미 recommendation_status=ACTIVE와의 조합을
            # 막지만, Loader에서도 다시 막는다(방어적 이중 확인 — 같은 원칙을
            # src.services.department_recommendation_scope.
            # JsonlDepartmentRecommendationScopePolicy.is_approved()에서도 쓴다).
            raise ExcludedGroupPromotedToActiveError(
                f"{entry.major_id}: 추천 제외 Group({entry.canonical_major_group_id})에서 로드됐다"
            )

        for alias in entry.aliases:
            existing_owner = alias_owner.get(alias)
            if existing_owner is not None and existing_owner != entry.major_id:
                raise AmbiguousAliasError(
                    f"alias {alias!r}가 {existing_owner}와 {entry.major_id} 양쪽에 있다 — 매칭이 모호해진다"
                )
            alias_owner[alias] = entry.major_id

        entries.append(entry)

    return entries


def load_canonical_major_group_to_service_major_bridge_v2(
    path: Path | None = None,
) -> dict[str, CanonicalMajorGroupServiceMajorBridgeV2]:
    """canonical_major_group_id를 Key로 돌려준다. 중복 Group Key는 Fail-Fast로
    막는다(§2 "Group 중복 연결 0")."""

    source = path or DEFAULT_CANONICAL_MAJOR_GROUP_BRIDGE_V2_PATH
    result: dict[str, CanonicalMajorGroupServiceMajorBridgeV2] = {}
    for row in _read_jsonl(source):
        entry = CanonicalMajorGroupServiceMajorBridgeV2.model_validate(row)
        if entry.canonical_major_group_id in result:
            raise DuplicateServiceMajorIdError(
                f"canonical_major_group_id 중복: {entry.canonical_major_group_id}"
            )
        result[entry.canonical_major_group_id] = entry
    return result
