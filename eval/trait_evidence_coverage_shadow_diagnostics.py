"""Trait Evidence Coverage "전체 Inventory 상한" 진단 Harness (보조 자료) —
a/trait-evidence-coverage-shadow.

**중요한 정정(후속 라운드)**: 이 파일이 재는 158문항/52~56문항 권고는 **실제 4+1/2+1
세션이 아니다** — 15개 Context와 각 Context의 Anchor 5개 전부를 순회한 "Inventory
상한" 수치다. **실제 세션 결과는
`eval/trait_evidence_coverage_session_diagnostics.py`를 보라** — 그쪽이 이제
`outputs/evaluation/trait_evidence_coverage_shadow_report.{json,md}`(주 보고서)를
쓴다. 이 파일의 산출물은 `trait_evidence_coverage_inventory_ceiling_report.{json,md}`
로 이름을 바꿔 "실제 세션 결과와 명확히 분리"했다(정정 지시 §7) — 완전히 삭제하지
않은 이유는 "Context/Anchor를 전부 열었을 때 구조적으로 몇 개까지 가능한가"라는
별도로 유용한 참고 질문에 계속 답하기 때문이다.

**진단 전용이다.** Runtime Stop Condition·Matching·질문 흐름·`src/api/main.py`·공개
Schema 어디에도 연결하지 않는다. LLM·네트워크·DB를 호출하지 않는다 — 실제 저장소에
이미 존재하는 고정 콘텐츠(Seed·Backup·Anchor Backup·V2 Direct Probe·ContextPack)만
읽어 결정론적으로 시뮬레이션한다.

## 무엇을 시뮬레이션하는가

Adaptive Tail(LLM 생성) 질문은 결정론적으로 재현할 수 없어 이 진단에서 제외한다 —
대신 "이 Context에 실제로 존재하는 고정 콘텐츠 전부"(Seed·Backup·Anchor Backup·Direct
Probe)를 그 Context의 가용 질문 Pool로 삼는다. 이건 "한 세션이 실제로 거치는 경로"가
아니라 **그 Context가 구조적으로 제공할 수 있는 최대 재료**를 보는 것이다 — 진단
목적("실제 충족 가능한 Trait 수")에 맞는 선택이다(§ 아래 "설계 결정과 한계" 참고).

## Persona 정책 — Coverage 최대화 결정론적 선택

질문마다 5개 선택지 중 "지금까지 누적된 effective_evidence_weight가 가장 낮은
Trait"를 가리키는 선택지를 고른다(동점이면 trait_id 알파벳 순, 그다음 선택지 순서).
이건 "그럴듯한 학생"을 흉내 내는 게 아니라 **한정된 질문 수 안에서 몇 개 Trait를
SUFFICIENT까지 끌어올릴 수 있는가라는 상한(Ceiling)을 재는 정책**이다 — 실제
Adaptive Target Planner(§8, 수정 금지)의 Gap 우선순위 로직과는 다르다.

## 두 환경

- **A. 현재 3 Context**(game/media/school_life) — 실제 저장소의 검수 상태를 그대로
  읽는다(수정하지 않는다). V2 Direct Probe 14개가 전부 TBD, 기존 Backup 6개가 전부
  REVISE라 이 둘은 승인 Evidence로 계산되지 않는다 — 이것도 실측이지 가정이 아니다.
- **B. 임시 승인 Fixture 기반 15 Context**(3 Legacy + 12 ContextPack) — 12개 Pack의
  검수 상태만 `tempfile`에 만든 가짜 전부-APPROVE Fixture로 대체한다
  (`ContextPackRegistry(review_status_dir=...)` 주입, `data/reviews/` 원본은 절대
  건드리지 않는다). Legacy 3 Context는 A와 동일하게 실제 상태를 그대로 쓴다.

## 설계 결정과 한계(§8 보고서에도 다시 기록한다)

- "2+1"/"4+1" 흐름은 실제 Context 선택 정책(`contrast_context_selector.py`, 수정
  금지)의 세션당 Context 개수 상한을 가리킨다. 이 진단은 그 상한을 그대로 재현하지
  않는다 — 대신 "그 Context 풀 전체가 제공하는 재료로 최대 몇 Trait를 채울 수 있는가"
  라는 상한 질문에 답하도록 설계를 단순화했다(사람이 실제로 겪는 한 세션의 정확한
  질문 순서를 재현하는 것이 아니다).
- Adaptive Tail(LLM) 질문은 원천적으로 제외한다 — 결정론(§9)을 지킬 수 없기 때문이다.
  그래서 이 진단의 숫자는 "LLM 없이 고정 콘텐츠만으로 도달 가능한" 하한에 더 가깝다.
"""

from __future__ import annotations

import json
import sys
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.contexts.context_definitions import CONTEXT_IDS  # noqa: E402
from src.data.questions.anchor_backup_questions import ANCHOR_BACKUP_QUESTIONS  # noqa: E402
from src.data.questions.trait_v2_direct_probe_blueprints import (  # noqa: E402
    V2_DIRECT_PROBE_BLUEPRINTS,
)
from src.data.questions.vertical_slice_backup_questions import (  # noqa: E402
    VERTICAL_SLICE_BACKUP_QUESTIONS,
)
from src.data.questions.vertical_slice_seed_questions import (  # noqa: E402
    VERTICAL_SLICE_SEED_QUESTIONS,
)
from src.data.trait_ontology.trait_probe_capabilities_v2 import CORE_TRAIT_IDS  # noqa: E402
from src.engines.trait_evidence_coverage_engine import (  # noqa: E402
    SUFFICIENT_MIN_CONTEXT_COUNT,
    SUFFICIENT_MIN_PRIMARY_COUNT,
    compute_all_trait_coverage,
    coverage_status_breakdown,
)
from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin, EvidenceRecord  # noqa: E402
from src.schemas.trait_evidence_coverage import TraitCoverageResult  # noqa: E402
from src.services.context_pack_registry import ContextPackRegistry, discover_context_packs  # noqa: E402
from src.services.trait_signal_registry import (  # noqa: E402
    register_context_pack_signals,
    resolve_trait_signals,
)
from src.services.trait_signal_review_gate import is_evidence_signal_approved  # noqa: E402

VERTICAL_SLICE_CONTEXT_IDS: tuple[str, ...] = ("game", "media", "school_life")
QUESTION_CAPS: tuple[int, ...] = (20, 30, 40, 50)
JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_inventory_ceiling_report.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "trait_evidence_coverage_inventory_ceiling_report.md"

# Native pack_direct_probe 승인 판정은 anchor_id를 실제로 쓰지 않지만(§ 감사 결과,
# trait_signal_review_gate._pack_native_direct_probe_approved), 바깥 함수
# is_evidence_signal_approved는 context_anchor_choices에 None이 아닌 값이 있어야만
# 그 안쪽 판정까지 내려간다 — 그래서 구조적으로 필요한 자리표시자다(실제 값은 안 쓰인다).
_PACK_DIRECT_PROBE_ANCHOR_PLACEHOLDER = "__pack_direct_probe__"


@dataclass(frozen=True)
class SimOption:
    role_id: str
    target_trait_id: str | None  # None = NO_SIGNAL


@dataclass(frozen=True)
class SimQuestion:
    context_id: str
    anchor_id: str | None
    family: str
    blueprint_id: str
    question_id: str
    frame_id: str
    options: tuple[SimOption, ...]


def _legacy_pool() -> list[SimQuestion]:
    """실제 저장소의 game/media/school_life 고정 콘텐츠 전부(감사 결과 그대로,
    새 필드를 만들지 않는다)."""

    out: list[SimQuestion] = []
    for context_id, seed in VERTICAL_SLICE_SEED_QUESTIONS.items():
        bp_id = f"{seed.question_id}_blueprint"
        opts = tuple(
            SimOption(o.role_id, next(iter(o.primary_trait_delta), None)) for o in seed.options
        )
        # 실제 SeedQuestion 타입에는 frame_id가 없다 — 코드 전반의 관례("seed_frame")를
        # 그대로 쓴다(answer_graph.py의 `question.frame_id == "seed_frame"` 분기, demo
        # persona fixture와 동일).
        out.append(SimQuestion(context_id, None, "seed", bp_id, seed.question_id, "seed_frame", opts))

    for context_id, backups in VERTICAL_SLICE_BACKUP_QUESTIONS.items():
        for q in backups:
            opts = tuple(
                SimOption(o.role_id, next(iter(o.primary_trait_delta), None)) for o in q.options
            )
            out.append(SimQuestion(context_id, None, "backup", q.question_id, q.question_id, q.frame_id, opts))

    for q in ANCHOR_BACKUP_QUESTIONS:
        opts = tuple(
            SimOption(o.role_id, next(iter(o.primary_trait_delta), None)) for o in q.options
        )
        out.append(SimQuestion(q.context, None, "backup", q.question_id, q.question_id, q.frame_id, opts))

    for bp in V2_DIRECT_PROBE_BLUEPRINTS:
        for context_id in bp.allowed_context_ids:
            if context_id not in VERTICAL_SLICE_CONTEXT_IDS:
                continue
            opts = tuple(
                SimOption(m.role_id, m.primary_trait_id if m.mapping_type == "TRAIT_SIGNAL" else None)
                for m in bp.option_mappings
            )
            out.append(SimQuestion(
                context_id, None, "v2_direct_probe", bp.blueprint_id, bp.base_question.question_id,
                bp.question_frame_id, opts,
            ))
    return out


def _pack_pool(registry: ContextPackRegistry) -> list[SimQuestion]:
    """등록된(Ontology 검증 통과) 모든 ContextPack의 고정 콘텐츠. 검수 여부와 무관하게
    Pool에는 전부 넣는다 — 승인 여부는 나중에 Gate 단계에서만 걸러진다(Pool 자체는
    "구조적으로 존재하는 질문"을 그대로 보여줘야 진단이 정직하다)."""

    out: list[SimQuestion] = []
    for pack in registry.all_packs():
        for seed in pack.seed_anchor_variants:
            bp_id = f"{seed.question.question_id}_blueprint"
            opts = tuple(
                SimOption(o.role_id, next(iter(o.primary_trait_delta), None))
                for o in seed.question.options
            )
            out.append(SimQuestion(
                pack.context_id, seed.anchor_id, "seed", bp_id, seed.question.question_id,
                seed.question.frame_id, opts,
            ))
        for backup in pack.anchor_backup_questions:
            opts = tuple(
                SimOption(o.role_id, next(iter(o.primary_trait_delta), None))
                for o in backup.question.options
            )
            out.append(SimQuestion(
                pack.context_id, backup.anchor_id, "pack_backup", backup.question.question_id,
                backup.question.question_id, backup.question.frame_id, opts,
            ))
        for bp in pack.direct_probe_candidates:
            opts = tuple(
                SimOption(m.role_id, m.primary_trait_id if m.mapping_type == "TRAIT_SIGNAL" else None)
                for m in bp.option_mappings
            )
            out.append(SimQuestion(
                pack.context_id, _PACK_DIRECT_PROBE_ANCHOR_PLACEHOLDER, "pack_direct_probe",
                bp.blueprint_id, bp.base_question.question_id, bp.question_frame_id, opts,
            ))
    return out


def _interleave_by_context(pool: list[SimQuestion]) -> list[SimQuestion]:
    """Context 하나를 다 소진한 뒤 다음 Context로 넘어가지 않고, Context를 고르게
    번갈아 가며 순서를 만든다 — 그래야 앞쪽 문항 몇 개만 봐도 여러 Context가 섞여
    "Context 2개 이상" 조건을 이르게 만족할 기회가 생긴다(한 Context를 다 쓰고 다음
    Context로 넘어가는 순서는 그 조건을 인위적으로 늦춘다). 결정론: Context 이름
    알파벳 순, Context 내부는 Pool에 담긴 원래(소스 파일) 순서를 유지한다."""

    by_context: dict[str, list[SimQuestion]] = defaultdict(list)
    for q in pool:
        by_context[q.context_id].append(q)
    ordered_contexts = sorted(by_context)
    interleaved: list[SimQuestion] = []
    index = 0
    while True:
        added = False
        for context_id in ordered_contexts:
            bucket = by_context[context_id]
            if index < len(bucket):
                interleaved.append(bucket[index])
                added = True
        if not added:
            break
        index += 1
    return interleaved


def _build_registry_with_fixture_approval(fixture_dir: Path) -> ContextPackRegistry:
    """§7 "실제 review JSON을 수정하지 말고 tempfile의 임시 승인 데이터만 사용한다."
    `data/reviews/context_packs/`는 전혀 읽지 않는다 — `review_status_dir`를
    `fixture_dir`로 지정해 완전히 다른 디렉터리를 쓴다."""

    packs, discovery_errors = discover_context_packs()
    if discovery_errors:
        raise RuntimeError(f"ContextPack 발견 중 오류: {discovery_errors}")
    registry = ContextPackRegistry(
        known_context_ids=frozenset(CONTEXT_IDS),
        review_status_dir=fixture_dir,
        _discovered=(packs, {}),
    )
    for context_id, pack in packs.items():
        keys = sorted(registry.required_review_keys(pack))
        rows = [
            {
                "blueprint_id": key, "reviewer_1_status": "APPROVE", "reviewer_1_comment": "",
                "reviewer_2_status": "TBD", "reviewer_2_comment": "", "resolution_note": "",
            }
            for key in keys
        ]
        (fixture_dir / f"{context_id}_review_status.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8",
        )
        register_context_pack_signals(pack)
    return registry


def _select_option(
    question: SimQuestion, running_weight: dict[str, float]
) -> SimOption:
    """Coverage 최대화 정책 — 현재 누적 weight가 가장 낮은 Trait를 가리키는 선택지를
    고른다. NO_SIGNAL(target_trait_id=None) 선택지는 절대 고르지 않는다(상한 측정
    목적상 항상 정보가 있는 선택지를 고른다). 전부 NO_SIGNAL이면(구조적으로 발생하지
    않아야 하지만 방어적으로) 첫 선택지를 고른다."""

    candidates = [o for o in question.options if o.target_trait_id is not None]
    if not candidates:
        return question.options[0]
    return min(candidates, key=lambda o: (running_weight.get(o.target_trait_id, 0.0), o.target_trait_id))


def _simulate(
    pool: list[SimQuestion], registry: ContextPackRegistry | None,
) -> tuple[list[EvidenceRecord], list[bool]]:
    """결정론적 Coverage 최대화 Persona로 Pool 전체를 순서대로 답변한다. 두 번째
    반환값은 각 EvidenceRecord가 승인된 질문에서 나왔는지(index 대응)다 — 매 질문마다
    그 질문 하나만의 context_anchor_choices로 개별 판정한다(같은 Context라도 질문마다
    실제 Anchor가 다를 수 있으므로 세션 전역 dict 하나를 공유하면 안 된다)."""

    ledger: list[EvidenceRecord] = []
    approved_flags: list[bool] = []
    running_weight: dict[str, float] = {trait_id: 0.0 for trait_id in CORE_TRAIT_IDS}

    for question in pool:
        option = _select_option(question, running_weight)
        legacy_delta = {option.target_trait_id: 1} if option.target_trait_id else {}
        resolution = resolve_trait_signals(
            question_family_id=question.family, blueprint_id=question.blueprint_id,
            role_id=option.role_id, legacy_primary_trait_delta=legacy_delta,
            is_resolution_question=False,
        )
        signals = [
            AppliedTraitSignal(
                trait_id=s.trait_id, signal_role=s.signal_role, weight=s.weight,
                related_concept_ids=s.related_concept_ids,
            )
            for s in resolution.signals
        ]
        origin = (
            EvidenceOrigin.V2_DIRECT_PROBE if question.family in ("v2_direct_probe", "pack_direct_probe")
            else EvidenceOrigin.PRIMARY_BLUEPRINT
        )
        # §9 결정론성: `src.ids.generate_evidence_id()`는 uuid4라 재실행마다 값이
        # 달라진다 — 이 진단은 재현 가능한 evidence_id가 필요하므로 질문 내용에서
        # 결정론적으로 파생시킨다(생성 시각·난수 없음).
        evidence_id = f"shadow_ev_{len(ledger) + 1:04d}_{question.question_id}_{option.role_id}"
        record = EvidenceRecord(
            evidence_id=evidence_id,
            answer_id=f"ans_{len(ledger) + 1:04d}",
            question_id=question.question_id,
            question_frame_id=question.frame_id,
            option_role_id=option.role_id,
            option_text="(Shadow 진단 시뮬레이션)",
            applied_primary_trait_delta=legacy_delta,
            applied_trait_signals_v2=signals,
            trait_signal_mapping_source_v2=resolution.mapping_source,
            evidence_origin=origin,
            context=question.context_id,
            source_type=f"shadow_sim:{question.family}",
            generator_version="shadow_v1",
            quality_gate_status="passed",
            source_question_family_id=question.family,
            source_blueprint_id=question.blueprint_id,
        )
        anchor_choices = {question.context_id: question.anchor_id} if question.anchor_id else {}
        approved = is_evidence_signal_approved(record, anchor_choices, registry)

        ledger.append(record)
        approved_flags.append(approved)
        if approved:
            for s in signals:
                bump = 1.0 if s.signal_role == "PRIMARY" else 0.5
                running_weight[s.trait_id] = running_weight.get(s.trait_id, 0.0) + bump

    return ledger, approved_flags


def _approved_ids_at_prefix(
    ledger: list[EvidenceRecord], approved_flags: list[bool], prefix_len: int
) -> set[str]:
    return {r.evidence_id for r, ok in zip(ledger[:prefix_len], approved_flags[:prefix_len]) if ok}


def _context_of_trait_evidence(
    trait_id: str, results: dict[str, TraitCoverageResult], ledger_by_id: dict[str, EvidenceRecord]
) -> set[str]:
    return {ledger_by_id[eid].context for eid in results[trait_id].contributing_evidence_ids}


def _run_environment(
    label: str, pool: list[SimQuestion], registry: ContextPackRegistry | None,
) -> dict[str, Any]:
    ordered = _interleave_by_context(pool)
    ledger, approved_flags = _simulate(ordered, registry)
    ledger_by_id = {r.evidence_id: r for r in ledger}

    prefix_reports: dict[int, dict[str, TraitCoverageResult]] = {}
    caps_to_measure = sorted(set(QUESTION_CAPS) | {len(ordered)})
    for cap in caps_to_measure:
        if cap > len(ordered) and cap != len(ordered):
            continue
        prefix_len = min(cap, len(ordered))
        approved_ids = _approved_ids_at_prefix(ledger, approved_flags, prefix_len)
        prefix_reports[cap] = compute_all_trait_coverage(
            CORE_TRAIT_IDS, ledger[:prefix_len], approved_ids
        )

    full_results = prefix_reports[len(ordered)]

    # 상위 5~8개 Trait가 SUFFICIENT가 되는 시점(질문 수) — 질문 하나씩 늘려가며 다시
    # 계산한다(작은 Pool이라 비용 문제 없다, 최대 200여 문항).
    sufficient_first_at: dict[str, int | None] = {trait_id: None for trait_id in CORE_TRAIT_IDS}
    for n in range(1, len(ordered) + 1):
        approved_ids = _approved_ids_at_prefix(ledger, approved_flags, n)
        results_n = compute_all_trait_coverage(CORE_TRAIT_IDS, ledger[:n], approved_ids)
        for trait_id, result in results_n.items():
            if sufficient_first_at[trait_id] is None and result.coverage_status == "SUFFICIENT":
                sufficient_first_at[trait_id] = n
        if all(v is not None for v in sufficient_first_at.values()):
            break

    context_bias: dict[str, Counter] = defaultdict(Counter)
    for question in ordered:
        for option in question.options:
            if option.target_trait_id:
                context_bias[question.context_id][option.target_trait_id] += 1

    repeated_no_growth_traits = sorted(
        trait_id for trait_id in CORE_TRAIT_IDS
        if full_results[trait_id].coverage_status in ("UNOBSERVED", "LIMITED")
        and sum(1 for q in ordered for o in q.options if o.target_trait_id == trait_id) >= 4
    )

    context_2plus_impossible = sorted(
        trait_id for trait_id in CORE_TRAIT_IDS
        if len({q.context_id for q in ordered for o in q.options if o.target_trait_id == trait_id}) < 2
    )

    # §8 "질문 Mapping 부족인지 Persona 특성 때문인지 구분" — 승인된 질문 중 이 Trait를
    # 제시한 개수(선택 여부와 무관)로 원인을 가른다. 근거: SUFFICIENT는 Primary>=2·
    # Context>=2가 필요하니, 승인된 기회 자체가 그 밑이면 Persona가 무엇을 고르든
    # 도달 불가능하다(Mapping 부족) — 기회는 충분한데 이 정책으로도 못 미쳤다면
    # 그건 이 Trait이 다른 Trait와 "경쟁에서 밀린" 정책 효과다.
    approved_opportunity_count: dict[str, int] = {trait_id: 0 for trait_id in CORE_TRAIT_IDS}
    approved_opportunity_contexts: dict[str, set[str]] = defaultdict(set)
    for question, is_approved in zip(ordered, approved_flags):
        if not is_approved:
            continue
        for option in question.options:
            if option.target_trait_id:
                approved_opportunity_count[option.target_trait_id] += 1
                approved_opportunity_contexts[option.target_trait_id].add(question.context_id)

    gap_classification: dict[str, str] = {}
    for trait_id in CORE_TRAIT_IDS:
        if full_results[trait_id].coverage_status == "SUFFICIENT":
            gap_classification[trait_id] = "SUFFICIENT"
        elif approved_opportunity_count[trait_id] < SUFFICIENT_MIN_PRIMARY_COUNT:
            gap_classification[trait_id] = "MAPPING_GAP"
        elif len(approved_opportunity_contexts[trait_id]) < SUFFICIENT_MIN_CONTEXT_COUNT:
            gap_classification[trait_id] = "CONTEXT_GAP"
        else:
            gap_classification[trait_id] = "POLICY_LIMITED"

    return {
        "label": label,
        "total_available_questions": len(ordered),
        "distinct_contexts": sorted({q.context_id for q in ordered}),
        "family_breakdown": dict(Counter(q.family for q in ordered)),
        "approved_question_count": sum(approved_flags),
        "prefix_reports": prefix_reports,
        "full_results": full_results,
        "sufficient_first_at": sufficient_first_at,
        "context_bias": {k: dict(v.most_common(5)) for k, v in context_bias.items()},
        "repeated_no_growth_traits": repeated_no_growth_traits,
        "context_2plus_structurally_impossible": context_2plus_impossible,
        "approved_opportunity_count": approved_opportunity_count,
        "gap_classification": gap_classification,
        "ledger_by_id": ledger_by_id,
    }


def run_diagnostics() -> dict[str, Any]:
    legacy_pool = _legacy_pool()
    env_a = _run_environment(
        "A. [Inventory 상한, 실제 세션 아님] 현재 3 Context 전체 고정 콘텐츠", legacy_pool, None
    )

    with tempfile.TemporaryDirectory(prefix="trait_coverage_shadow_fixture_") as tmp:
        fixture_dir = Path(tmp)
        registry = _build_registry_with_fixture_approval(fixture_dir)
        pack_pool = _pack_pool(registry)
        env_b = _run_environment(
            "B. [Inventory 상한, 실제 세션 아님] 15 Context 전체 고정 콘텐츠(tempfile 임시 승인)",
            legacy_pool + pack_pool, registry,
        )

    return {"env_a": env_a, "env_b": env_b}


# ── 보고서 직렬화 ────────────────────────────────────────────────────────

def _serialize_results(results: dict[str, TraitCoverageResult]) -> dict[str, Any]:
    return {trait_id: r.model_dump() for trait_id, r in sorted(results.items())}


def _serialize_environment(env: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": env["label"],
        "total_available_questions": env["total_available_questions"],
        "distinct_contexts": env["distinct_contexts"],
        "family_breakdown": dict(sorted(env["family_breakdown"].items())),
        "approved_question_count": env["approved_question_count"],
        "coverage_status_breakdown_by_cap": {
            str(cap): coverage_status_breakdown(results)
            for cap, results in sorted(env["prefix_reports"].items())
        },
        "full_results": _serialize_results(env["full_results"]),
        "sufficient_first_at_question_count": dict(sorted(env["sufficient_first_at"].items())),
        "context_bias_top5_by_context": dict(sorted(env["context_bias"].items())),
        "repeated_no_growth_traits": env["repeated_no_growth_traits"],
        "context_2plus_structurally_impossible_traits": env["context_2plus_structurally_impossible"],
        "approved_opportunity_count_by_trait": dict(sorted(env["approved_opportunity_count"].items())),
        "gap_classification_by_trait": dict(sorted(env["gap_classification"].items())),
    }


def _top_n_sufficient_at(sufficient_first_at: dict[str, int | None], n: int) -> int | None:
    """상위 n개 Trait가 전부 SUFFICIENT가 되는 최소 질문 수. n개 미만이 도달했다면
    None(이 환경에서는 도달 불가)."""

    reached = sorted(v for v in sufficient_first_at.values() if v is not None)
    if len(reached) < n:
        return None
    return reached[n - 1]


def _cross_environment_summary(env_a: dict[str, Any], env_b: dict[str, Any]) -> dict[str, Any]:
    def _sufficient_count_at(env: dict[str, Any], cap: int) -> int | None:
        results = env["prefix_reports"].get(cap)
        if results is None:
            return None
        return coverage_status_breakdown(results)["SUFFICIENT"]

    # §9 결정론성: CORE_TRAIT_IDS는 set이라 프로세스마다 PYTHONHASHSEED가 달라지면
    # 순회 순서가 바뀐다(같은 프로세스 안에서는 안정적이라 단위 테스트로는 못 잡고,
    # 스크립트를 별도 프로세스로 두 번 실행해야 드러난다 — 실측으로 확인했다). Counter
    # 삽입 순서에 의존하는 tie-break(`most_common()`)를 쓰지 않고, 항상 trait_id
    # 문자열로 명시적 정렬한다.
    unobserved_frequency: Counter[str] = Counter()
    for env in (env_a, env_b):
        for trait_id, result in sorted(env["full_results"].items()):
            if result.coverage_status == "UNOBSERVED":
                unobserved_frequency[trait_id] += 1

    min_5 = _top_n_sufficient_at(env_b["sufficient_first_at"], 5)
    max_8 = _top_n_sufficient_at(env_b["sufficient_first_at"], 8)

    most_frequently_unobserved = sorted(
        unobserved_frequency, key=lambda trait_id: (-unobserved_frequency[trait_id], trait_id)
    )

    return {
        "env_a_sufficient_count_at_current_pool_size": {
            "pool_size": env_a["total_available_questions"],
            "sufficient_count": coverage_status_breakdown(env_a["full_results"])["SUFFICIENT"],
        },
        "sufficient_count_by_question_cap": {
            "env_a": {str(cap): _sufficient_count_at(env_a, cap) for cap in QUESTION_CAPS},
            "env_b": {str(cap): _sufficient_count_at(env_b, cap) for cap in QUESTION_CAPS},
        },
        "most_frequently_unobserved_traits": most_frequently_unobserved,
        "gap_classification_env_a": dict(sorted(env_a["gap_classification"].items())),
        "gap_classification_env_b": dict(sorted(env_b["gap_classification"].items())),
        "recommended_question_range": {
            "minimum": min_5,
            "maximum": max_8,
            "basis": (
                "B 환경(15 Context, 임시 승인 Fixture) 기준 — 상위 5개 Trait가 전부 "
                "SUFFICIENT가 되는 최소 질문 수를 최소값으로, 상위 8개가 전부 SUFFICIENT가 "
                "되는 질문 수를 최대값으로 잡았다. A 환경(현재 3 Context)은 현재 승인 상태로는 "
                "단 하나의 Trait도 SUFFICIENT에 도달하지 못해 권장 범위의 근거로 쓸 수 없다."
            ),
        },
        "runtime_integration_readiness": {
            "ready": False,
            "reasons": [
                "A 환경(현재 실제 승인 상태)에서 SUFFICIENT Trait 수가 0이다 — Coverage 기반 "
                "종료를 지금 Runtime에 연결하면 거의 모든 세션이 Stop 조건을 영원히 못 만족한다.",
                "V2 Direct Probe 14개가 전부 reviewer_1_status=TBD라 신규 12개 Trait의 유일한 "
                "PRIMARY 출처가 통째로 계산에서 빠진다 — 검수가 먼저 끝나야 한다.",
                "12개 ContextPack이 전부 미검수라 B 환경의 결과는 '검수가 끝난다면'이라는 "
                "가정 위의 상한일 뿐, 지금 당장 재현되는 상태가 아니다.",
                "이 진단은 Adaptive Tail(LLM 생성) 질문을 포함하지 않는다 — 실제 세션에는 "
                "이 진단이 보지 못한 질문 유형이 더 있다.",
            ],
        },
    }


def _write_json_report(diagnostics: dict[str, Any]) -> None:
    payload = {
        "coverage_policy": {
            "primary_weight": 1.0,
            "related_weight": 0.5,
            "no_signal_weight": 0.0,
            "sufficient_min_primary_count": SUFFICIENT_MIN_PRIMARY_COUNT,
            "sufficient_min_effective_weight": 3.0,
            "sufficient_min_context_count": SUFFICIENT_MIN_CONTEXT_COUNT,
            "sufficient_min_frame_count": 2,
            "sufficient_min_directional_consistency": 0.7,
        },
        "environments": {
            "env_a": _serialize_environment(diagnostics["env_a"]),
            "env_b": _serialize_environment(diagnostics["env_b"]),
        },
        "cross_environment_summary": _cross_environment_summary(diagnostics["env_a"], diagnostics["env_b"]),
        "note": (
            "이 문서는 실제 세션 결과가 아니라 15개 Context·Anchor 5개 전부를 순회한 "
            "'전체 Inventory 상한' 참고 자료다(정정 지시 §7) — 실제 4+1/2+1 세션 결과는 "
            "trait_evidence_coverage_shadow_report.json을 봐야 한다. 이 보고서는 "
            "Shadow(진단 전용) 산출물이다. Runtime Stop Condition·Matching·질문 흐름에 "
            "아직 연결되지 않았다. 생성 시각·메모리 값을 담지 않는다 — 같은 코드에서 "
            "재실행하면 byte-identical해야 한다."
        ),
    }
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {JSON_OUTPUT_PATH}")


def _fmt_status_row(breakdown: dict[str, int]) -> str:
    order = ("UNOBSERVED", "LIMITED", "SUPPORTED", "SUFFICIENT", "CONFLICTED")
    return " · ".join(f"{k} {breakdown.get(k, 0)}" for k in order)


def _write_markdown_report(diagnostics: dict[str, Any]) -> None:
    env_a, env_b = diagnostics["env_a"], diagnostics["env_b"]
    summary = _cross_environment_summary(env_a, env_b)

    lines: list[str] = [
        "# Trait Evidence Coverage — 전체 Inventory 상한 보고서 (참고 자료)",
        "",
        "> **이 문서는 실제 세션 결과가 아니다.** 15개 Context와 각 Context의 Anchor",
        "> 5개 전부를 순회한 \"구조적 상한\" 수치다 — 실제 4+1/2+1 세션 결과는",
        "> `outputs/evaluation/trait_evidence_coverage_shadow_report.md`를 봐야 한다.",
        "> 아래 \"권장 질문 수\"는 실제 세션 권장치로 쓰지 않는다(정정 지시 §7).",
        "",
        "브랜치 `a/trait-evidence-coverage-shadow`. **진단 전용이다** — Runtime Stop",
        "Condition·Matching·학생 API 어디에도 연결하지 않았다. 생성 시각을 담지 않는다",
        "(같은 코드로 재실행하면 이 파일과 byte-identical해야 한다).",
        "",
        "## 1. Coverage Policy 최종 기준",
        "",
        "**가중치** — PRIMARY 1.0 · 검수 승인된 RELATED 0.5 · NO_SIGNAL 0 · 승인되지 "
        "않은 Signal은 계산에서 제외 · 동일 blueprint_id+frame_id 반복은 1회만 인정",
        "(Registry의 실제 저장 weight 0.33/0.67과는 별개 — 이 Policy 전용 고정 상수다).",
        "",
        "**SUFFICIENT** — Primary 2개 이상 AND 유효 가중치 합계 3.0 이상 AND 서로 다른 "
        "Context 2개 이상 AND 서로 다른 Frame 2개 이상 AND 동일 방향 비율 70% 이상 AND "
        "unresolved conflict 없음(전부 동시 충족).",
        "",
        "**상태 판정 순서(우선순위)**:",
        "",
        "1. Primary·Related 둘 다 0건 → `UNOBSERVED`",
        "2. 미해결 Conflict 존재 또는 방향 일관성 70% 미만 → `CONFLICTED`",
        "3. 위 SUFFICIENT 6개 조건 전부 충족 → `SUFFICIENT`",
        "4. Primary 2개 이상 + Frame 2개 이상(전체 기준 미달) → `SUPPORTED`",
        "5. 그 외(한 Context/한 Frame에만 집중 등) → `LIMITED`",
        "",
        "> SUFFICIENT는 Trait가 높다는 뜻이 아니다 — 높음/낮음/상황 의존적을 판단할 만큼",
        "> 근거가 충분하다는 뜻으로만 쓴다.",
        "",
        "## 2. 실행 조건 요약",
        "",
        f"- **환경 A** — {env_a['label']}",
        f"  - Pool {env_a['total_available_questions']}문항(family: {env_a['family_breakdown']}), "
        f"승인 {env_a['approved_question_count']}문항",
        f"- **환경 B** — {env_b['label']}",
        f"  - Pool {env_b['total_available_questions']}문항(family: {env_b['family_breakdown']}), "
        f"승인 {env_b['approved_question_count']}문항",
        "- Persona 정책: 매 질문마다 '지금까지 누적 가중치가 가장 낮은 Trait'를 가리키는",
        "  선택지를 고르는 결정론적 Coverage 최대화 정책(실제 Adaptive Target Planner와",
        "  다르다 — §설계 결정과 한계 참고).",
        "",
        "## 3. 현재 3 Context 결과 (환경 A)",
        "",
        "| 질문 수 상한 | " + " · ".join(("UNOBSERVED", "LIMITED", "SUPPORTED", "SUFFICIENT", "CONFLICTED")) + " |",
        "|---|---|",
    ]
    for cap in sorted(env_a["prefix_reports"]):
        lines.append(f"| {cap} | {_fmt_status_row(coverage_status_breakdown(env_a['prefix_reports'][cap]))} |")
    lines += [
        "",
        f"- 약 20문항(cap=20) 시점 SUFFICIENT 수: "
        f"{coverage_status_breakdown(env_a['prefix_reports'].get(20, env_a['full_results']))['SUFFICIENT']}",
        f"- 전체 Pool({env_a['total_available_questions']}문항) 소진 시점 SUFFICIENT 수: "
        f"{coverage_status_breakdown(env_a['full_results'])['SUFFICIENT']}",
        "- 원인: V2 Direct Probe 14개 전원 `reviewer_1_status=TBD`(신규 12개 Trait의 유일한",
        "  PRIMARY 출처), 기존 Backup 6개 전원 `REVISE` — 둘 다 승인 Evidence 계산에서",
        "  제외된다(실측, 가정 아님). 실제 승인된 재료는 Seed 3개 + Anchor Backup 15개",
        f"  = {env_a['approved_question_count']}문항뿐이다.",
        f"- Context 2개 조건 때문에 구조적으로 SUFFICIENT 불가능한 Trait: "
        f"{', '.join(env_a['context_2plus_structurally_impossible']) or '(없음)'}",
        "",
        "## 4. 15 Context, 임시 승인 Fixture 결과 (환경 B)",
        "",
        "| 질문 수 상한 | " + " · ".join(("UNOBSERVED", "LIMITED", "SUPPORTED", "SUFFICIENT", "CONFLICTED")) + " |",
        "|---|---|",
    ]
    for cap in sorted(env_b["prefix_reports"]):
        lines.append(f"| {cap} | {_fmt_status_row(coverage_status_breakdown(env_b['prefix_reports'][cap]))} |")
    top8 = sorted(
        ((n, t) for t, n in env_b["sufficient_first_at"].items() if n is not None)
    )[:8]
    lines += [
        "",
        "**상위 Trait가 SUFFICIENT에 도달하는 시점(질문 수, 오름차순, 상위 8개):**",
        "",
        "| 순위 | Trait | 도달 질문 수 |",
        "|---|---|---|",
    ]
    for rank, (n, trait_id) in enumerate(top8, start=1):
        lines.append(f"| {rank} | {trait_id} | {n} |")
    lines += [
        "",
        f"- Context 2개 조건 때문에 구조적으로 SUFFICIENT 불가능한 Trait: "
        f"{', '.join(env_b['context_2plus_structurally_impossible']) or '(없음)'}",
        f"- 전체 Pool({env_b['total_available_questions']}문항) 소진해도 SUFFICIENT에 못 이른 Trait: "
        + (", ".join(sorted(t for t, n in env_b["sufficient_first_at"].items() if n is None)) or "(없음)"),
        "",
        "## 5. 가장 자주 미관찰(UNOBSERVED)로 남는 Trait",
        "",
        (", ".join(summary["most_frequently_unobserved_traits"]) if summary["most_frequently_unobserved_traits"]
         else "(두 환경 모두 UNOBSERVED로 남은 Trait 없음)"),
        "",
        "## 6. 원인 구분 — 질문 Mapping 부족 vs Persona 특성",
        "",
        "`MAPPING_GAP`(승인된 기회 자체가 Primary 2개 미만 — Persona가 무엇을 골라도",
        "SUFFICIENT 불가) / `CONTEXT_GAP`(기회는 있지만 Context가 1개뿐) /",
        "`POLICY_LIMITED`(기회·Context 조건은 충분한데 이 Coverage 최대화 정책으로도",
        "SUFFICIENT까지 못 감 — 실제 Persona 다양성 문제에 더 가깝다) / `SUFFICIENT`.",
        "",
        "| Trait | 환경 A | 환경 B |",
        "|---|---|---|",
    ]
    for trait_id in sorted(CORE_TRAIT_IDS):
        lines.append(
            f"| {trait_id} | {env_a['gap_classification'][trait_id]} | "
            f"{env_b['gap_classification'][trait_id]} |"
        )
    lines += [
        "",
        "## 7. 권장 최소·최대 질문 수",
        "",
        f"- 최소 {summary['recommended_question_range']['minimum']}문항 — "
        "상위 5개 Trait가 SUFFICIENT에 도달",
        f"- 최대 {summary['recommended_question_range']['maximum']}문항 — "
        "상위 8개 Trait가 SUFFICIENT에 도달",
        f"- 근거: {summary['recommended_question_range']['basis']}",
        "",
        "## 8. Coverage 기반 종료를 Runtime에 연결해도 되는가",
        "",
        f"**{'가능' if summary['runtime_integration_readiness']['ready'] else '아직 이르다'}**",
        "",
    ]
    for reason in summary["runtime_integration_readiness"]["reasons"]:
        lines.append(f"- {reason}")
    lines += [
        "",
        "## 9. 설계 결정과 한계",
        "",
        "- Adaptive Tail(LLM 생성) 질문은 결정론을 지킬 수 없어 이 진단에 포함하지",
        "  않았다 — 이 보고서의 숫자는 '고정 콘텐츠만으로 도달 가능한' 하한에 가깝다.",
        "- '2+1'/'4+1'은 실제 세션의 Context 개수 상한(수정 금지)이다. 이 진단은 그",
        "  상한을 그대로 재현하지 않고, 해당 Context 풀 전체가 제공하는 재료의 상한을",
        "  본다(§설계 결정, 스크립트 docstring 참고).",
        "- Persona는 '그럴듯한 학생'이 아니라 Coverage를 의도적으로 최대화하는",
        "  결정론적 정책이다 — 실제 Adaptive Target Planner의 Gap 우선순위 로직과",
        "  다르다.",
        "- 환경 B의 12개 ContextPack 승인은 전부 `tempfile` 안의 가짜 Fixture다.",
        "  `data/reviews/`는 이 스크립트 실행 전후로 바이트 하나도 바뀌지 않는다.",
    ]

    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    diagnostics = run_diagnostics()
    _write_json_report(diagnostics)
    _write_markdown_report(diagnostics)


if __name__ == "__main__":
    main()
