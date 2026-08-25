"""Service Canonical Major v2(39개) MajorProfile Loader — 2026-08-25 지시서
(a/major-profiles-v2-38) §2.

`src/data/majors/vertical_slice_major_profiles_v2.py`(3개 고정 구조)를
대체한다 — `VERTICAL_SLICE_MAJOR_PROFILES_V2`는 더 이상 존재하지 않는다.
`data/master/major_profiles_v2.jsonl`에서 39개 Service Canonical Major v2
Catalog(`data/master/service_canonical_majors_v2.jsonl`, ACTIVE 38개 Group
기반 + hci_ux 1개) 전부를 자동 로드한다. Catalog가 바뀌면 이 Loader가 읽는
ID 집합도 자동으로 따라간다 — major_id 목록을 이 파일에 하드코딩하지 않는다.

Fail-Fast(§2):
- Catalog(39개)와 Profile 파일의 major_id 집합이 정확히 일치해야 한다 —
  1개라도 누락되면(Catalog에는 있는데 Profile 파일에 없음) 즉시 예외. 반대로
  Profile 파일에 Catalog에 없는 major_id가 있어도(예: 예체능 제외 Group에서
  파생된 값, 또는 폐기된 옛 값) 즉시 예외 — "정확히 일치"는 양방향이다.
- 같은 major_id가 파일에 두 번 있으면 마지막 값으로 조용히 덮어쓰지 않는다.

예체능 제외 4개 Group은 애초에 39개 Catalog에 없으므로(§ Catalog 자체가 이미
걸렀다), 이 Loader가 Catalog와의 1:1 일치만 강제하면 "예체능 제외 4개 Profile
로드 금지"가 구조적으로 함께 지켜진다 — 별도 예체능 목록을 이 파일이 다시
들고 있지 않는다(단일 정본 원칙)."""

from __future__ import annotations

from pathlib import Path

from src.schemas.major import MajorProfile
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2

_MASTER_PATH = Path(__file__).resolve().parents[3] / "data" / "master" / "major_profiles_v2.jsonl"


def load_service_major_profiles_v2(path: Path | None = None) -> list[MajorProfile]:
    source = path or _MASTER_PATH
    if not source.exists():
        raise FileNotFoundError(
            f"{source}가 없다 — scripts/career_build_major_profiles_v2.py를 먼저 실행해야 한다."
        )
    catalog_ids = tuple(sorted(m.major_id for m in load_service_canonical_majors_v2()))
    catalog_id_set = frozenset(catalog_ids)

    by_id: dict[str, MajorProfile] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        profile = MajorProfile.model_validate_json(line)
        if profile.major_id in by_id:
            raise ValueError(
                f"{source}에 major_id={profile.major_id!r}가 두 번 이상 있다 — "
                "Loader가 마지막 값으로 덮어쓰지 않고 즉시 오류로 막는다."
            )
        by_id[profile.major_id] = profile

    file_id_set = frozenset(by_id)
    missing = catalog_id_set - file_id_set
    if missing:
        raise ValueError(
            f"{source}에 Service Catalog Major {sorted(missing)}의 MajorProfile(v2)이 없다 — "
            "career_build_major_profiles_v2.py를 다시 실행했는지 확인하세요."
        )
    extra = file_id_set - catalog_id_set
    if extra:
        raise ValueError(
            f"{source}에 39개 Service Catalog에 없는 major_id가 있다(예체능 제외 Group 유래 값이거나 "
            f"폐기된 값일 수 있다) — {sorted(extra)}. Catalog와 Profile ID 집합이 정확히 일치해야 한다."
        )

    return [by_id[major_id] for major_id in catalog_ids]


SERVICE_MAJOR_PROFILES_V2: list[MajorProfile] = load_service_major_profiles_v2()
