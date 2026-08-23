"""ContextPack Runtime Adapter — 2026-08-23 Trait Ontology v2(2.8단계) §4. A 소유
(중앙 통합).

ContextPack Registry(발견·검증·검수 승인 판정)와 실제 Assessment 질문 흐름(main.py) 사이의
어댑터. `game`/`media`/`school_life` 같은 이름을 조건문으로 나열하지 않는다 — 어떤
context_id가 와도 (a) Legacy Vertical Slice Context면 관여하지 않고(항상 None 반환,
호출부가 기존 Legacy 조회로 폴백), (b) 그 외에는 Registry에서 실제로 발견·Ontology
검증·검수 승인까지 통과한 Pack만 돌려준다(Fail-Closed) — Flag가 꺼져 있어도 마찬가지다.

반환 타입은 전부 기존 계약 타입 그대로다(`ContextRoutingBlueprint`/
`ContextAnchorPresentation`/`FinalizedQuestion`/`V2DirectProbeBlueprint`) — 학생 API
응답 Schema를 바꾸지 않는다."""

from __future__ import annotations

from typing import Callable

from src.schemas.context_anchor_presentation import ContextAnchorPresentation
from src.schemas.context_pack import ContextPack
from src.schemas.context_routing import ContextRoutingBlueprint
from src.schemas.question import FinalizedQuestion
from src.schemas.v2_direct_probe import V2DirectProbeBlueprint
from src.services.context_pack_registry import ALL_BATCH_CONTEXT_IDS, ContextPackRegistry


class ContextPackRuntime:
    def __init__(
        self,
        registry: ContextPackRegistry,
        enabled: Callable[[], bool],
        legacy_context_ids: frozenset[str],
    ) -> None:
        self._registry = registry
        self._enabled = enabled
        self._legacy_context_ids = legacy_context_ids

    def _pack_if_active(self, context_id: str) -> ContextPack | None:
        """§3-1 Fail-Closed 활성화 조건을 전부 적용한 뒤에만 Pack을 돌려준다 — 호출부는
        이 결과가 None이 아니면 항상 "이 Context는 실제로 서빙 가능하다"고 믿어도 된다."""

        if context_id in self._legacy_context_ids:
            return None  # Legacy 3개는 이 어댑터가 절대 관여하지 않는다.
        if context_id not in ALL_BATCH_CONTEXT_IDS:
            return None  # 활성화 배치에 없는 Context는 Pack이 있어도 서빙 대상이 아니다.
        if not self._enabled():
            return None
        if not self._registry.is_pack_review_approved(context_id):
            return None
        return self._registry.get_pack(context_id)

    def active_pack_context_ids(self) -> list[str]:
        """§3-1 조건을 전부 만족하는 신규 Context id 목록(결정론적 정렬)."""

        return sorted(cid for cid in ALL_BATCH_CONTEXT_IDS if self._pack_if_active(cid) is not None)

    def get_routing_question(self, context_id: str) -> ContextRoutingBlueprint | None:
        pack = self._pack_if_active(context_id)
        return pack.routing_blueprint if pack is not None else None

    def get_anchor_presentation(self, context_id: str, anchor_id: str) -> ContextAnchorPresentation | None:
        pack = self._pack_if_active(context_id)
        if pack is None:
            return None
        return next((a for a in pack.anchor_presentations if a.anchor_id == anchor_id), None)

    def get_seed_question(self, context_id: str, anchor_id: str) -> FinalizedQuestion | None:
        pack = self._pack_if_active(context_id)
        if pack is None:
            return None
        entry = next((s for s in pack.seed_anchor_variants if s.anchor_id == anchor_id), None)
        return entry.question if entry is not None else None

    def get_backup_candidates(self, context_id: str, anchor_id: str) -> list[FinalizedQuestion]:
        """§4 "다른 Anchor의 Seed·Backup이 섞이면 안 된다" — 이 Anchor 하나의 Backup만
        돌려준다(있으면 정확히 1개, 없으면 빈 목록)."""

        pack = self._pack_if_active(context_id)
        if pack is None:
            return []
        entry = next((b for b in pack.anchor_backup_questions if b.anchor_id == anchor_id), None)
        return [entry.question] if entry is not None else []

    def get_direct_probe_candidates(self, context_id: str) -> list[V2DirectProbeBlueprint]:
        """2026-08-23 Trait Ontology v2(2.9단계) §5 — Pack 자신의
        `direct_probe_candidates`(현재 12개 전부 빈 목록, T·S·L이 나중에 채울 수도
        있는 자리)에 검수 승인된 공용 Adaptive Probe Blueprint를 더한다
        (`ContextPackRegistry.shared_probe_blueprints_for_context()`, Fail-Closed —
        미승인 Blueprint는 절대 섞이지 않는다). Context 이름을 여기 하드코딩하지
        않는다 — Registry가 `allowed_context_ids` 멤버십과 단일 공유 검수 파일만으로
        판단한다."""

        pack = self._pack_if_active(context_id)
        if pack is None:
            return []
        return list(pack.direct_probe_candidates) + self._registry.shared_probe_blueprints_for_context(context_id)
