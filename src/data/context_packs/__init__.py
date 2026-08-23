"""Context Pack 저장소 — 2026-08-23 Trait Ontology v2(2.7단계) §1/§2.

**이 디렉터리를 직접 편집하지 마세요.** `src/services/context_pack_registry.py`가
이 패키지 안의 모듈을 전부 자동으로 훑어서 `CONTEXT_PACK`이라는 최상위 상수를 가진
모듈만 실제 Context Pack으로 등록한다(`discover_context_packs()`). Context 제작
에이전트는 여기에 자기 Context 하나당 새 파일 하나만 추가하면 된다 — 예를 들어
`business_pack.py`를 만들고 그 안에 `CONTEXT_PACK: ContextPack = ...`을 정의하면
끝이다. 이 `__init__.py`도, `src/services/context_pack_registry.py`도, `src/api/
main.py`도 수정할 필요가 없다(중앙 파일 소유권 — 이 3개는 A가 소유한다).

`_example_pack_builder.py`는 실제 Pack이 아니다 — `CONTEXT_PACK` 상수를 노출하지
않으므로 자동 발견 대상에서 제외된다(파일 자체의 docstring 참고)."""

from __future__ import annotations
