"""Trait Vector Shadow Repository — 2026-08-23 Trait Ontology v2(1.5단계) §9/§10.

1단계에서는 `compute_trait_vector_snapshot_all()`이 테스트와 평가 스크립트에서만
호출됐다 — 실제 `/profile` 흐름에서는 한 번도 계산되지 않았다. 이 파일은 그 계산 결과를
세션 단위로 담아두는 순수 저장소만 정의한다(계산 자체는 여전히
`src/engines/trait_vector_snapshot_engine.py`가 한다 — 이 파일은 계산하지 않는다).

시연용 In-Memory 구현이면 충분하다(§9) — PostgreSQL Profile Store가 아직 없는 것과 같은
이유로, 나중에 실제 Store로 교체할 때 이 Protocol의 save/load 시그니처만 유지하면 된다
(`InMemorySessionStore`와 동일한 설계 원칙)."""

from __future__ import annotations

from typing import Protocol

from src.schemas.trait_vector_snapshot import TraitVectorSnapshot


class TraitVectorShadowRepository(Protocol):
    def save(self, session_id: str, snapshot: TraitVectorSnapshot) -> None: ...
    def load(self, session_id: str) -> TraitVectorSnapshot | None: ...


class InMemoryTraitVectorShadowRepository:
    """§9 규칙: 저장·조회 모두 방어적으로 복사한다(호출자가 반환값을 고쳐도 저장소
    원본이 오염되지 않는다) — `TraitVectorSnapshot`은 frozen이라 최상위 재바인딩은 이미
    막히지만, 중첩된 dict/`TraitVectorEntry`까지 완전히 지키려면 deep copy가 필요하다.
    같은 session_id로 다시 save()하면 그 자리의 값을 덮어쓸 뿐 누적하지 않는다 — Profile을
    여러 번 조회해도 중복 계산이나 값 누적이 생기지 않는다."""

    def __init__(self) -> None:
        self._snapshots: dict[str, TraitVectorSnapshot] = {}

    def save(self, session_id: str, snapshot: TraitVectorSnapshot) -> None:
        self._snapshots[session_id] = snapshot.model_copy(deep=True)

    def load(self, session_id: str) -> TraitVectorSnapshot | None:
        snapshot = self._snapshots.get(session_id)
        return snapshot.model_copy(deep=True) if snapshot is not None else None
