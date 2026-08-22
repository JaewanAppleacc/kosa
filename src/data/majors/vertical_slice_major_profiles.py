"""Vertical Slice 대표 전공 3개의 Major Multi-Vector — 설계안 §15.

2026-08-22 12차 리뷰: 예전엔 이 파일이 Trait Vector 숫자를 직접 손으로 채운 정본이었다
(review_status="draft", source_ids=[] — 근거 없는 A의 1차 초안). 동시에
`data/master/major_profiles.jsonl`에도 C가 만든 별도 Profile이 존재해서, 같은 개념의
"정본"이 두 곳에 서로 다른 값으로 있었다.

지금은 `data/master/major_profiles.jsonl` 하나만 정본이다 — 그 값은
`scripts/career_build_major_profiles.py`의 `build_evidence_based_profiles()`가
`data/master/major_trait_mapping_evidence.jsonl`(실제 학과 공식 자료 근거)에서
결정론적으로 생성한다. 이 파일은 그 정본에서 Vertical Slice 3개(media_communication/
hci_ux/industrial_engineering)만 걸러 읽는 얇은 Loader로 남는다 — 기존 `from
src.data.majors.vertical_slice_major_profiles import VERTICAL_SLICE_MAJOR_PROFILES`
호출부(main.py, tests/*)는 이 파일이 Loader로 바뀐 걸 몰라도 된다(같은 이름의
`list[MajorProfile]` 상수를 그대로 제공).
"""

from __future__ import annotations

from pathlib import Path

from src.schemas.major import MajorProfile

_MASTER_PATH = Path(__file__).resolve().parents[3] / "data" / "master" / "major_profiles.jsonl"

# 이 3개만 "Vertical Slice에서 실제로 추천 가능한 대표 전공"이다 — Matching Engine
# (src/api/main.py)이 여기서 그대로 읽는다. 여기서 개수·구성을 바꾸면 곧 추천 가능한
# 전공 자체가 바뀌므로, 이번 12차 리뷰 범위에서는 건드리지 않는다(§14 "새로운 대표
# 전공을 추가하지 않는다").
VERTICAL_SLICE_MAJOR_IDS: tuple[str, ...] = ("media_communication", "hci_ux", "industrial_engineering")


def load_vertical_slice_major_profiles(path: Path | None = None) -> list[MajorProfile]:
    source = path or _MASTER_PATH
    if not source.exists():
        raise FileNotFoundError(
            f"{source}가 없다 — scripts/career_build_major_profiles.py를 먼저 실행해야 한다."
        )
    by_id: dict[str, MajorProfile] = {}
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        profile = MajorProfile.model_validate_json(line)
        if profile.major_id in VERTICAL_SLICE_MAJOR_IDS:
            by_id[profile.major_id] = profile

    missing = set(VERTICAL_SLICE_MAJOR_IDS) - set(by_id)
    if missing:
        raise ValueError(
            f"{source}에 Vertical Slice 대표 전공 {sorted(missing)}의 MajorProfile이 없다 — "
            "career_build_major_profiles.py를 다시 실행했는지 확인하세요."
        )
    # VERTICAL_SLICE_MAJOR_IDS 선언 순서를 그대로 따른다 — 파일 안 줄 순서에 의존하지 않는
    # 결정론적 순서.
    return [by_id[major_id] for major_id in VERTICAL_SLICE_MAJOR_IDS]


VERTICAL_SLICE_MAJOR_PROFILES: list[MajorProfile] = load_vertical_slice_major_profiles()
