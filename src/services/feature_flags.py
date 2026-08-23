"""Feature Flag 로더 — 2026-08-23 Trait Ontology v2(2단계) §4, 2.6단계 §2.

`src/llm/settings.py::llm_generation_enabled()`와 같은 패턴이다 — 명시적 opt-in
플래그이고, `.env`에 값이 있어도 이 함수가 꺼져 있으면 항상 OFF로 취급한다. OFF일 때는
기존 Legacy 질문 흐름·Profile·추천 결과가 완전히 그대로 유지돼야 한다(§4/§6/§20).

2.6단계 §2: `ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES`와 `ENABLE_TRAIT_VECTOR_V2_PRIMARY`는
서로 다른 질문에 답하는 완전히 독립된 Flag다 — 하나가 다른 하나를 함의하지 않는다.

- DIRECT_PROBES: v2 전용 질문(Context Routing/Seed Anchor Variant/V2 Direct Probe/
  Anchor Backup)을 실제 검사 흐름에 포함하는가. 이 Flag가 꺼져 있으면 세션은 순수
  Legacy 질문 흐름만 겪는다.
- PRIMARY: (DIRECT_PROBES 여부와 무관하게) `/profile`·`/majors`·`/subjects`가
  TraitVectorSnapshot(v2)을 실제 입력으로 쓰는가. DIRECT_PROBES=false여도 PRIMARY=true면
  세션은 순수 Legacy 질문만 겪지만, 그 Evidence를 v2 24-Trait 구조로 다시 계산해 Profile·
  Major·Subject에 쓴다 — "질문 흐름"과 "그 결과를 어떤 엔진으로 해석할지"가 분리된
  설계이기 때문이다.

기본값은 둘 다 OFF다 — OFF에서는 기존 Legacy 결과와 완전히 동일해야 한다(§9).
"""

from __future__ import annotations

import os

MAX_V2_DIRECT_PROBE_QUESTIONS = 4
MAX_V2_DIRECT_PROBES_PER_TRAIT = 1


def _flag_on(name: str, env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return source.get(name, "").strip().lower() in {"1", "true", "yes"}


def trait_vector_v2_direct_probes_enabled(env: dict[str, str] | None = None) -> bool:
    return _flag_on("ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", env)


def trait_vector_v2_primary_enabled(env: dict[str, str] | None = None) -> bool:
    """2.6단계 §2 — v2 Trait Vector Snapshot을 Profile·전공·과목 추천의 실제 입력으로
    쓸지 여부. DIRECT_PROBES와 독립이다(위 모듈 docstring 참고)."""

    return _flag_on("ENABLE_TRAIT_VECTOR_V2_PRIMARY", env)
