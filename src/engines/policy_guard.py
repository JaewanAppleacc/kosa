"""policy_guard.py — 설계안 §27이 정의하는 6개 불변식을 한곳에서 강제한다.

각 규칙은 이미 다른 모듈에서 개별적으로 지켜지지만(§6-3, §11, §24, §5-1/§8, §20),
모듈마다 따로 구현하면 하나를 빠뜨릴 위험이 있어서 이 파일이 최종 방어선 역할을 한다.
`tests/test_policy_guard.py`는 이 6개를 의도적으로 위반하는 입력을 넣어 실제로
막히는지 확인하는 계약 테스트다 (CLAUDE.md: "eval/policy_guard_test.py를 생략하지 않는다").
"""

from __future__ import annotations

from typing import Any, Literal

from src.schemas.assessment_state import AssessmentState
from src.schemas.course import CourseRecommendationItem
from src.schemas.question import GeneratedOption, OptionBlueprint


class PolicyViolation(Exception):
    """policy_guard의 6개 규칙 중 하나라도 위반되면 발생시킨다."""


def guard_trait_in_ontology(trait_id: str, known_trait_ids: set[str]) -> str | None:
    """§6-3: Ontology에 없는 Trait 후보는 UNMAPPED_TRAIT로 저장하고 계산에서 제외한다.

    예외를 던지지 않는다 — UNMAPPED_TRAIT는 정상적으로 발생할 수 있는 상태이므로,
    호출자가 이 반환값을 보고 "계산에 포함시키지 않는다"는 결정을 내려야 한다.
    반환값이 None이면 UNMAPPED_TRAIT라는 뜻이다.
    """

    return trait_id if trait_id in known_trait_ids else None


def guard_role_ids_match_blueprint(
    options: list[GeneratedOption], blueprint: OptionBlueprint
) -> None:
    """§11: LLM이 반환한 Role ID가 Blueprint에 없으면 거부한다."""

    blueprint_role_ids = {role.role_id for role in blueprint.roles}
    for option in options:
        if option.role_id not in blueprint_role_ids:
            raise PolicyViolation(
                f"LLM이 반환한 role_id {option.role_id!r}가 blueprint "
                f"{blueprint.blueprint_id!r}에 없다"
            )


def guard_exactly_five_options(options: list[Any]) -> None:
    """§11: 선택지는 정확히 5개여야 한다."""

    if len(options) != 5:
        raise PolicyViolation(f"선택지는 정확히 5개여야 한다, got {len(options)}")


def guard_llm_call_budget(current_call_count: int, max_calls_per_session: int) -> None:
    """§24: 세션당 LLM 호출 예산을 초과하면 호출 자체를 차단한다."""

    if current_call_count >= max_calls_per_session:
        raise PolicyViolation(
            f"세션 LLM 호출 예산 초과: {current_call_count}/{max_calls_per_session}"
        )


def guard_no_major_signal_in_assessment_state() -> None:
    """§5-1, §8: 전공 관련도·순위를 Assessment Planner 입력으로 전달하지 않는다.

    코드 리뷰로 매번 확인하는 대신, AssessmentState에 major/전공 관련 필드 자체가
    존재하지 않는다는 것을 구조적으로 검증한다 — 필드가 새로 추가되면 이 테스트가 깨진다.
    """

    forbidden_substrings = ("major", "department", "전공", "학과")
    for field_name in AssessmentState.model_fields:
        lowered = field_name.lower()
        if any(token in lowered for token in forbidden_substrings):
            raise PolicyViolation(
                f"AssessmentState에 전공 관련 필드 {field_name!r}가 존재한다 — "
                "Assessment 단계는 전공 순위를 참조하면 안 된다 (§5-1, §8)"
            )


def guard_offered_status_matches_core_category(
    items: list[CourseRecommendationItem], source: Literal["PRE_SURVEY", "POST_OFFERING"]
) -> None:
    """2026-08-24 14차 리뷰: `is_actually_offered`가 `bool`에서 `bool | None`으로
    바뀌면서(§6), "False면 절대 core로 노출하지 않는다"는 예전 docstring 주장이 실제
    코드로 강제되지 않고 있었다 — 이 함수가 그 빈틈을 메운다.

    PRE_SURVEY에서는 검사하지 않는다 — PRE_SURVEY의 `core`는 "실제 개설이 확인된 핵심
    과목"이 아니라 "학생 Trait 근거가 충분한 희망 우선과목"이라는 뜻이라, 개설 여부
    미확정(`is_actually_offered=None`)인 채로 core가 나오는 게 정상이다. POST_OFFERING
    에서만 실제 개설(`is_actually_offered is True`)이 확인된 과목만 core로 노출하도록
    막는다."""

    if source != "POST_OFFERING":
        return
    violating = [i for i in items if i.category == "core" and i.is_actually_offered is not True]
    if violating:
        raise PolicyViolation(
            "POST_OFFERING에서는 실제 개설이 확인된(is_actually_offered=True) 과목만 "
            f"core로 노출할 수 있다 — 위반 subject_id: {[i.subject_id for i in violating]}"
        )


def guard_subject_must_be_offered(
    recommended_subject_ids: list[str], offered_subject_ids: set[str]
) -> None:
    """§20 POST_OFFERING: 학교 파일에 없는 과목을 실제 개설과목처럼 추천하지 않는다."""

    not_offered = [s for s in recommended_subject_ids if s not in offered_subject_ids]
    if not_offered:
        raise PolicyViolation(
            f"학교 개설 목록에 없는 과목을 추천하려 했다: {not_offered}"
        )
