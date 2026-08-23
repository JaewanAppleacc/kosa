"""SubjectRepository 구현 — 설계안 §20, 2026-08-24 14차 리뷰(2026-08-25 15차 리뷰 §5 보완).

`src/repositories/protocols.py`에 정의한 `SubjectRepository` Protocol을 만족한다.
`src/repositories/department_repository.py`와 같은 구조: `data/master/subjects.jsonl`
(정본, `scripts/career_build_subject_profiles.py`가 결정론적으로 생성)을 앱 시작 시
한 번 읽어 메모리에 들고 있는다.

2026-08-25 15차 리뷰: `src.data.majors.vertical_slice_major_profiles.
load_vertical_slice_major_profiles`가 정본 파일의 중복 major_id를 막는 것과 같은 방식을
그대로 가져온다(코드를 복제하지 않고, "리스트를 dict로 모으면서 이미 있는 key를 다시
보면 즉시 예외"라는 같은 패턴만 재사용). 마지막 값으로 조용히 덮어쓰면, 정본 파일이
손상돼도 앱이 "둘 중 하나"를 임의로 골라 잘못된 정본으로 시작해 버린다 — 그 대신
즉시 실패시킨다.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.course import SubjectProfile

DEFAULT_MASTER_PATH = Path(__file__).resolve().parents[2] / "data" / "master" / "subjects.jsonl"


class DuplicateSubjectIdError(ValueError):
    """정본 파일(또는 주입된 목록)에 같은 subject_id가 두 번 이상 있을 때 — 어느 행이
    맞는지 알 수 없으므로 조용히 뒤 항목으로 덮어쓰지 않고 즉시 실패시킨다. 학생 답변
    등 민감정보는 담지 않고 subject_id만 메시지에 남긴다."""


def load_subjects(path: Path | None = None) -> list[SubjectProfile]:
    source = path or DEFAULT_MASTER_PATH
    if not source.exists():
        return []
    return [
        SubjectProfile.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _index_by_id(subjects: list[SubjectProfile]) -> dict[str, SubjectProfile]:
    by_id: dict[str, SubjectProfile] = {}
    for subject in subjects:
        if subject.subject_id in by_id:
            raise DuplicateSubjectIdError(
                f"duplicate subject_id: {subject.subject_id!r} — 정본 파일 또는 주입된 "
                "목록에 같은 과목이 두 번 이상 있다."
            )
        by_id[subject.subject_id] = subject
    return by_id


class JsonlSubjectRepository:
    """`data/master/subjects.jsonl`을 읽는 SubjectRepository. 파일 안 행 순서가 달라져도
    `all()`/`related_to_major()`의 반환 순서는 항상 입력 리스트 순서를 그대로 따르므로
    결정론적이다(정렬을 별도로 하지 않고, 정본 파일 자체가 이미 subject_id 오름차순으로
    결정론적으로 생성된다 — scripts/career_build_subject_profiles.py)."""

    def __init__(self, subjects: list[SubjectProfile] | None = None, path: Path | None = None):
        self._subjects = subjects if subjects is not None else load_subjects(path)
        self._by_id = _index_by_id(self._subjects)  # 중복 subject_id는 여기서 즉시 예외.

    def __len__(self) -> int:
        return len(self._subjects)

    def all(self) -> list[SubjectProfile]:
        return list(self._subjects)

    def related_to_major(self, major_id: str) -> list[SubjectProfile]:
        if not major_id:
            return []
        return [s for s in self._subjects if major_id in s.related_major_ids]

    def get(self, subject_id: str) -> SubjectProfile | None:
        return self._by_id.get(subject_id)
