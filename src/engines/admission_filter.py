"""입결 비교 가능성 필터 (작업자 C 소유) — 설계안 §18, C 지시서 §3.

강제하는 규칙은 두 개다.

1. **같은 `data_comparability_group`끼리만 한 결과에 담는다.** 학년도·전형·전형유형·
   지표가 다른 자료를 하나의 성적 순위로 합치면, 화면에서는 그럴듯한 줄세우기가 되지만
   근거가 없는 값이 된다.
2. **합격 가능성을 단정하는 값을 만들지 않는다.** 이 모듈은 주어진 자료를 고르고 묶을
   뿐, 새 점수를 계산하지 않는다.

`AdmissionReference.data_comparability_group`은 데이터에 이미 들어 있는 필드지만, 사람이
손으로 채우면 오타 한 글자로 서로 다른 자료가 같은 그룹이 된다. 그래서 값을 `derive()`로
만들고, 적재 시점에 저장된 값과 파생 값이 같은지 검사한다.
"""

from __future__ import annotations

from collections import defaultdict

from src.schemas.major import AdmissionReference


class ComparabilityViolation(Exception):
    """비교 불가능한 자료가 한 결과에 섞였을 때."""


def derive_comparability_group(
    admission_year: int, admission_type: str, admission_track: str, score_metric: str
) -> str:
    """비교 가능성을 결정하는 네 축을 그대로 이어 붙인다.

    네 축인 이유: 학년도가 다르면 응시집단이 다르고, 전형(수시/정시)과 전형유형(교과/
    종합/논술 등)이 다르면 선발 기준 자체가 다르며, 지표(백분위 70%컷 / 등급 50%컷 등)가
    다르면 숫자의 뜻이 다르다. 넷 중 하나라도 다르면 같은 축에 올릴 수 없다.
    """

    parts = [
        str(admission_year),
        admission_type.strip(),
        admission_track.strip(),
        score_metric.strip(),
    ]
    if not all(parts):
        raise ValueError(f"비교 그룹 축에 빈 값이 있다: {parts}")
    return "|".join(parts)


def comparability_group_of(reference: AdmissionReference) -> str:
    return derive_comparability_group(
        reference.admission_year,
        reference.admission_type,
        reference.admission_track,
        reference.score_metric,
    )


def validate_group_field(references: list[AdmissionReference]) -> list[str]:
    """저장된 `data_comparability_group`이 파생 값과 어긋난 행을 찾아낸다.

    예외를 던지지 않고 목록을 돌려주는 이유는 데이터 품질 검사(지시서 §3 "데이터 누락,
    중복, 타입, 출처, 기준일을 자동 검사한다")가 전체 행을 한 번에 훑고 보고해야 하기
    때문이다.
    """

    problems: list[str] = []
    for reference in references:
        expected = comparability_group_of(reference)
        if reference.data_comparability_group != expected:
            problems.append(
                f"{reference.department_id} {reference.admission_year}: "
                f"data_comparability_group={reference.data_comparability_group!r}이 "
                f"파생값 {expected!r}과 다르다"
            )
    return problems


def group_by_comparability(
    references: list[AdmissionReference],
) -> dict[str, list[AdmissionReference]]:
    grouped: dict[str, list[AdmissionReference]] = defaultdict(list)
    for reference in references:
        grouped[reference.data_comparability_group].append(reference)
    return dict(grouped)


def assert_single_group(references: list[AdmissionReference]) -> None:
    """한 리스트 안에 그룹이 둘 이상이면 즉시 실패시킨다.

    Repository·MCP Tool이 결과를 내보내기 직전에 호출한다. 검사를 반환값이 아니라 예외로
    둔 이유는, 이 조건이 깨진 결과는 화면에 나가면 안 되기 때문이다 — 조용히 걸러내면
    사용자는 일부만 보이는 목록을 전체로 오해한다.
    """

    groups = {r.data_comparability_group for r in references}
    if len(groups) > 1:
        raise ComparabilityViolation(
            "비교 불가능한 입결 자료가 한 결과에 섞였다: " + ", ".join(sorted(groups))
        )


def select_group(
    references: list[AdmissionReference], preferred_group: str | None = None
) -> tuple[str, list[AdmissionReference]]:
    """비교 가능한 그룹 하나를 골라 그 그룹만 돌려준다.

    `preferred_group`이 주어지면 그 그룹만, 없으면 **가장 최근 학년도 → 자료 수가 많은
    순 → 그룹명 순**으로 하나를 고른다. 여러 그룹을 이어 붙여 돌려주지 않는다.
    """

    if not references:
        return ("", [])

    grouped = group_by_comparability(references)
    if preferred_group is not None:
        return (preferred_group, grouped.get(preferred_group, []))

    def sort_key(item: tuple[str, list[AdmissionReference]]) -> tuple[int, int, str]:
        name, rows = item
        return (-max(r.admission_year for r in rows), -len(rows), name)

    name, rows = sorted(grouped.items(), key=sort_key)[0]
    return (name, rows)


def sort_within_group(
    references: list[AdmissionReference], by: str = "score_70_cut"
) -> list[AdmissionReference]:
    """한 그룹 안에서만 정렬한다. 그룹이 섞여 있으면 정렬하지 않고 실패시킨다.

    값이 없는 행(`None`)은 뒤로 보낸다 — 0으로 취급하면 "성적이 가장 낮은 학과"로 잘못
    읽힌다.
    """

    if by not in {"score_50_cut", "score_70_cut"}:
        raise ValueError(f"정렬 기준은 score_50_cut 또는 score_70_cut만 허용한다: {by!r}")
    assert_single_group(references)
    return sorted(
        references,
        key=lambda r: (getattr(r, by) is None, -(getattr(r, by) or 0.0), r.department_id),
    )


def verified_only(references: list[AdmissionReference]) -> list[AdmissionReference]:
    """`review_status="verified"`인 자료만 남긴다.

    draft 자료를 화면 비교에 쓰지 않기 위한 것이다. 초안 단계 수치가 확정 수치와 같은
    목록에 섞이면, 뒤에 정정돼도 이미 사용자가 본 뒤가 된다.
    """

    return [r for r in references if r.review_status == "verified"]
