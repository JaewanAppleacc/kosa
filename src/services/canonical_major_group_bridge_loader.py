"""Canonical Major Group ↔ Canonical Major Bridge Loader — 2026-08-24 지시서
(Bridge 계약) §4, a/canonical-major-bridge-scope 지시서 §2(Scope 교차 검증).

이 모듈은 `data/master/canonical_major_group_bridge.draft.jsonl`을 읽고,
`data/canonical_major_groups.draft.jsonl`(42개 Group 정본)과
`data/master/canonical_majors.jsonl`(10개 Major 정본) 두 쪽 모두와 대조해
Fail-Fast로 검증한다. Pydantic 모델(`CanonicalMajorGroupBridgeEntry`)은 한 행
안에서만 판단 가능한 규칙을 강제하고, 이 모듈은 파일 전체·다른 정본과 대조해야
하는 규칙(중복 Key, 존재하지 않는 Group/Major, 완결성, Scope 소계열 코드가 실제
대학알리미 코드표·그 Group의 코드 목록에 속하는지)을 강제한다 —
`canonical_major_group_draft_loader.py`/`context_pack_registry.py`와 같은 계층
분리 원칙이다.

**아직 Runtime에 연결하지 않는다** — 이 Loader를 호출하는 API·Matching 코드는
없다(지시서 §3). 검증 실패 시 예외를 던질 뿐 아무것도 자동으로 고치거나
승인하지 않는다."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from src.engines.canonical_mapper import load_canonical_majors
from src.schemas.canonical_major_group_bridge import CanonicalMajorGroupBridgeEntry
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIDGE_DRAFT_PATH = _REPO_ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl"
DEFAULT_CANONICAL_MAJORS_PATH = _REPO_ROOT / "data" / "master" / "canonical_majors.jsonl"
# A 결정사항(outputs/handoff/academyinfo_a_decisions.md §1) — 전국 학과 후보의 정본
# 조사연도는 2025다. Scope 소계열 코드도 같은 연도 코드표로 검증해야 Group 쪽
# (`canonical_major_group_draft_loader.py`가 읽는 2025 소계열 코드)과 기준이 어긋나지 않는다.
DEFAULT_SMALL_SERIES_CODE_TABLE_PATH = (
    _REPO_ROOT / "data" / "academyinfo_raw" / "2025" / "codes" / "getCodeBySmallSeries.jsonl.gz"
)

# 예체능 4개 Group — A 결정사항(outputs/handoff/academyinfo_a_decisions.md §3)과
# 정확히 같은 4개다. 이 목록을 이 모듈이 직접 들고 있는 이유: Bridge 검증은
# "이 4개는 EXCLUDED_RECOMMENDATION이어야 한다"를 Fail-Fast로 강제해야 하는데,
# 그 대상 목록 자체가 별도 정본이 없다(§3 문서가 산문으로만 명시했다) — 여기서
# 코드로 고정해 재발을 막는다(테스트로도 이 목록과 문서를 대조한다).
ARTS_EXCLUDED_GROUP_IDS = frozenset({"fine_arts_design", "music", "performing_media_arts", "sports_dance"})


class BridgeValidationError(ValueError):
    """개별 행이 아니라 Bridge 파일 전체 수준의 구조 오류(중복 Key, 존재하지 않는
    Group/Major 참조, 완결성 위반)."""


class BridgeScopeValidationError(BridgeValidationError):
    """2026-08-24 a/canonical-major-bridge-scope 지시서 §2 — Scope 필드가 다른
    정본(대학알리미 158개 소계열 코드표, 그 Group 자신의 소계열 목록)과 맞지 않을 때.
    `BridgeValidationError`의 하위 타입이라 기존에 `BridgeValidationError`만 잡던
    호출부도 그대로 잡는다. 오류 메시지에는 group_id·major_id·코드값만 담고, 질문
    원문·사용자 데이터·API Key는 절대 포함하지 않는다(이 Loader가 다루는 데이터
    자체에 애초에 그런 값이 없다 — Bridge는 순수 분류 메타데이터다)."""


def load_official_small_series_codes(path: Path | None = None) -> dict[str, str]:
    """대학알리미 표준분류 소계열 158개 공식 코드표(`getCodeBySmallSeries`)를
    `{cdid(코드): cdnm(명칭)}`으로 돌려준다. 이 코드표 자체가 정본이다 — Bridge나
    Group Draft가 아니라 원본 수집 데이터(`data/academyinfo_raw/`)에서 직접 읽는다."""

    resolved = path or DEFAULT_SMALL_SERIES_CODE_TABLE_PATH
    codes: dict[str, str] = {}
    with gzip.open(resolved, "rt", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            codes[row["cdid"]] = row["cdnm"]
    return codes


def validate_bridge_scope_row(
    entry: CanonicalMajorGroupBridgeEntry, *, official_codes: dict[str, str], group_small_series_codes: frozenset[str],
) -> None:
    """2026-08-24 a/canonical-major-bridge-scope 지시서 §2 "Schema 우회(model_construct
    등)에 대비한 Service 방어 검증" — `CanonicalMajorGroupBridgeEntry`의
    `_scope_field_consistency` model_validator와 같은 행 단위 규칙을 Pydantic
    검증에 의존하지 않고 순수 함수로 다시 확인한 뒤, 이 함수만 할 수 있는 교차 검증
    (코드가 실제 158개 공식 코드표에 있는가, 그 Group 자신의 소계열 목록에 속하는가)
    까지 더한다. `model_construct()`로 Pydantic 검증을 건너뛴 값이 들어와도 이 함수는
    여전히 막는다 — `entry`의 필드값만 읽지, Pydantic이 검증을 실제로 실행했다고
    가정하지 않는다."""

    group_id, major_id = entry.canonical_major_group_id, entry.canonical_major_id
    scope_type = entry.scope_type
    included = entry.included_small_series_codes
    excluded = entry.excluded_small_series_codes

    def fail(message: str) -> None:
        raise BridgeScopeValidationError(f"{group_id} -> {major_id}: {message}")

    # ── 행 단위 규칙 재확인(Schema 우회 대비) ──
    for label, codes in (("included_small_series_codes", included), ("excluded_small_series_codes", excluded)):
        if any(not c.strip() for c in codes):
            fail(f"{label}에 공백/빈 문자열 코드가 있다")
        if len(codes) != len(set(codes)):
            fail(f"{label}에 중복 코드가 있다: {codes}")

    if entry.mapping_status == "UNMAPPED" and scope_type is not None:
        fail(f"UNMAPPED는 scope_type을 가질 수 없다(현재 {scope_type!r})")

    if entry.mapping_status == "EXCLUDED_RECOMMENDATION" and scope_type != "EXCLUDED_RECOMMENDATION":
        fail(f"EXCLUDED_RECOMMENDATION 행의 scope_type은 항상 EXCLUDED_RECOMMENDATION이어야 한다(현재 {scope_type!r})")
    if scope_type == "EXCLUDED_RECOMMENDATION" and entry.mapping_status != "EXCLUDED_RECOMMENDATION":
        fail(f"scope_type=EXCLUDED_RECOMMENDATION은 mapping_status도 그래야 한다(현재 {entry.mapping_status!r})")

    if entry.mapping_status in ("EVIDENCED", "REVIEW_REQUIRED") and scope_type is None:
        fail(f"{entry.mapping_status}는 scope_type이 있어야 한다")

    overlap = set(included) & set(excluded)
    if overlap:
        fail(f"included_small_series_codes와 excluded_small_series_codes가 겹친다: {sorted(overlap)}")

    if scope_type == "FULL_GROUP" and (included or excluded):
        fail("FULL_GROUP은 included/excluded_small_series_codes를 동시에 사용하지 않는다")

    if scope_type == "INCLUDED_SMALL_SERIES_ONLY" and not included:
        fail("INCLUDED_SMALL_SERIES_ONLY는 included_small_series_codes가 최소 1개 있어야 한다")

    # ── 교차 검증(이 함수만 할 수 있다 — 다른 정본이 필요하다) ──
    all_codes = set(included) | set(excluded)
    unknown_official = all_codes - official_codes.keys()
    if unknown_official:
        fail(f"대학알리미 공식 소계열 158개 코드표에 없는 코드: {sorted(unknown_official)}")

    not_in_group = all_codes - group_small_series_codes
    if not_in_group:
        fail(f"이 Group({group_id})의 공식 소계열 목록에 속하지 않는 코드: {sorted(not_in_group)}")


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
    small_series_code_table_path: Path | None = None,
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

    groups = load_canonical_major_groups_draft(group_draft_path)
    known_group_ids = {g.canonical_major_id for g in groups}
    group_codes_by_id = {g.canonical_major_id: frozenset(g.included_official_small_series_codes) for g in groups}
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

    # 2026-08-24 a/canonical-major-bridge-scope 지시서 §2 — Scope 필드 교차 검증.
    # `CanonicalMajorGroupBridgeEntry`의 model_validator가 이미 행 단위 규칙을
    # 강제했지만, "Schema 우회(model_construct 등)에 대비한 Service 방어 검증"
    # 요구사항에 따라 여기서 순수 함수로 다시 한 번 확인하고, 이 함수만 할 수 있는
    # 교차 검증(공식 코드표 존재 여부, 그 Group 자신의 소계열 목록 부분집합 여부)을
    # 더한다. Group ID가 42개 초안에 없는 행은 위에서 이미 걸러졌으므로
    # `group_codes_by_id[e.canonical_major_group_id]`는 항상 안전하게 조회된다.
    official_codes = load_official_small_series_codes(small_series_code_table_path)
    for e in entries:
        validate_bridge_scope_row(
            e, official_codes=official_codes, group_small_series_codes=group_codes_by_id[e.canonical_major_group_id],
        )

    return BridgeLoadReport(entries)
