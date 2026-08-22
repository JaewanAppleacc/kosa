"""Vertical Slice Active Trait 목록 — 2026-08-31 Trait Ontology v2(1단계) §7.

`CORE_TRAIT_IDS`(24개, Ontology 전체)와 `VERTICAL_SLICE_ACTIVE_TRAIT_IDS`(실제로 현재
3개 Context·검토된 질문에서 탐색할 수 있는 부분집합)를 분리한다 — Stop Condition·
Coverage Gap 탐지·Adaptive Target Planner·질문 반복 판단에는 반드시
`VERTICAL_SLICE_ACTIVE_TRAIT_IDS`만 써야 한다(지시서 §7). 24개 전체를 채우려고 질문을
무한 반복하거나 6문항 상한까지 억지로 끌고 가면 안 된다.

Active 선정 조건(지시서 §7):
1. 현재 질문·선택지에 명확한 Mapping이 존재한다.
2. 적어도 2개의 서로 다른 질문 Frame 또는 2개의 Context에서 확인 가능하다.
3. 한 번의 Seed Option에만 등장하는 Trait는 Active로 성급히 지정하지 않는다.

기존 12개 Trait(`VERTICAL_SLICE_TRAIT_IDS`)는 이미 이 조건을 만족한다(round 12~19에서
실제로 STRONG/MODERATE 판정까지 검증됨) — 전부 Active다.

신규 12개 Trait는 `src/services/trait_signal_registry.py`의 RELATED Signal 등록
결과를 실제로 세어본 뒤 조건 2를 만족하는 것만 포함한다(아래
`_active_new_trait_ids_from_registry()`가 이 계산을 한다 — 손으로 다시 세지 않는다,
Registry가 바뀌면 이 목록도 같이 바뀐다). 계산 결과와 그 근거는
`outputs/reviews/trait_ontology_v2_review.md`에 Coverage Matrix로 남긴다.
"""

from __future__ import annotations

from collections import defaultdict

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.services.trait_ontology_v2 import load_trait_ontology_v2
from src.services.trait_signal_registry import ROLE_ID_TO_TRAIT_SIGNALS


def _active_new_trait_ids_from_registry() -> set[str]:
    """§7 조건 2: RELATED Signal이 서로 다른 role_id(≈서로 다른 질문 문항) 2개 이상에서
    관찰되는 신규 Trait만 Active로 인정한다. role_id는 Blueprint/Seed 안에서 항상 서로
    다른 질문 문항을 가리키므로("한 Blueprint 안에서도 같은 Trait 중복 배정 금지", §9-1),
    서로 다른 role_id 2개는 곧 서로 다른 질문에서 관찰된다는 뜻이다."""

    role_ids_by_new_trait: dict[str, set[str]] = defaultdict(set)
    for role_id, signals in ROLE_ID_TO_TRAIT_SIGNALS.items():
        for signal in signals:
            if signal.trait_id not in VERTICAL_SLICE_TRAIT_IDS:
                role_ids_by_new_trait[signal.trait_id].add(role_id)
    return {trait_id for trait_id, role_ids in role_ids_by_new_trait.items() if len(role_ids) >= 2}


CORE_TRAIT_IDS: set[str] = {t.trait_id for t in load_trait_ontology_v2()}

VERTICAL_SLICE_ACTIVE_TRAIT_IDS: set[str] = VERTICAL_SLICE_TRAIT_IDS | _active_new_trait_ids_from_registry()
