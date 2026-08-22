"""SubjectRepository 구현 — 설계안 §20, 2026-08-24 14차 리뷰.

`src/repositories/protocols.py`에 정의한 `SubjectRepository` Protocol을 만족한다.
`src/repositories/department_repository.py`와 같은 구조: `data/master/subjects.jsonl`
(정본, `scripts/career_build_subject_profiles.py`가 결정론적으로 생성)을 앱 시작 시
한 번 읽어 메모리에 들고 있는다.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.schemas.course import SubjectProfile

DEFAULT_MASTER_PATH = Path(__file__).resolve().parents[2] / "data" / "master" / "subjects.jsonl"


def load_subjects(path: Path | None = None) -> list[SubjectProfile]:
    source = path or DEFAULT_MASTER_PATH
    if not source.exists():
        return []
    return [
        SubjectProfile.model_validate(json.loads(line))
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class JsonlSubjectRepository:
    """`data/master/subjects.jsonl`을 읽는 SubjectRepository."""

    def __init__(self, subjects: list[SubjectProfile] | None = None, path: Path | None = None):
        self._subjects = subjects if subjects is not None else load_subjects(path)
        self._by_id = {s.subject_id: s for s in self._subjects}

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
