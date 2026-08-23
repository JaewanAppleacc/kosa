"""V2 Direct Probe 2인 Human Review 상태 로더/Validator — 2026-08-23 Trait Ontology
v2(2.3단계) §4.

`data/reviews/v2_direct_probe_question_review_status.json`(질문 14개)과
`data/reviews/v2_direct_probe_option_review_status.json`(선택지 70개)을 읽고, 다음을
검증한다.

- 두 파일이 실제 Blueprint 목록(`V2_DIRECT_PROBE_BLUEPRINTS`)과 정확히 일치하는
  Key 집합을 갖는가(빠짐·중복 없음).
- `V2DirectProbeBlueprint.review_status`가 `"team_reviewed"`로 이미 승격된 항목이
  있다면, 그 Blueprint의 질문 단위 검토와 5개 선택지 단위 검토가 전부 실제로
  두 검토자 모두 APPROVE인 상태인가("한쪽만 승인했는데 이미 승격된" 불일치를 잡는다).

이 모듈은 검토 결과를 스스로 채우거나 승격시키지 않는다 — 오직 읽고 검증만 한다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS
from src.schemas.v2_direct_probe_review import OptionReviewEntry, QuestionReviewEntry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews"
QUESTION_REVIEW_PATH = _DATA_DIR / "v2_direct_probe_question_review_status.json"
OPTION_REVIEW_PATH = _DATA_DIR / "v2_direct_probe_option_review_status.json"

_QUESTION_ADAPTER: TypeAdapter[list[QuestionReviewEntry]] = TypeAdapter(list[QuestionReviewEntry])
_OPTION_ADAPTER: TypeAdapter[list[OptionReviewEntry]] = TypeAdapter(list[OptionReviewEntry])


class ReviewStatusValidationError(ValueError):
    """검토 상태 파일 자체가 구조적으로 잘못됐거나(중복·누락 Key, 잘못된 enum 값 —
    Pydantic이 먼저 잡는다), 이미 team_reviewed로 승격된 항목의 실제 두 검토자 상태가
    승격 조건을 만족하지 못할 때."""


def load_question_review_entries(path: Path = QUESTION_REVIEW_PATH) -> list[QuestionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _QUESTION_ADAPTER.validate_python(raw)


def load_option_review_entries(path: Path = OPTION_REVIEW_PATH) -> list[OptionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _OPTION_ADAPTER.validate_python(raw)


def validate_review_status_files(
    *,
    question_path: Path = QUESTION_REVIEW_PATH,
    option_path: Path = OPTION_REVIEW_PATH,
) -> None:
    """§4 Validator. 문제가 없으면 조용히 반환한다(Fail-Fast — 문제가 있으면 예외).
    이 함수 실행 자체는 어떤 검토 결과도 대신 채우거나 승격시키지 않는다."""

    question_entries = load_question_review_entries(question_path)
    option_entries = load_option_review_entries(option_path)

    expected_blueprint_ids = {b.blueprint_id for b in V2_DIRECT_PROBE_BLUEPRINTS}
    question_blueprint_ids = [e.blueprint_id for e in question_entries]
    if len(question_blueprint_ids) != len(set(question_blueprint_ids)):
        raise ReviewStatusValidationError(f"{question_path}: blueprint_id가 중복됐다: {question_blueprint_ids}")
    if set(question_blueprint_ids) != expected_blueprint_ids:
        missing = expected_blueprint_ids - set(question_blueprint_ids)
        extra = set(question_blueprint_ids) - expected_blueprint_ids
        raise ReviewStatusValidationError(
            f"{question_path}: 실제 Blueprint 목록과 일치하지 않는다(빠짐: {sorted(missing)}, "
            f"불필요: {sorted(extra)})"
        )

    expected_option_keys = {
        (b.blueprint_id, m.role_id) for b in V2_DIRECT_PROBE_BLUEPRINTS for m in b.option_mappings
    }
    option_keys = [(e.blueprint_id, e.role_id) for e in option_entries]
    if len(option_keys) != len(set(option_keys)):
        raise ReviewStatusValidationError(f"{option_path}: (blueprint_id, role_id)가 중복됐다: {option_keys}")
    if set(option_keys) != expected_option_keys:
        missing = expected_option_keys - set(option_keys)
        extra = set(option_keys) - expected_option_keys
        raise ReviewStatusValidationError(
            f"{option_path}: 실제 Option 목록과 일치하지 않는다(빠짐: {sorted(missing)}, "
            f"불필요: {sorted(extra)})"
        )

    question_by_id = {e.blueprint_id: e for e in question_entries}
    options_by_blueprint: dict[str, list[OptionReviewEntry]] = {}
    for e in option_entries:
        options_by_blueprint.setdefault(e.blueprint_id, []).append(e)

    for blueprint in V2_DIRECT_PROBE_BLUEPRINTS:
        if blueprint.review_status != "team_reviewed":
            continue
        # §4: 이미 승격된 항목은 질문 단위와 모든 선택지 단위가 전부 실제로 두 검토자
        # 모두 APPROVE(final_status == TEAM_REVIEWED)여야 한다 — 하나라도 아니면
        # "team_reviewed로 승격됐지만 실제로는 검토가 끝나지 않은" 불일치다.
        question_entry = question_by_id[blueprint.blueprint_id]
        if question_entry.final_status != "TEAM_REVIEWED":
            raise ReviewStatusValidationError(
                f"{blueprint.blueprint_id}: Blueprint.review_status는 'team_reviewed'이지만 "
                f"질문 단위 검토는 아직 TEAM_REVIEWED가 아니다(reviewer_1={question_entry.reviewer_1_status}, "
                f"reviewer_2={question_entry.reviewer_2_status})"
            )
        for option_entry in options_by_blueprint[blueprint.blueprint_id]:
            if option_entry.final_status != "TEAM_REVIEWED":
                raise ReviewStatusValidationError(
                    f"{blueprint.blueprint_id}/{option_entry.role_id}: Blueprint.review_status는 "
                    f"'team_reviewed'이지만 이 선택지 검토는 아직 TEAM_REVIEWED가 아니다"
                    f"(reviewer_1={option_entry.reviewer_1_status}, reviewer_2={option_entry.reviewer_2_status})"
                )
