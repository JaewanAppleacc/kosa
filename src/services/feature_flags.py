"""Feature Flag 로더 — 2026-08-23 Trait Ontology v2(2단계) §4.

`src/llm/settings.py::llm_generation_enabled()`와 같은 패턴이다 — 명시적 opt-in
플래그이고, `.env`에 값이 있어도 이 함수가 꺼져 있으면 항상 OFF로 취급한다. OFF일 때는
기존 Legacy 질문 흐름·Profile·추천 결과가 완전히 그대로 유지돼야 한다(§4/§6/§20).
"""

from __future__ import annotations

import os

MAX_V2_DIRECT_PROBE_QUESTIONS = 4
MAX_V2_DIRECT_PROBES_PER_TRAIT = 1


def trait_vector_v2_direct_probes_enabled(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return source.get("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "").strip().lower() in {"1", "true", "yes"}
