"""Canonical Major Group ↔ Canonical Major Bridge Loader — 2026-08-24 지시서
(Bridge 계약) §4.

이 모듈은 `data/master/canonical_major_group_bridge.draft.jsonl`을 읽고,
`data/canonical_major_groups.draft.jsonl`(42개 Group 정본)과
`data/master/canonical_majors.jsonl`(10개 Major 정본) 두 쪽 모두와 대조해
Fail-Fast로 검증한다. Pydantic 모델(`CanonicalMajorGroupBridgeEntry`)은 한 행
안에서만 판단 가능한 규칙을 강제하고, 이 모듈은 파일 전체·다른 정본과 대조해야
하는 규칙(중복 Key, 존재하지 않는 Group/Major, 완결성)을 강제한다 —
`canonical_major_group_draft_loader.py`/`context_pack_registry.py`와 같은 계층
분리 원칙이다.

**아직 Runtime에 연결하지 않는다** — 이 Loader를 호출하는 API·Matching 코드는
없다(지시서 §3). 검증 실패 시 예외를 던질 뿐 아무것도 자동으로 고치거나
승인하지 않는다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from src.engines.canonical_mapper import load_canonical_majors
from src.schemas.canonical_major_group_bridge import CanonicalMajorGroupBridgeEntry
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIDGE_DRAFT_PATH = _REPO_ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl"
DEFAULT_CANONICAL_MAJORS_PATH = _REPO_ROOT / "data" / "master" / "canonical_majors.jsonl"

# 예체능 4개 Group — A 결정사항(outputs/handoff/academyinfo_a_decisions.md §3)과
# 정확히 같은 4개다. 이 목록을 이 모듈이 직접 들고 있는 이유: Bridge 검증은
# "이 4개는 EXCLUDED_RECOMMENDATION이어야 한다"를 Fail-Fast로 강제해야 하는데,
# 그 대상 목록 자체가 별도 정본이 없다(§3 문서가 산문으로만 명시했다) — 여기서
# 코드로 고정해 재발을 막는다(테스트로도 이 목록과 문서를 대조한다).
ARTS_EXCLUDED_GROUP_IDS = frozenset({"fine_arts_design", "music", "performing_media_arts", "sports_dance"})


class BridgeValidationError(ValueError):
    """개별 행이 아니라 Bridge 파일 전체 수준의 구조 오류(중복 Key, 존재하지 않는
    Group/Major 참조, 완결성 위반)."""


class BridgeLoadReport:
    """로드 결과 + 완결성 감사 요약. 실제 검증은 `load_canonical_major_group_bridge()`가
    이미 Fail-Fast로 끝냈으므로, 이 객체는 "성공적으로 로드된 뒤"의 요약 통계만
    담는다(감사 가능성, 지시서 §4 "42개 Group 전체가 ... 감사 가능")."""

    def __init__(self, entries: list[CanonicalMajorGroupBridgeEntry]) -> None:
        self.entries = entries

    def group_ids_covered(self) -> set[str]:
        return {e.canonical_major_group_id for e in self.entries}

    def major_ids_covered(self) -> set[str]:
        return {e.canonical_major_id for e in self.entries if e.canonical_major_id is not None}

    def entries_by_status(self, status: str) -> list[CanonicalMajorGroupBridgeEntry]:
        return [e for e in self.entries if e.mapping_status == status]

    def entries_for_major(self, major_id: str) -> list[CanonicalMajorGroupBridgeEntry]:
        return [e for e in self.entries if e.canonical_major_id == major_id]

    def entries_for_group(self, group_id: str) -> list[CanonicalMajorGroupBridgeEntry]:
        return [e for e in self.entries if e.canonical_major_group_id == group_id]


def _raw_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_canonical_major_group_bridge(
    bridge_path: Path | None = None, *, group_draft_path: Path | None = None, majors_path: Path | None = None,
) -> BridgeLoadReport:
    """지시서 §4의 Fail-Fast 규칙을 전부 강제한 뒤 `BridgeLoadReport`를 돌려준다.
    하나라도 위반하면 `BridgeValidationError`(또는 Pydantic의 `ValidationError`를
    감싼 것)를 던진다 — 조용히 걸러내지 않는다."""

    resolved_bridge_path = bridge_path or DEFAULT_BRIDGE_DRAFT_PATH
    raw_rows = _raw_rows(resolved_bridge_path)

    entries: list[CanonicalMajorGroupBridgeEntry] = []
    for i, row in enumerate(raw_rows):
        try:
            entries.append(CanonicalMajorGroupBridgeEntry.model_validate(row))
        except PydanticValidationError as exc:
            raise BridgeValidationError(f"{resolved_bridge_path}:{i + 1}번째 행 검증 실패 — {exc}") from exc

    known_group_ids = {g.canonical_major_id for g in load_canonical_major_groups_draft(group_draft_path)}
    known_major_ids = {m.major_id for m in load_canonical_majors(majors_path or DEFAULT_CANONICAL_MAJORS_PATH)}

    # Group ID가 42개 초안에 실제로 존재하는지.
    unknown_group_refs = {e.canonical_major_group_id for e in entries} - known_group_ids
    if unknown_group_refs:
        raise BridgeValidationError(f"42개 Group 초안에 없는 canonical_major_group_id: {sorted(unknown_group_refs)}")

    # canonical_major_id가 기존 10개 정본에 실제로 존재하는지.
    unknown_major_refs = {e.canonical_major_id for e in entries if e.canonical_major_id is not None} - known_major_ids
    if unknown_major_refs:
        raise BridgeValidationError(f"기존 10개 Major 정본에 없는 canonical_major_id: {sorted(unknown_major_refs)}")

    # 중복 Bridge Key 차단 — (group_id, major_id) 쌍이 유일해야 한다. major_id가
    # None인 UNMAPPED/EXCLUDED 행도 같은 group_id로 두 번 나오면 안 된다(뭘 감사해야
    # 할지 모호해진다).
    seen_keys: set[tuple[str, str | None]] = set()
    for e in entries:
        key = (e.canonical_major_group_id, e.canonical_major_id)
        if key in seen_keys:
            raise BridgeValidationError(f"중복 Bridge Key: {key}")
        seen_keys.add(key)

    # major_id가 None인 행(UNMAPPED 전용)이 있는 Group은 그 행 하나만 가져야 한다 —
    # "이 Group은 후보가 없다"는 선언과 "이 Group은 이런 후보가 있다"는 선언이
    # 동시에 존재하면 감사 시 어느 쪽이 최종 판단인지 알 수 없다.
    for group_id in {e.canonical_major_group_id for e in entries}:
        rows = [e for e in entries if e.canonical_major_group_id == group_id]
        none_status = {r.mapping_status for r in rows if r.canonical_major_id is None}
        if none_status and len(rows) > 1:
            raise BridgeValidationError(
                f"{group_id!r}: canonical_major_id가 None인 행과 다른 후보 행이 함께 존재한다"
                f"(None 행은 그 Group에 유일한 행이어야 한다) — {[r.mapping_status for r in rows]}"
            )

    # 예체능 4개 Group은 추천 가능 상태로 저장 불가 — EXCLUDED_RECOMMENDATION 아닌
    # 상태(EVIDENCED/REVIEW_REQUIRED/UNMAPPED)로 이 4개가 등장하면 Fail.
    for e in entries:
        if e.canonical_major_group_id in ARTS_EXCLUDED_GROUP_IDS and e.mapping_status != "EXCLUDED_RECOMMENDATION":
            raise BridgeValidationError(
                f"예체능 Group {e.canonical_major_group_id!r}는 EXCLUDED_RECOMMENDATION이어야 한다"
                f"(현재 {e.mapping_status!r}) — 추천 가능 상태로 저장할 수 없다"
            )

    # 42개 Group 전체가 최소 한 번은 등장해야 감사 가능하다.
    missing_groups = known_group_ids - {e.canonical_major_group_id for e in entries}
    if missing_groups:
        raise BridgeValidationError(f"Bridge에 전혀 등장하지 않는 Group(감사 불가): {sorted(missing_groups)}")

    # 기존 10개 Major 전체가 최소 하나의 Bridge 후보를 가져야 한다(지시서 §4 "모든
    # 기존 10개 Major에 최소 하나의 Bridge 후보가 있거나, 없으면 그 사실이 UNMAPPED로
    # 명시됨" — 이 Bridge 데이터는 10개 전부를 실제로 커버하도록 설계했으므로, "없으면
    # UNMAPPED로 명시" 분기는 아직 쓰이지 않는다. 나중에 Major가 추가되고 후보가 없는
    # 채로 남으면 이 검증이 즉시 잡아낸다).
    majors_without_any_bridge = known_major_ids - {e.canonical_major_id for e in entries if e.canonical_major_id}
    if majors_without_any_bridge:
        raise BridgeValidationError(
            f"Bridge 후보가 하나도 없는 기존 Major(명시적 UNMAPPED 필요): {sorted(majors_without_any_bridge)}"
        )

    return BridgeLoadReport(entries)
