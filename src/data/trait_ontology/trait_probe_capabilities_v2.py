"""Trait Probe Coverage — 2026-08-23 Trait Ontology v2(1.5단계) §7/§8.

1단계 `vertical_slice_active_traits.py`는 "서로 다른 role_id 2개 ≈ 서로 다른 질문
Frame·Context"라는 잘못된 가정으로 `VERTICAL_SLICE_ACTIVE_TRAIT_IDS`(19개)를 계산했고,
이름은 "Active"인데 실제로는 Adaptive Target Planner가 그 이름을 참조하지도 않아서
("Planner에서 반드시 사용한다"는 주석과 실제 동작이 어긋났다) 혼동을 남겼다. 이 파일은
그 문제를 다음과 같이 고친다:

1. `LEGACY_RUNTIME_ACTIVE_TRAIT_IDS`: Adaptive Target Planner·Stop Condition·Coverage
   Gap이 실제로 참조하는 유일한 집합 — `VERTICAL_SLICE_TRAIT_IDS`(기존 12개)와 정확히
   같다(재수출일 뿐 새로 계산하지 않는다). 이 파일이 v2 계산을 아무리 바꿔도 Planner
   동작에는 절대 영향이 없다는 걸 이름과 값 둘 다로 보증한다.
2. `TRAIT_PROBE_CAPABILITIES`: Trait별로 Blueprint·Context·Frame 각각을 독립적으로 센
   `TraitProbeCapability`. Blueprint/Context/Frame은 서로 다른 축이라 하나가 늘어난다고
   나머지가 같이 늘어나는 게 아니다 — role_id 개수만으로 유추하지 않는다.
3. `OBSERVABLE_TRAIT_IDS` / `DIRECTLY_MEASURABLE_TRAIT_IDS` / `RELATED_ONLY_TRAIT_IDS` /
   `NOT_PROBED_TRAIT_IDS`: v2 Shadow 계산·보고서 전용 진단 집합이다 — Planner·Stop
   Condition·질문 순서 어디에도 아직 적용하지 않는다(§8, Shadow Mode 유지).

Context/Frame 도달 가능성 규칙(정적으로 구조에서만 계산, 실제 세션 관찰과는 별개):
- Seed Blueprint는 그 Seed가 속한 Context 1개, Frame은 항상 "seed_frame" 1개뿐이다.
- Backup Blueprint도 그 Backup이 속한 Context 1개, Frame은 항상 "backup" 1개뿐이다.
- Tail Blueprint(3개)는 game/media/school_life 어느 Context에서도 Target Planner가
  선택할 수 있고(§8 `blueprint_for_target_trait`가 Context와 무관하게 결정), Frame도
  Planner가 위치·테마에 따라 `QUESTION_FRAME_TEXT`의 9개 중 아무거나 고를 수 있다
  (frame_role_map.py — Blueprint와 Frame은 서로 독립된 축이다). 그래서 Tail Blueprint는
  Context 3개·Frame 9개 전부를 "도달 가능"으로 센다 — 이건 구조적 상한이지, 실제 한
  세션에서 전부 관찰된다는 뜻이 아니다(실제 관찰 수치는 §11/§14 Persona 실측이 낸다).
"""

from __future__ import annotations

from src.data.contexts.context_definitions import VERTICAL_SLICE_CONTEXT_IDS
from src.data.question_frames.frame_role_map import QUESTION_FRAME_TEXT
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS_BY_ID
from src.data.questions.vertical_slice_backup_questions import VERTICAL_SLICE_BACKUP_QUESTIONS
from src.data.questions.vertical_slice_seed_questions import VERTICAL_SLICE_SEED_QUESTIONS
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS
from src.schemas.question import seed_question_to_blueprint
from src.schemas.trait_probe_capability import TraitProbeCapability
from src.services.trait_ontology_v2 import load_trait_ontology_v2
from src.services.trait_signal_registry import all_registrations

# §7: Adaptive Target Planner·Stop Condition·Coverage Gap이 실제로 쓰는 유일한 집합.
# 기존 12개와 동일 — 이 이름을 v2 진단 집합과 절대 혼동하지 않도록 명시적으로 재수출한다.
LEGACY_RUNTIME_ACTIVE_TRAIT_IDS: set[str] = set(VERTICAL_SLICE_TRAIT_IDS)

CORE_TRAIT_IDS: set[str] = {t.trait_id for t in load_trait_ontology_v2()}

_ALL_TAIL_FRAME_IDS: frozenset[str] = frozenset(QUESTION_FRAME_TEXT.keys())
_ALL_TAIL_CONTEXT_IDS: frozenset[str] = frozenset(VERTICAL_SLICE_CONTEXT_IDS)

# blueprint_id -> context_id (Seed/Backup만 — Tail Blueprint는 Context에 묶이지 않는다).
_SEED_BLUEPRINT_CONTEXT: dict[str, str] = {
    seed_question_to_blueprint(seed).blueprint_id: context_id
    for context_id, seed in VERTICAL_SLICE_SEED_QUESTIONS.items()
}
_BACKUP_BLUEPRINT_CONTEXT: dict[str, str] = {
    backup.question_id: context_id
    for context_id, backups in VERTICAL_SLICE_BACKUP_QUESTIONS.items()
    for backup in backups
}


def _reachable_context_and_frame_ids(question_family_id: str, blueprint_id: str) -> tuple[set[str], set[str]]:
    if question_family_id == "seed":
        return {_SEED_BLUEPRINT_CONTEXT[blueprint_id]}, {"seed_frame"}
    if question_family_id == "backup":
        return {_BACKUP_BLUEPRINT_CONTEXT[blueprint_id]}, {"backup"}
    if question_family_id == "v2_direct_probe":
        # 2026-08-23 2단계 §7: Direct Probe Blueprint는 Seed/Backup처럼 Context·Frame이
        # 그 Blueprint 하나에 고정된다(`allowed_context_ids`/`question_frame_id`) —
        # Tail Blueprint처럼 아무 Context·Frame에서나 쓰이는 게 아니다.
        v2_bp = V2_DIRECT_PROBE_BLUEPRINTS_BY_ID[blueprint_id]
        return set(v2_bp.allowed_context_ids), {v2_bp.question_frame_id}
    # "tail_blueprint" — Blueprint와 Context·Frame이 독립 축이라 구조적 상한을 그대로 쓴다.
    return set(_ALL_TAIL_CONTEXT_IDS), set(_ALL_TAIL_FRAME_IDS)


def _compute_capabilities() -> dict[str, TraitProbeCapability]:
    capabilities: dict[str, TraitProbeCapability] = {
        trait_id: TraitProbeCapability(trait_id=trait_id) for trait_id in CORE_TRAIT_IDS
    }
    for key, signals in all_registrations().items():
        contexts, frames = _reachable_context_and_frame_ids(key.question_family_id, key.blueprint_id)
        for signal in signals:
            cap = capabilities[signal.trait_id]
            cap.blueprint_ids.add(key.blueprint_id)
            cap.context_ids |= contexts
            cap.frame_ids |= frames
            if signal.signal_role == "PRIMARY":
                cap.primary_probe_count += 1
            else:
                cap.related_probe_count += 1
    return capabilities


TRAIT_PROBE_CAPABILITIES: dict[str, TraitProbeCapability] = _compute_capabilities()


def _compute_directly_measurable() -> frozenset[str]:
    """§7 DIRECTLY_MEASURABLE 정의: PRIMARY Signal이 존재하고, "그 PRIMARY Signal을 낸"
    Blueprint가 2개 이상이며, 그 Blueprint들만 놓고 봐도 서로 다른 Frame 2개 이상 또는
    Context 2개 이상에서 직접 확인 가능해야 한다 — RELATED만 있는 Blueprint를 섞어서
    Blueprint 다양성을 부풀리지 않는다(그러면 "PRIMARY로 직접 확인 가능"이라는 원래
    의미가 흐려진다)."""

    primary_only: dict[str, dict[str, set[str]]] = {}
    for key, signals in all_registrations().items():
        primary_trait_ids = {s.trait_id for s in signals if s.signal_role == "PRIMARY"}
        if not primary_trait_ids:
            continue
        contexts, frames = _reachable_context_and_frame_ids(key.question_family_id, key.blueprint_id)
        for trait_id in primary_trait_ids:
            tracked = primary_only.setdefault(
                trait_id, {"blueprint_ids": set(), "context_ids": set(), "frame_ids": set()}
            )
            tracked["blueprint_ids"].add(key.blueprint_id)
            tracked["context_ids"] |= contexts
            tracked["frame_ids"] |= frames

    return frozenset(
        trait_id
        for trait_id, tracked in primary_only.items()
        if len(tracked["blueprint_ids"]) >= 2 and (len(tracked["frame_ids"]) >= 2 or len(tracked["context_ids"]) >= 2)
    )


DIRECTLY_MEASURABLE_TRAIT_IDS: frozenset[str] = _compute_directly_measurable()

RELATED_ONLY_TRAIT_IDS: frozenset[str] = frozenset(
    trait_id
    for trait_id, cap in TRAIT_PROBE_CAPABILITIES.items()
    if cap.related_probe_count > 0 and trait_id not in DIRECTLY_MEASURABLE_TRAIT_IDS
)

OBSERVABLE_TRAIT_IDS: frozenset[str] = frozenset(
    trait_id
    for trait_id, cap in TRAIT_PROBE_CAPABILITIES.items()
    if cap.primary_probe_count > 0 or cap.related_probe_count > 0
)

NOT_PROBED_TRAIT_IDS: frozenset[str] = frozenset(CORE_TRAIT_IDS - OBSERVABLE_TRAIT_IDS)
