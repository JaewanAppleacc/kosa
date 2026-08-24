"""전국 학과 1,072건 Production Master 전환 — 2026-08-25 지시서(a/national-master-
promotion-final-wiring) §1·§2·§3.

입력은 오직 다음 두 개뿐이다 — academyinfo API를 다시 호출하지 않고, 학교/학과 이름
문자열로 조인하지 않는다.

    1. `data/academyinfo_work/2025/promotion_dry_run/national_master_promotion_
       candidates.jsonl` — 이미 Gate를 전부 통과한 1,072건 승격 후보(§1 검증 대상).
    2. `data/academyinfo_work/2025/departments.normalized.jsonl` — 확정 24,422행
       Snapshot. `region`/`campus`/`admission_unit`은 여기서만 조인한다(offering_id
       재계산 — `schl_id`+`source_schl_mjr_id`가 Offering Identity v2의 유일 키다).

후보 한 건이라도 Snapshot에서 못 찾으면 즉시 Fail-Fast하고 Master를 쓰지 않는다.
`old_department_id`는 감사용으로만 참고하고 새 Repository Key로 쓰지 않는다(§2).

기존 Master 35건은 삭제하지 않는다 — `data/archive/departments_legacy_demo_35.jsonl`로
읽기 전용 보존하고, SHA-256·행 수를 Manifest에 남긴 뒤에만 `data/master/departments.jsonl`을
새 1,072건으로 원자적으로 교체한다(§3 "35건과 병합해 1,107건으로 만들지 않는다").

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_promote_national_departments_master.py
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

CANDIDATES_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "promotion_dry_run" / (
    "national_master_promotion_candidates.jsonl"
)
SNAPSHOT_PATH = ROOT / "data" / "academyinfo_work" / "2025" / "departments.normalized.jsonl"
MASTER_PATH = ROOT / "data" / "master" / "departments.jsonl"
ARCHIVE_PATH = ROOT / "data" / "archive" / "departments_legacy_demo_35.jsonl"
ARCHIVE_MANIFEST_PATH = ROOT / "data" / "archive" / "departments_legacy_demo_35.manifest.json"
PROMOTION_MANIFEST_PATH = ROOT / "data" / "master" / "departments_promotion_manifest.json"

EXPECTED_CANDIDATE_COUNT = 1072
EXPECTED_MAJOR_BREAKDOWN = {
    "business_administration": 271,
    "media_communication": 133,
    "life_science": 134,
    "mechanical_engineering": 114,
    "computer_science": 209,
    "education": 78,
    "industrial_engineering": 53,
    "psychology": 80,
    "hci_ux": 0,
    "design": 0,
}
_ARTS_SPORTS_LARGE_SERIES_CODE = "C"


class PromotionValidationError(ValueError):
    """§1 입력 검증 실패 — Master를 쓰지 않고 즉시 중단한다."""


class SnapshotJoinError(ValueError):
    """§2 "한 건이라도 조인 실패 시 Fail-Fast" — 조인 안 된 offering_id만 메시지에 담는다
    (학과명·대학명 등 다른 필드는 담지 않는다, 원본 학생 데이터가 아니라 재현 가능한
    식별자이므로 안전하다)."""


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


def validate_candidates(candidates: list[dict[str, Any]]) -> None:
    """§1 — Section 1 입력 검증. 전부 통과해야만 §2 조인으로 넘어간다."""

    if len(candidates) != EXPECTED_CANDIDATE_COUNT:
        raise PromotionValidationError(
            f"후보 행 수가 {EXPECTED_CANDIDATE_COUNT}가 아니다: {len(candidates)}건"
        )

    offering_ids = [c["offering_id"] for c in candidates]
    duplicate_offering_ids = sorted(oid for oid, count in Counter(offering_ids).items() if count > 1)
    if duplicate_offering_ids:
        raise PromotionValidationError(f"offering_id 중복 {len(duplicate_offering_ids)}건: {duplicate_offering_ids}")

    missing_canonical_major = [c["offering_id"] for c in candidates if not c.get("canonical_major_id")]
    if missing_canonical_major:
        raise PromotionValidationError(f"canonical_major_id 누락 {len(missing_canonical_major)}건")

    bad_status = sorted({c["department_status"] for c in candidates} - {"EXISTING", "NEW"})
    if bad_status:
        raise PromotionValidationError(f"EXISTING/NEW 이외의 department_status 발견: {bad_status}")

    missing_source_url = [c["offering_id"] for c in candidates if not (c.get("source_url") or "").strip()]
    if missing_source_url:
        raise PromotionValidationError(f"source_url 누락 {len(missing_source_url)}건")

    major_breakdown = dict(Counter(c["canonical_major_id"] for c in candidates))
    if major_breakdown != {k: v for k, v in EXPECTED_MAJOR_BREAKDOWN.items() if v > 0}:
        raise PromotionValidationError(
            f"Major별 후보 수가 기대값과 다르다 — 실제: {major_breakdown} / 기대: "
            f"{ {k: v for k, v in EXPECTED_MAJOR_BREAKDOWN.items() if v > 0} }"
        )


def build_snapshot_index(snapshot_rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """§2 — Snapshot 24,422행을 offering_id로 색인한다. Snapshot 자체는 이미
    24,422행 전부가 유일한 (schl_id, source_schl_mjr_id) 쌍이라는 것을 dry run이
    이미 검증했다(BLOCKED_DUPLICATE_ID 0건) — 여기서는 그 사실을 다시 이용만 한다."""

    index: dict[str, dict[str, Any]] = {}
    for row in snapshot_rows:
        offering_id = generate_offering_id(row["schl_id"], row["source_schl_mjr_id"])
        index[offering_id] = row
    return index


def join_and_build_department_rows(
    candidates: list[dict[str, Any]], snapshot_index: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """§2 — region/campus/admission_unit을 Snapshot에서 조인하고 공개 Department
    Schema로 재배열한다. 한 건이라도 조인 실패·계약학과·예체능·상태 불일치가 나오면
    즉시 Fail-Fast한다(Master를 쓰지 않는다)."""

    missing_join = [c["offering_id"] for c in candidates if c["offering_id"] not in snapshot_index]
    if missing_join:
        raise SnapshotJoinError(
            f"Snapshot에서 조인되지 않는 offering_id {len(missing_join)}건: {sorted(missing_join)}"
        )

    contract_hits: list[str] = []
    arts_hits: list[str] = []
    inactive_status_hits: list[str] = []
    rows: list[dict[str, Any]] = []

    for candidate in candidates:
        snapshot = snapshot_index[candidate["offering_id"]]

        if snapshot.get("major_character_name") in _CONTRACT_MAJOR_CHARACTERS:
            contract_hits.append(candidate["offering_id"])
        large_series_code = (snapshot.get("official_classification") or {}).get("large_series_code")
        if large_series_code == _ARTS_SPORTS_LARGE_SERIES_CODE:
            arts_hits.append(candidate["offering_id"])
        if snapshot.get("department_status") not in ("EXISTING", "NEW"):
            inactive_status_hits.append(candidate["offering_id"])

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

    if contract_hits:
        raise PromotionValidationError(f"계약학과/산업체위탁 혼입 {len(contract_hits)}건: {sorted(contract_hits)}")
    if arts_hits:
        raise PromotionValidationError(f"예체능(대계열 C) 혼입 {len(arts_hits)}건: {sorted(arts_hits)}")
    if inactive_status_hits:
        raise PromotionValidationError(
            f"Snapshot department_status가 EXISTING/NEW가 아닌 행 {len(inactive_status_hits)}건: "
            f"{sorted(inactive_status_hits)}"
        )

    return rows


def validate_department_schema(rows: list[dict[str, Any]]) -> list[Department]:
    """§2 "1,072건 전부 Department.model_validate() 통과". 실패하면 어느 offering_id인지
    포함해 즉시 던진다."""

    validated: list[Department] = []
    for row in rows:
        try:
            validated.append(Department.model_validate(row))
        except Exception as exc:  # noqa: BLE001 — Fail-Fast, 원인을 그대로 전파한다.
            raise PromotionValidationError(f"{row['department_id']}: Department 검증 실패 — {exc}") from exc
    return validated


def archive_existing_master(master_path: Path, archive_path: Path, manifest_path: Path) -> dict[str, Any]:
    """§3 — 기존 35건을 삭제하지 않고 읽기 전용 Archive로 보존한다. 이미 같은 내용으로
    Archive가 있으면 다시 만들지 않는다(멱등) — 있는데 내용이 다르면(같은 스크립트를
    두 번째 승격 라운드에서 실행하는 사고 등) 절대 덮어쓰지 않고 즉시 실패한다."""

    if not master_path.exists():
        raise PromotionValidationError(f"기존 Master가 없다: {master_path}")

    current_bytes = master_path.read_bytes()
    current_sha256 = hashlib.sha256(current_bytes).hexdigest()
    current_row_count = len([line for line in current_bytes.decode("utf-8").splitlines() if line.strip()])

    if archive_path.exists():
        archived_sha256 = _sha256(archive_path)
        if archived_sha256 != current_sha256:
            raise PromotionValidationError(
                "data/archive/departments_legacy_demo_35.jsonl이 이미 존재하는데 현재 "
                "data/master/departments.jsonl과 SHA-256이 다르다 — 다른 내용을 덮어쓰지 않는다."
            )
    else:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        archive_path.write_bytes(current_bytes)
        archive_path.chmod(0o444)

    manifest = {
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "source_path": "data/master/departments.jsonl",
        "archive_path": "data/archive/departments_legacy_demo_35.jsonl",
        "row_count": current_row_count,
        "sha256": current_sha256,
        "note": (
            "2026-08-25 전국 학과 1,072건 Production Master 전환 — 기존 데모 35건을 "
            "삭제하지 않고 읽기 전용으로 보존한다. 새 Production Master(1,072건)와 절대 "
            "병합되지 않는다."
        ),
    }
    _write_text_atomic(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest


def main(argv: list[str] | None = None) -> int:
    use_utf8_stdout()

    candidates = _read_jsonl(CANDIDATES_PATH)
    validate_candidates(candidates)
    candidates.sort(key=lambda c: c["offering_id"])

    snapshot_rows = _read_jsonl(SNAPSHOT_PATH)
    snapshot_index = build_snapshot_index(snapshot_rows)

    department_rows = join_and_build_department_rows(candidates, snapshot_index)
    validated_departments = validate_department_schema(department_rows)
    if len(validated_departments) != EXPECTED_CANDIDATE_COUNT:
        raise PromotionValidationError(
            f"검증 통과 행 수가 {EXPECTED_CANDIDATE_COUNT}가 아니다: {len(validated_departments)}건"
        )

    archive_manifest = archive_existing_master(MASTER_PATH, ARCHIVE_PATH, ARCHIVE_MANIFEST_PATH)

    department_rows_sorted = sorted(department_rows, key=lambda r: r["department_id"])
    _write_jsonl_atomic(MASTER_PATH, department_rows_sorted)
    new_sha256 = _sha256(MASTER_PATH)

    promotion_manifest = {
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "source_candidates_path": str(CANDIDATES_PATH.relative_to(ROOT)),
        "source_snapshot_path": str(SNAPSHOT_PATH.relative_to(ROOT)),
        "master_path": "data/master/departments.jsonl",
        "master_row_count": len(department_rows_sorted),
        "master_sha256": new_sha256,
        "major_breakdown": dict(Counter(r["canonical_major_id"] for r in department_rows_sorted).most_common()),
        "archived_legacy_master": archive_manifest,
        "note": (
            "기존 데모 35건은 data/archive/departments_legacy_demo_35.jsonl로 보존되고, "
            "data/master/departments.jsonl은 이 1,072건으로 완전히 교체됐다(병합 아님)."
        ),
    }
    _write_text_atomic(
        PROMOTION_MANIFEST_PATH, json.dumps(promotion_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    print("전국 학과 Production Master 전환 완료")
    print(f"  Master 행 수: {len(department_rows_sorted)}")
    print(f"  Master SHA-256: {new_sha256}")
    print(f"  Archive(기존 35건) SHA-256: {archive_manifest['sha256']}")
    for major_id, count in promotion_manifest["major_breakdown"].items():
        print(f"  {major_id}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
