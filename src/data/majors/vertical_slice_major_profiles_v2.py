"""Vertical Slice 대표 전공 3개의 v2(24-Trait) MajorProfile Loader — 2026-08-23 Trait
Ontology v2(2.6단계) §6/§9.

`vertical_slice_major_profiles.py`(Legacy)와 완전히 같은 Loader 패턴이지만
`data/master/major_profiles_v2.jsonl`(scripts/career_build_major_profiles_v2.py 산출물)
을 읽는다는 점이 다르다 — Legacy 정본은 이 모듈이 전혀 건드리지 않는다."""

from __future__ import annotations

from pathlib import Path

from src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_IDS
from src.schemas.major import MajorProfile

_MASTER_PATH = Path(__file__).resolve().parents[3] / "data" / "master" / "major_profiles_v2.jsonl"


def load_vertical_slice_major_profiles_v2(path: Path | None = None) -> list[MajorProfile]:
    source = path or _MASTER_PATH
    if not source.exists():
        raise FileNotFoundError(
            f"{source}가 없다 — scripts/career_build_major_profiles_v2.py를 먼저 실행해야 한다."
        )
    by_id: dict[str, MajorProfile] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        profile = MajorProfile.model_validate_json(line)
        if profile.major_id not in VERTICAL_SLICE_MAJOR_IDS:
            continue
        if profile.major_id in by_id:
            raise ValueError(
                f"{source}에 major_id={profile.major_id!r}가 두 번 이상 있다 — "
                "Loader가 마지막 값으로 덮어쓰지 않고 즉시 오류로 막는다."
            )
        by_id[profile.major_id] = profile

    missing = set(VERTICAL_SLICE_MAJOR_IDS) - set(by_id)
    if missing:
        raise ValueError(
            f"{source}에 Vertical Slice 대표 전공 {sorted(missing)}의 MajorProfile(v2)이 없다 — "
            "career_build_major_profiles_v2.py를 다시 실행했는지 확인하세요."
        )
    return [by_id[major_id] for major_id in VERTICAL_SLICE_MAJOR_IDS]


VERTICAL_SLICE_MAJOR_PROFILES_V2: list[MajorProfile] = load_vertical_slice_major_profiles_v2()
