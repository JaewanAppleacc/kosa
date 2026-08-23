"""Context Routing 2인 Human Review 상태 로더/Validator — 2026-08-23 Trait Ontology
v2(2.5단계) §10.

`v2_direct_probe_review_store.py`와 완전히 같은 패턴을 Context Routing Blueprint 3개
(15개 Option)에 대해 그대로 반복한다 — 파일도, 스키마(`QuestionReviewEntry`/
`OptionReviewEntry`)도 재사용한다. Routing 질문은 Trait Signal이 구조적으로 없기
때문에(`ContextRoutingBlueprint`의 model_validator가 이미 강제) `team_reviewed` 승격
전제 조건을 v2 Direct Probe처럼 별도로 검증할 필요가 없다 — 이 모듈은 Key 집합
일치만 검증한다."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import TypeAdapter

from src.data.questions.context_routing_blueprints import CONTEXT_ROUTING_BLUEPRINTS
from src.schemas.v2_direct_probe_review import OptionReviewEntry, QuestionReviewEntry

_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "reviews"
ROUTING_QUESTION_REVIEW_PATH = _DATA_DIR / "v2_context_routing_question_review_status.json"
ROUTING_OPTION_REVIEW_PATH = _DATA_DIR / "v2_context_routing_option_review_status.json"

_QUESTION_ADAPTER: TypeAdapter[list[QuestionReviewEntry]] = TypeAdapter(list[QuestionReviewEntry])
_OPTION_ADAPTER: TypeAdapter[list[OptionReviewEntry]] = TypeAdapter(list[OptionReviewEntry])


class RoutingReviewStatusValidationError(ValueError):
    """검토 상태 파일의 Key 집합이 실제 Context Routing Blueprint 목록과 다를 때."""


def load_routing_question_review_entries(
    path: Path = ROUTING_QUESTION_REVIEW_PATH,
) -> list[QuestionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _QUESTION_ADAPTER.validate_python(raw)


def load_routing_option_review_entries(path: Path = ROUTING_OPTION_REVIEW_PATH) -> list[OptionReviewEntry]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return _OPTION_ADAPTER.validate_python(raw)


def validate_routing_review_status_files(
    *,
    question_path: Path = ROUTING_QUESTION_REVIEW_PATH,
    option_path: Path = ROUTING_OPTION_REVIEW_PATH,
) -> None:
    question_entries = load_routing_question_review_entries(question_path)
    option_entries = load_routing_option_review_entries(option_path)

    expected_blueprint_ids = {b.blueprint_id for b in CONTEXT_ROUTING_BLUEPRINTS}
    question_blueprint_ids = [e.blueprint_id for e in question_entries]
    if len(question_blueprint_ids) != len(set(question_blueprint_ids)):
        raise RoutingReviewStatusValidationError(f"{question_path}: blueprint_id가 중복됐다: {question_blueprint_ids}")
    if set(question_blueprint_ids) != expected_blueprint_ids:
        missing = expected_blueprint_ids - set(question_blueprint_ids)
        extra = set(question_blueprint_ids) - expected_blueprint_ids
        raise RoutingReviewStatusValidationError(
            f"{question_path}: 실제 Context Routing Blueprint 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )

    expected_option_keys = {
        (b.blueprint_id, m.role_id) for b in CONTEXT_ROUTING_BLUEPRINTS for m in b.option_mappings
    }
    option_keys = [(e.blueprint_id, e.role_id) for e in option_entries]
    if len(option_keys) != len(set(option_keys)):
        raise RoutingReviewStatusValidationError(f"{option_path}: (blueprint_id, role_id)가 중복됐다: {option_keys}")
    if set(option_keys) != expected_option_keys:
        missing = expected_option_keys - set(option_keys)
        extra = set(option_keys) - expected_option_keys
        raise RoutingReviewStatusValidationError(
            f"{option_path}: 실제 Context Routing Option 목록과 일치하지 않는다"
            f"(빠짐: {sorted(missing)}, 불필요: {sorted(extra)})"
        )
