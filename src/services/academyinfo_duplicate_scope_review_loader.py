"""대학알리미 중복 과정 승인 정본 Loader와 패킷 교차검증."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.schemas.academyinfo_duplicate_scope_review import AcademyInfoDuplicateScopeDecision

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DECISION_PATH = _REPO_ROOT / "data" / "reviews" / "academyinfo_duplicate_scope_review_status.jsonl"
DEFAULT_PACKET_PATH = (
    _REPO_ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "duplicate_decision_draft.jsonl"
)

_DECISION_ADAPTER = TypeAdapter(AcademyInfoDuplicateScopeDecision)


class DuplicateAcademyInfoReviewKeyError(ValueError):
    pass


class AcademyInfoReviewPacketMismatchError(ValueError):
    pass


def _read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{line_number}: JSONL 형식 오류") from exc
    return rows


def load_academyinfo_duplicate_scope_decisions(
    decision_path: Path = DEFAULT_DECISION_PATH,
    packet_path: Path = DEFAULT_PACKET_PATH,
) -> list[AcademyInfoDuplicateScopeDecision]:
    decisions = [_DECISION_ADAPTER.validate_python(row) for row in _read_jsonl(decision_path)]
    decision_ids = [decision.candidate_id for decision in decisions]
    if len(decision_ids) != len(set(decision_ids)):
        raise DuplicateAcademyInfoReviewKeyError("중복 과정 승인 정본에 candidate_id 중복이 있다")

    packet_rows = _read_jsonl(packet_path)
    packet_by_id = {row["candidate_id"]: row for row in packet_rows}
    if len(packet_by_id) != len(packet_rows):
        raise DuplicateAcademyInfoReviewKeyError("중복 과정 검수 패킷에 candidate_id 중복이 있다")
    if set(decision_ids) != set(packet_by_id):
        raise AcademyInfoReviewPacketMismatchError("승인 정본과 검수 패킷의 candidate_id 집합이 다르다")

    for decision in decisions:
        packet = packet_by_id[decision.candidate_id]
        if decision.department_id != packet.get("department_id"):
            raise AcademyInfoReviewPacketMismatchError(f"{decision.candidate_id}: department_id 불일치")
        if decision.approved_decision != packet.get("recommended_decision"):
            raise AcademyInfoReviewPacketMismatchError(f"{decision.candidate_id}: 관계 결정 불일치")

        packet_records = {row["source_record_id"]: row for row in packet.get("records", [])}
        decision_records = {row.source_record_id: row for row in decision.records}
        if set(packet_records) != set(decision_records):
            raise AcademyInfoReviewPacketMismatchError(f"{decision.candidate_id}: source_record_id 집합 불일치")
        for source_record_id, reviewed in decision_records.items():
            source = packet_records[source_record_id]
            expected = {
                "schl_mjr_id": reviewed.schl_mjr_id,
                "major_character_name": reviewed.major_character_name,
                "recommendation_scope": reviewed.recommendation_scope,
                "exclusion_reason": reviewed.exclusion_reason,
            }
            actual = {field: source.get(field) for field in expected}
            if actual != expected:
                raise AcademyInfoReviewPacketMismatchError(
                    f"{decision.candidate_id}/{source_record_id}: 승인 범위가 검수 패킷과 다르다"
                )
    return decisions
