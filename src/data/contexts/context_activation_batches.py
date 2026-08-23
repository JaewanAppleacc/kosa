"""Context Pack 활성화 배치 정의 — 2026-08-23 Trait Ontology v2(2.7단계) §6.

`src/services/context_pack_registry.py`가 이 값을 그대로 재노출한다(기존
`from src.services.context_pack_registry import CONTEXT_ACTIVATION_BATCHES` 호출부를
깨지 않기 위해). 이 값을 별도의 최하위 모듈로 뺀 이유는 2.9단계에서
`src/data/questions/context_pack_shared_probe_blueprints.py`도 이 값(허용 Context id
목록)이 필요해졌는데, 그 파일이 `context_pack_registry.py`를 직접 import하면
순환 참조(Registry → 공용 Probe 목록 → Registry)가 생기기 때문이다 — Context 이름을
아는 이 작은 상수 모듈만 두 곳이 공유한다."""

from __future__ import annotations

# 다음 활성화 배치. Pack이 등록되고 검수(APPROVED)되기 전까지는 이 목록에 있어도
# assessment_supported_context_ids()에 포함되지 않는다(Fail-Closed, context_pack_registry.py).
CONTEXT_ACTIVATION_BATCHES: dict[int, frozenset[str]] = {
    1: frozenset({"business", "science", "sports"}),
    2: frozenset({"making", "volunteer", "writing", "travel"}),
    3: frozenset({"art_design", "cooking", "fashion_beauty", "history_humanities", "law_politics"}),
}
ALL_BATCH_CONTEXT_IDS: frozenset[str] = frozenset(
    context_id for batch in CONTEXT_ACTIVATION_BATCHES.values() for context_id in batch
)
