"""대학알리미 공식 코드 기반 판정 — 지시서 §7.

**공식 코드값만 본다.** 학교명·학과명 문자열로 추측하지 않는다. 근거는
`rationale_c/07-academyinfo-collection.md` §7-1·§7-9.

판정 결과는 여기서 확정하지 않는다. 이 모듈은 "공식 필드가 무엇을 말하는가"만 답하고,
추천 적격성·Canonical Mapping 확정은 검토 단계(§9)의 몫이다.
"""

from __future__ import annotations

from typing import Mapping

# ── 학교종류 (getCodeByKind) ─────────────────────────────────────────
SCHOOL_KIND_UNIVERSITY = "03"  # 대학교

# ── 수업연한 (getCodeByLessonTerm) ───────────────────────────────────
# 코드는 연한 순으로 증가하다가 14·15에서 끊긴다. 14="1년(교육특성화)", 15="2년(교육특성화)"로
# 코드값은 크지만 실제 연한은 1~2년이다 — `>= "07"` 같은 대소 비교로 거르면 이 둘이 딸려
# 들어온다. 그래서 부등호가 아니라 **명시적 집합**으로 잡는다.
LESSON_TERM_LABELS: Mapping[str, str] = {
    "01": "1년", "02": "1.5년", "03": "2년", "04": "2.5년", "05": "3년",
    "06": "3.5년", "07": "4년", "08": "4.5년", "09": "5년", "10": "5.5년",
    "11": "6년", "12": "6.5년", "13": "7년",
    "14": "1년(교육특성화)", "15": "2년(교육특성화)",
}

# 4년제 학사과정으로 인정하는 수업연한.
# 07(4년)부터 13(7년)까지 포함한다 — 의·치·한의·수의예과가 11(6년)이라
# "정확히 4년"으로 잡으면 이들이 통째로 빠진다. 학생이 지원하는 정규 학사과정이므로 포함한다.
FOUR_YEAR_OR_LONGER_TERM_CODES: frozenset[str] = frozenset(
    {"07", "08", "09", "10", "11", "12", "13"}
)

# ── 학위과정 (getCodeByDegreeCourse) ─────────────────────────────────
DEGREE_COURSE_BACHELOR = "3"  # 학사

# ── 표준분류 "분류 없음" 센티널 (§7-9) ───────────────────────────────
# N.C.E는 분류명이 아니라 미분류 표시다. 유효 계열로 취급하면 미분류 학과 수천 건이
# 존재하지 않는 "N.C.E 전공"으로 뭉친다.
UNCLASSIFIED_MIDDLE_SERIES = "99"
UNCLASSIFIED_SMALL_SERIES = "999"
UNCLASSIFIED_SERIES_LABELS: frozenset[str] = frozenset({"N.C.E", "N.C.E."})


def lesson_term_label(code: str) -> str | None:
    return LESSON_TERM_LABELS.get((code or "").strip().zfill(2))


def is_four_year_or_longer(row: Mapping[str, str]) -> bool:
    """수업연한이 4~7년인가. 코드가 비었거나 모르는 값이면 False(보수적)."""
    return (row.get("lsnTrmCd") or "").strip().zfill(2) in FOUR_YEAR_OR_LONGER_TERM_CODES


def is_university(row: Mapping[str, str]) -> bool:
    """학교종류가 '대학교'인가. 전문대학·사이버대학·기능대학 등은 제외된다."""
    return (row.get("schlKndCd") or "").strip().zfill(2) == SCHOOL_KIND_UNIVERSITY


def is_bachelor_course(row: Mapping[str, str]) -> bool:
    return (row.get("pbnfDgriCrseDivCd") or "").strip() == DEGREE_COURSE_BACHELOR


def is_series_unclassified(row: Mapping[str, str]) -> bool:
    """표준분류 중·소계열이 미분류(N.C.E)인가.

    코드와 이름 양쪽을 본다 — 코드 체계가 바뀌어도 이름 쪽에서 걸리고, 그 반대도 마찬가지다.
    """
    if (row.get("srsMclftCd") or "").strip() == UNCLASSIFIED_MIDDLE_SERIES:
        return True
    if (row.get("srsSclftCd") or "").strip() == UNCLASSIFIED_SMALL_SERIES:
        return True
    for key in ("korSrsMclftNm", "korSrsSclftNm"):
        if (row.get(key) or "").strip() in UNCLASSIFIED_SERIES_LABELS:
            return True
    return False


def undergraduate_scope_reason(row: Mapping[str, str]) -> str | None:
    """4년제 학사 범위에서 제외되는 이유. 포함 대상이면 None.

    제외 행을 지우지 않고 이 사유와 함께 `excluded_records.jsonl`에 남긴다 (§7).
    """
    if not is_university(row):
        kind = (row.get("schlKndNm") or "").strip() or (row.get("schlKndCd") or "?")
        return f"학교종류가 대학교가 아님: {kind}"
    if not is_bachelor_course(row):
        course = (row.get("pbnfDgriCrseDivNm") or "").strip() or "?"
        return f"학위과정이 학사가 아님: {course}"
    if not is_four_year_or_longer(row):
        code = (row.get("lsnTrmCd") or "").strip().zfill(2)
        return f"수업연한이 4년 미만: {lesson_term_label(code) or code}"
    return None


# ── 서비스 추천 범위 (A 결정 2026-08-24) ────────────────────────────────
# "4~7년제 학사과정의 **주간 과정**"만 Master 승격 후보다. 야간은 원본·Lineage·Audit에
# 보존하되 승격·분류·추천에서 제외한다. 삭제하지 않는다.
DAY_NIGHT_DAY = "주간"
DAY_NIGHT_NIGHT = "야간"

EXCLUDED_NIGHT_COURSE = "EXCLUDED_NIGHT_COURSE"
EXCLUDED_DISTANCE_UNIVERSITY = "EXCLUDED_DISTANCE_UNIVERSITY"
EXCLUDED_UNKNOWN_DAY_NIGHT = "EXCLUDED_UNKNOWN_DAY_NIGHT"

# 원격·사이버·방송통신 대학의 **공식 학교종류 코드**.
# 교명 문자열로 판정하지 않는다 — 일반 대학의 "디지털·온라인" 학과가 걸리면 안 된다
# (A 결정: "일반 대학의 온라인 강의·디지털 관련 학과는 제외하지 않음").
# 04·05는 대학알리미 getCodeByKind/getCodeByType의 원격대학 계열 코드다.
DISTANCE_SCHOOL_KIND_CODES: frozenset[str] = frozenset({"04", "05"})
DISTANCE_SCHOOL_KIND_NAME_HINTS: frozenset[str] = frozenset(
    {"사이버대학(대학)", "사이버대학", "원격대학", "방송통신대학"}
)


def is_distance_university(row: Mapping[str, str]) -> bool:
    """사이버·원격·방송통신대학인가. **공식 코드/유형명으로만 판정한다.**

    교명에 '사이버'가 들어가는지 보지 않는다. 학교 유형은 대학알리미가 코드로 관리하고,
    교명 문자열로 거르면 일반 대학의 '디지털·온라인' 학과가 잘못 걸린다.
    """
    code = (row.get("schlKndCd") or "").strip().zfill(2)
    if code in DISTANCE_SCHOOL_KIND_CODES:
        return True
    # 코드 체계가 바뀌어도 유형명 쪽에서 걸리게 이중으로 본다. 여기서도 교명이 아니라
    # **학교종류 필드**만 본다.
    return (row.get("schlKndNm") or "").strip() in DISTANCE_SCHOOL_KIND_NAME_HINTS


def recommendation_scope_exclusion(row: Mapping[str, str]) -> str | None:
    """추천 Master 승격 후보에서 빠지는 사유. 포함 대상이면 None.

    4~7년제 학사 판정(`undergraduate_scope_reason`)을 통과한 뒤에 적용한다 —
    이건 "학사과정인가"가 아니라 "서비스가 추천할 범위인가"를 묻는다.
    """
    if is_distance_university(row):
        return EXCLUDED_DISTANCE_UNIVERSITY

    day_night = (row.get("dghtDivNm") or "").strip()
    if not day_night:
        # 값이 없다고 주간으로 추정하지 않는다 (A 결정 §3).
        return EXCLUDED_UNKNOWN_DAY_NIGHT
    if day_night == DAY_NIGHT_DAY:
        return None
    if day_night == DAY_NIGHT_NIGHT:
        return EXCLUDED_NIGHT_COURSE
    # '원격' 같은 제3의 값. 주간이 아니므로 제외하되 야간과 구분해 기록한다.
    return EXCLUDED_UNKNOWN_DAY_NIGHT
