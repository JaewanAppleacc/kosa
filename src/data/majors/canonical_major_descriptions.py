"""Canonical Major 설명 정본 — 2026-08-24 A3 지시서 §1/§7.

Legacy Matching(`matching_engine.py`)과 v2 Matching(`matching_engine_v2.py`), 그 외
`MajorRelevance`를 만드는 모든 호출부(`main.py`, `knowledge_subgraph_service.py`,
`course_planning_service.py`, `course_planning_service_v2.py`, `eval/
major_matching_persona_diagnostics.py`)가 `MajorRelevance.description`을 만들 때
반드시 이 딕셔너리 하나만 참조한다 — 호출부마다 따로 만들면 Legacy와 v2가 서로 다른
설명을 만들 위험이 생긴다(§7 "Legacy와 v2가 서로 다른 설명을 만들지 않음"). Runtime
LLM이 즉흥 생성하지 않고 `data/master/canonical_majors.jsonl`(정본)에서 모듈
import 시점에 결정론적으로 한 번만 읽는다."""

from __future__ import annotations

from pathlib import Path

from src.engines.canonical_mapper import load_canonical_majors

_CANONICAL_MAJORS_PATH = Path(__file__).resolve().parents[3] / "data" / "master" / "canonical_majors.jsonl"

CANONICAL_MAJOR_DESCRIPTIONS_BY_ID: dict[str, str] = {
    entry.major_id: entry.description for entry in load_canonical_majors(_CANONICAL_MAJORS_PATH)
}
