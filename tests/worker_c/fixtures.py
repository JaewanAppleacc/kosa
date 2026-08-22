"""테스트 공용 데이터 — 파일 저장소에 의존하지 않는 최소 객체들."""

from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.major import AdmissionReference, Department

VERIFIED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)


def department(
    department_id: str = "dept_test_001",
    university_name: str = "테스트대학교",
    department_name: str = "컴퓨터공학과",
    college_name: str = "공과대학",
    region: str = "서울",
    canonical_major_id: str | None = None,
) -> Department:
    return Department(
        department_id=department_id,
        university_name=university_name,
        campus=None,
        region=region,
        department_name=department_name,
        college_name=college_name,
        admission_unit=college_name,
        department_status="EXISTING",
        source_svy_year=2025,
        source_url="https://www.academyinfo.go.kr/",
        canonical_major_id=canonical_major_id,
    )


def admission_reference(
    department_id: str = "dept_test_001",
    admission_year: int = 2025,
    admission_type: str = "정시",
    admission_track: str = "나군",
    score_metric: str = "백분위 70%컷",
    score_70_cut: float | None = 95.0,
    review_status: str = "verified",
) -> AdmissionReference:
    group = f"{admission_year}|{admission_type}|{admission_track}|{score_metric}"
    return AdmissionReference(
        department_id=department_id,
        admission_year=admission_year,
        admission_type=admission_type,
        admission_track=admission_track,
        score_metric=score_metric,
        score_50_cut=None,
        score_70_cut=score_70_cut,
        minimum_requirement=None,
        source_url="https://www.adiga.kr/",
        data_comparability_group=group,
        review_status=review_status,  # type: ignore[arg-type]
        verified_at=VERIFIED_AT,
    )
