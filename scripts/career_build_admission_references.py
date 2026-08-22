"""AdmissionReference 적재 (작업자 C 소유) — 설계안 §18, C 지시서 §3.

## 지금 수치가 비어 있는 이유 (그대로 읽어 주세요)

설계안에 입결 Source가 지정돼 있지 않고, 대학어디가(adiga)는 자동 수집이 막혀 있다.
따라서 **실제 컷 점수를 확인할 경로가 아직 없다.** 확인하지 않은 숫자를 채워 넣으면
화면에서는 진짜처럼 보이지만 근거가 없으므로, 이 스크립트는 두 파일을 나눠서 만든다.

    admission_references.jsonl              score_50_cut/score_70_cut = null,
                                            review_status = "draft"
                                            → 학년도·전형·전형유형·지표 축만 확정된 골격
    admission_references.placeholder.jsonl  같은 행에 **합성 숫자**를 넣은 것.
                                            테스트·데모 전용이며 실제 입결이 아니다.

출처가 확정되면 골격 파일의 두 컷 필드만 채우고 `review_status`를 `verified`로 올리면
된다 — 행 구조와 `data_comparability_group`은 그대로다.

실행:
    python scripts/career_build_admission_references.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.admission_filter import (  # noqa: E402
    derive_comparability_group,
    validate_group_field,
)
from src.schemas.major import AdmissionReference  # noqa: E402

MASTER_DIR = ROOT / "data" / "master"
OUT_DIR = ROOT / "data" / "admissions"

SOURCE_URL = "https://www.adiga.kr/"
VERIFIED_AT = datetime(2026, 8, 21, tzinfo=timezone.utc)

# (학년도, 전형, 전형유형, 지표) — 이 넷이 비교 가능성의 축이다.
AXES: list[tuple[int, str, str, str]] = [
    (2025, "정시", "나군", "국어·수학·탐구 백분위 70%컷"),
    (2025, "수시", "학생부교과", "교과 등급 50%컷"),
    (2024, "정시", "나군", "국어·수학·탐구 백분위 70%컷"),
]

# 축마다 담을 학과 (대학명, 학과명). data/master/departments.jsonl에 있어야 한다.
TARGETS: list[tuple[str, str]] = [
    ("서울대학교", "컴퓨터공학부"),
    ("연세대학교", "컴퓨터과학과"),
    ("고려대학교", "컴퓨터학과"),
    ("한양대학교", "컴퓨터소프트웨어학부"),
    ("중앙대학교", "소프트웨어학부"),
    ("성균관대학교", "소프트웨어학과"),
    ("경희대학교", "컴퓨터공학부"),
    ("부산대학교", "정보컴퓨터공학부"),
    ("충남대학교", "컴퓨터융합학부"),
    ("고려대학교", "미디어학부"),
    ("중앙대학교", "미디어커뮤니케이션학부"),
    ("서울대학교", "기계공학부"),
    ("한양대학교", "기계공학부"),
    ("부산대학교", "기계공학부"),
    ("연세대학교", "경영학과"),
    ("고려대학교", "경영학과"),
]

# 합성 숫자 (placeholder 파일 전용). 실제 입결이 아니다.
PLACEHOLDER_70: dict[str, float] = {
    "국어·수학·탐구 백분위 70%컷": 95.0,
    "교과 등급 50%컷": 1.6,
}


def _load_departments() -> dict[tuple[str, str], str]:
    path = MASTER_DIR / "departments.jsonl"
    index: dict[tuple[str, str], str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        index[(row["university_name"], row["department_name"])] = row["department_id"]
    return index


def build() -> tuple[list[AdmissionReference], list[AdmissionReference]]:
    index = _load_departments()
    skeleton: list[AdmissionReference] = []
    placeholder: list[AdmissionReference] = []

    for axis_index, (year, admission_type, track, metric) in enumerate(AXES):
        group = derive_comparability_group(year, admission_type, track, metric)
        # 축마다 학과 수를 달리 둔다 — 그룹 크기가 다를 때 select_group()이 어떤 그룹을
        # 고르는지 실제로 확인할 수 있어야 한다.
        targets = TARGETS if axis_index == 0 else TARGETS[: len(TARGETS) - axis_index * 3]
        for university, department in targets:
            department_id = index.get((university, department))
            if department_id is None:
                raise SystemExit(f"master에 없는 학과: {university} {department}")

            common = dict(
                department_id=department_id,
                admission_year=year,
                admission_type=admission_type,
                admission_track=track,
                score_metric=metric,
                source_url=SOURCE_URL,
                data_comparability_group=group,
                verified_at=VERIFIED_AT,
            )
            skeleton.append(
                AdmissionReference(
                    **common,
                    score_50_cut=None,
                    score_70_cut=None,
                    minimum_requirement="수치 미확정 — 출처(대학어디가/대학별 입학처) 확정 후 적재",
                    review_status="draft",
                )
            )
            # 합성값은 학과별로 조금씩 어긋나게 둬서 정렬 동작을 확인할 수 있게 한다.
            # 파이썬 내장 hash()는 실행마다 값이 달라진다(문자열 해시 랜덤화) — 재생성
            # 결과가 매번 바뀌면 안 되므로 고정 해시를 쓴다.
            digest = hashlib.sha256(department_id.encode("utf-8")).digest()
            offset = (digest[0] % 40) / 10.0
            base = PLACEHOLDER_70[metric]
            value = round(base - offset, 2) if metric.startswith("국어") else round(base + offset / 10, 2)
            placeholder.append(
                AdmissionReference(
                    **common,
                    score_50_cut=None,
                    score_70_cut=value,
                    minimum_requirement="합성값 — 실제 입결 아님",
                    review_status="draft",
                )
            )

    return skeleton, placeholder


def _write(path: Path, rows: list[AdmissionReference]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(r.model_dump_json() + "\n" for r in rows), encoding="utf-8")


if __name__ == "__main__":
    use_utf8_stdout()
    skeleton, placeholder = build()
    problems = validate_group_field(skeleton) + validate_group_field(placeholder)
    if problems:
        raise SystemExit("data_comparability_group 불일치:\n" + "\n".join(problems))

    _write(OUT_DIR / "admission_references.jsonl", skeleton)
    _write(OUT_DIR / "admission_references.placeholder.jsonl", placeholder)
    groups = sorted({r.data_comparability_group for r in skeleton})
    print(f"AdmissionReference {len(skeleton)}행 / 비교 그룹 {len(groups)}개")
    for group in groups:
        count = sum(1 for r in skeleton if r.data_comparability_group == group)
        print(f"  {group} — {count}행")
