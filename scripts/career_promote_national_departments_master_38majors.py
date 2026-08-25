"""전국 학과 → 38개 서비스 Major 기준 Production Master 재생성 —
c/national-departments-38-majors §3.

`scripts/career_promote_national_departments_master.py`(8개 Major·1,072건 라운드)와
같은 원칙(atomic 교체, 기존 Master는 삭제하지 않고 읽기 전용 Archive로 보존, Snapshot
재조인, Fail-Fast)을 따르되, 이번 라운드는 후보 수·Major별 분포가 이 실행 이전에는
알려지지 않은 값이다(38개 Major 전체로 재분류하는 첫 라운드이므로 "기대 분포를
미리 하드코딩"하지 않는다) — 대신 구조적 불변식만 검증한다:

    - offering_id 중복 0
    - canonical_major_id 전부 39개 Service Canonical Major v2(ACTIVE) 중 하나
    - department_status ∈ {EXISTING, NEW}
    - major_character_name이 계약학과/산업체위탁이 아님(재검증 — Dry Run이 이미
      걸렀지만 여기서도 다시 확인한다, "허위 승인 금지"와 같은 이중 확인 원칙)
    - 예체능 대계열(C) 아님(재검증)

기존 Master(현재 1,072건, 8개 Major)는 삭제하지 않고
`data/archive/departments_legacy_1072_8majors.jsonl`로 읽기 전용 보존한 뒤에만
`data/master/departments.jsonl`을 이 라운드의 READY_FOR_PROMOTION 전체로 원자적으로
교체한다(기존 35건 Archive와 같은 원칙 — 병합하지 않는다).

**이 스크립트는 main.py·MajorExplorationService·Matching Engine을 건드리지 않는다**
(지시서 금지 사항) — `data/master/departments.jsonl`만 교체한다. 그 파일을 몇 개
Major까지 노출할지(`DEFAULT_SERVICE_MAJOR_IDS`)는 별도 배선 라운드의 몫이다.

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_promote_national_departments_master_38majors.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_build_national_department_promotion_dry_run import (  # noqa: E402
    _CONTRACT_MAJOR_CHARACTERS,
)
from scripts.career_console import use_utf8_stdout  # noqa: E402
from src.ids import generate_offering_id  # noqa: E402
from src.schemas.major import Department  # noqa: E402
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2  # noqa: E402

DRY_RUN_DIR = ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run"
# Dry Run의 원본 출력(promotion_candidates.jsonl)이 아니라, 그 위에
# career_build_national_master_promotion_candidates.py(a/final-integration-master-
# promotion §6, 이번 라운드에서도 그대로 재사용)가 이미 Master-승격용 필드 이름
# (canonical_major_id 등)으로 재배열해 만든 이 파일을 읽는다 — Gate를 다시
# 계산하지 않는다(그 스크립트가 이미 READY_FOR_PROMOTION만 옮겨 담았다).
CANDIDATES_PATH = DRY_RUN_DIR / "national_master_promotion_candidates.jsonl"
SNAPSHOT_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "departments.normalized.jsonl"
MASTER_PATH = ROOT / "data" / "master" / "departments.jsonl"
ARCHIVE_PATH = ROOT / "data" / "archive" / "departments_legacy_1072_8majors.jsonl"
ARCHIVE_MANIFEST_PATH = ROOT / "data" / "archive" / "departments_legacy_1072_8majors.manifest.json"
PROMOTION_MANIFEST_PATH = ROOT / "data" / "master" / "departments_promotion_manifest_38majors.json"

_ARTS_SPORTS_LARGE_SERIES_CODE = "C"


class PromotionValidationError(ValueError):
    """§1 입력 검증 실패 — Master를 쓰지 않고 즉시 중단한다."""


class SnapshotJoinError(ValueError):
    """한 건이라도 Snapshot에서 조인 실패 시 Fail-Fast(다른 필드는 메시지에 담지
    않는다 — offering_id는 재현 가능한 식별자라 안전하다)."""


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise PromotionValidationError(f"필수 입력이 없다: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_dumps(row: dict[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(_canonical_dumps(row) + "\n")
    tmp.replace(path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    tmp.replace(path)


def validate_candidates(candidates: list[dict[str, Any]], *, active_major_ids: frozenset[str]) -> None:
    if not candidates:
        raise PromotionValidationError("승격 후보가 0건이다 — Dry Run을 먼저 실행했는지 확인하세요.")

    offering_ids = [c["offering_id"] for c in candidates]
    duplicate_offering_ids = sorted(oid for oid, count in Counter(offering_ids).items() if count > 1)
    if duplicate_offering_ids:
        raise PromotionValidationError(f"offering_id 중복 {len(duplicate_offering_ids)}건: {duplicate_offering_ids}")

    missing_canonical_major = [c["offering_id"] for c in candidates if not c.get("canonical_major_id")]
    if missing_canonical_major:
        raise PromotionValidationError(f"canonical_major_id 누락 {len(missing_canonical_major)}건")

    unknown_major = sorted({c["canonical_major_id"] for c in candidates} - active_major_ids)
    if unknown_major:
        raise PromotionValidationError(
            f"39개 Service Canonical Major v2(ACTIVE)에 없는 canonical_major_id: {unknown_major}"
        )

    bad_status = sorted({c["department_status"] for c in candidates} - {"EXISTING", "NEW"})
    if bad_status:
        raise PromotionValidationError(f"EXISTING/NEW 이외의 department_status 발견: {bad_status}")

    missing_source_url = [c["offering_id"] for c in candidates if not (c.get("source_url") or "").strip()]
    if missing_source_url:
        raise PromotionValidationError(f"source_url 누락 {len(missing_source_url)}건")


def build_snapshot_index(snapshot_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for row in snapshot_rows:
        offering_id = generate_offering_id(row["schl_id"], row["source_schl_mjr_id"])
        index[offering_id] = row
    return index


def join_and_build_department_rows(
    candidates: list[dict[str, Any]], snapshot_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    missing_join = [c["offering_id"] for c in candidates if c["offering_id"] not in snapshot_index]
    if missing_join:
        raise SnapshotJoinError(
            f"Snapshot에서 조인되지 않는 offering_id {len(missing_join)}건: {sorted(missing_join)[:20]}"
        )

    arts_hits: list[str] = []
    inactive_status_hits: list[str] = []
    contract_hits: list[str] = []
    rows: list[dict[str, Any]] = []

    for candidate in candidates:
        snapshot = snapshot_index[candidate["offering_id"]]

        large_series_code = (snapshot.get("official_classification") or {}).get("large_series_code")
        if large_series_code == _ARTS_SPORTS_LARGE_SERIES_CODE:
            arts_hits.append(candidate["offering_id"])
        if snapshot.get("department_status") not in ("EXISTING", "NEW"):
            inactive_status_hits.append(candidate["offering_id"])
        # `national_master_promotion_candidates.jsonl`에는 major_character_name이
        # 없다 — Snapshot(24,422행 원본)에만 있다. Dry Run이 이미 이 값으로 계약학과·
        # 산업체위탁을 걸렀지만, 여기서도 Snapshot을 다시 조인한 김에 재검증한다
        # (허위 승인 금지와 같은 이중 확인 원칙).
        if snapshot.get("major_character_name") in _CONTRACT_MAJOR_CHARACTERS:
            contract_hits.append(candidate["offering_id"])

        rows.append(
            {
                "department_id": candidate["offering_id"],
                "university_name": candidate["university_name"],
                "campus": snapshot.get("campus"),
                "region": snapshot.get("region") or "",
                "department_name": candidate["department_name"],
                "college_name": candidate["college_name"],
                "admission_unit": snapshot.get("admission_unit"),
                "department_status": candidate["department_status"],
                "source_svy_year": candidate["source_svy_year"],
                "source_url": candidate["source_url"],
                "canonical_major_id": candidate["canonical_major_id"],
                "department_url": candidate.get("department_url"),
            }
        )

    if arts_hits:
        raise PromotionValidationError(f"예체능(대계열 C) 혼입(재검증) {len(arts_hits)}건: {sorted(arts_hits)[:20]}")
    if inactive_status_hits:
        raise PromotionValidationError(
            f"Snapshot department_status가 EXISTING/NEW가 아닌 행(재검증) {len(inactive_status_hits)}건"
        )
    if contract_hits:
        raise PromotionValidationError(f"계약학과/산업체위탁 혼입(재검증) {len(contract_hits)}건: {sorted(contract_hits)[:20]}")

    return rows


def validate_department_schema(rows: list[dict[str, Any]]) -> list[Department]:
    validated: list[Department] = []
    for row in rows:
        try:
            validated.append(Department.model_validate(row))
        except Exception as exc:  # noqa: BLE001 — Fail-Fast, 원인을 그대로 전파한다.
            raise PromotionValidationError(f"{row['department_id']}: Department 검증 실패 — {exc}") from exc
    return validated


def archive_existing_master(master_path: Path, archive_path: Path, manifest_path: Path) -> dict[str, Any]:
    if not master_path.exists():
        raise PromotionValidationError(f"기존 Master가 없다: {master_path}")

    current_bytes = master_path.read_bytes()
    current_sha256 = hashlib.sha256(current_bytes).hexdigest()
    current_row_count = len([line for line in current_bytes.decode("utf-8").splitlines() if line.strip()])

    if archive_path.exists():
        archived_sha256 = _sha256(archive_path)
        if archived_sha256 != current_sha256:
            raise PromotionValidationError(
                f"{archive_path}이 이미 존재하는데 현재 {master_path}와 SHA-256이 다르다 — "
                "다른 내용을 덮어쓰지 않는다."
            )
    else:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(current_bytes)
        archive_path.chmod(0o444)

    try:
        archive_path_display = str(archive_path.relative_to(ROOT))
    except ValueError:
        archive_path_display = str(archive_path)

    manifest = {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "source_path": "data/master/departments.jsonl",
        "archive_path": archive_path_display,
        "row_count": current_row_count,
        "sha256": current_sha256,
        "note": (
            "2026-08-25 전국 학과 38개 서비스 Major 재분류(c/national-departments-38-majors) "
            "— 기존 8개 Major·1,072건 Master를 삭제하지 않고 읽기 전용으로 보존한다. 새 "
            "Production Master(38개 Major)와 절대 병합되지 않는다."
        ),
    }
    _write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()

    active_major_ids = frozenset(
        m.major_id for m in load_service_canonical_majors_v2() if m.recommendation_status == "ACTIVE"
    )

    candidates = _read_jsonl(CANDIDATES_PATH)
    validate_candidates(candidates, active_major_ids=active_major_ids)
    candidates.sort(key=lambda c: c["offering_id"])

    snapshot_rows = _read_jsonl(SNAPSHOT_PATH)
    snapshot_index = build_snapshot_index(snapshot_rows)

    department_rows = join_and_build_department_rows(candidates, snapshot_index)
    validated_departments = validate_department_schema(department_rows)
    if len(validated_departments) != len(candidates):
        raise PromotionValidationError(
            f"검증 통과 행 수({len(validated_departments)})가 후보 수({len(candidates)})와 다르다"
        )

    archive_manifest = archive_existing_master(MASTER_PATH, ARCHIVE_PATH, ARCHIVE_MANIFEST_PATH)

    department_rows_sorted = sorted(department_rows, key=lambda r: r["department_id"])
    _write_jsonl_atomic(MASTER_PATH, department_rows_sorted)
    new_sha256 = _sha256(MASTER_PATH)

    def _display_path(path: Path) -> str:
        try:
            return str(path.relative_to(ROOT))
        except ValueError:
            return str(path)

    major_breakdown = dict(Counter(r["canonical_major_id"] for r in department_rows_sorted).most_common())
    promotion_manifest = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "source_candidates_path": _display_path(CANDIDATES_PATH),
        "source_snapshot_path": _display_path(SNAPSHOT_PATH),
        "master_path": "data/master/departments.jsonl",
        "master_row_count": len(department_rows_sorted),
        "master_sha256": new_sha256,
        "distinct_major_count": len(major_breakdown),
        "major_breakdown": major_breakdown,
        "archived_legacy_master": archive_manifest,
        "note": (
            "기존 8개 Major·1,072건 Master는 data/archive/departments_legacy_1072_8majors.jsonl로 "
            "보존되고, data/master/departments.jsonl은 이 38개 Major 재분류 결과로 완전히 "
            "교체됐다(병합 아님). main.py/MajorExplorationService/Matching Engine은 이 실행으로 "
            "바뀌지 않는다 — 이 38개 Major를 실제로 API에 노출할지는 별도 배선 라운드의 몫이다."
        ),
    }
    _write_text_atomic(
        PROMOTION_MANIFEST_PATH, json.dumps(promotion_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    print("전국 학과 38개 서비스 Major Production Master 전환 완료")
    print(f"  Master 행 수: {len(department_rows_sorted)}")
    print(f"  Master SHA-256: {new_sha256}")
    print(f"  Archive(기존 1,072건·8개 Major) SHA-256: {archive_manifest['sha256']}")
    print(f"  서로 다른 Major 수: {len(major_breakdown)}")
    for major_id, count in major_breakdown.items():
        print(f"  {major_id}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
