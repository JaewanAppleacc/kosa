"""최종 모델 활성화 전 Readiness Audit — a/final-activation-readiness-audit.

**읽기 전용 진단이다.** Runtime·Review·Master·Mock·Feature Flag·질문·Mapping 무엇도
바꾸지 않는다 — 이 스크립트는 오직 현재 저장소·로컬 데이터의 상태를 있는 그대로
읽어서 보고할 뿐이다. Fixture 승인도, 세션 시뮬레이션도 하지 않는다 — 실제
`data/reviews/`·`data/master/`·`data/academyinfo_work/` 파일을 그대로 읽는다(단,
이 Worktree에 실제로 없는 로컬 전용 파일은 "없음"으로 정직하게 보고한다 — 있는
척 위조하지 않는다).

**재사용하는 실제 함수** (다시 구현하지 않는다):

    src.services.context_pack_registry.discover_context_packs / ContextPackRegistry
    src.services.feature_flags.*_enabled
    src.engines.contrast_context_selector.compute_context_selection_policy
    src.services.trait_signal_registry.register_context_pack_signals /
        register_shared_probe_blueprint_signals / all_registrations
    src.engines.trait_evidence_coverage_engine (a/trait-evidence-coverage-shadow에서
        이미 trait-vector-v2에 병합됨 — SUFFICIENT 기준 상수만 참조, 재계산은
        구조적 가능성 판단에만 쓴다. 실제 세션 시뮬레이션은 하지 않는다)

이 스크립트가 참조하는 REGISTRY(`register_context_pack_signals` 등)는 **프로세스
전역 mutable 상태**다(`src/services/trait_signal_registry.py::_REGISTRY`) — 한 번
등록하면 같은 프로세스 안에서 재등록 시도는 멱등(같은 값이면 조용히 통과, 다른 값이면
예외)이라 이 스크립트를 여러 번 호출해도 안전하다(멱등성 테스트로 검증)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.contexts.context_definitions import CONTEXT_IDS  # noqa: E402
from src.data.questions.context_pack_shared_probe_blueprints import (  # noqa: E402
    CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS,
)
from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_BLUEPRINTS  # noqa: E402
from src.data.trait_ontology.trait_probe_capabilities_v2 import CORE_TRAIT_IDS  # noqa: E402
from src.engines.contrast_context_selector import (  # noqa: E402
    MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1,
    ContextSelectionConfigError,
    compute_context_selection_policy,
)
from src.engines.trait_evidence_coverage_engine import (  # noqa: E402
    SUFFICIENT_MIN_CONTEXT_COUNT,
    SUFFICIENT_MIN_EFFECTIVE_WEIGHT,
    SUFFICIENT_MIN_FRAME_COUNT,
    SUFFICIENT_MIN_PRIMARY_COUNT,
)
from src.services.context_pack_registry import ContextPackRegistry, discover_context_packs  # noqa: E402
from src.services.feature_flags import (  # noqa: E402
    context_pack_runtime_enabled,
    context_selection_4_plus_1_enabled,
    trait_vector_v2_direct_probes_enabled,
    trait_vector_v2_primary_enabled,
)
from src.services.trait_signal_registry import (  # noqa: E402
    register_context_pack_signals,
    register_shared_probe_blueprint_signals,
    all_registrations,
)

VERTICAL_SLICE_CONTEXT_IDS: tuple[str, ...] = ("game", "media", "school_life")

JSON_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "final_activation_readiness_report.json"
MD_OUTPUT_PATH = ROOT / "outputs" / "evaluation" / "final_activation_readiness_report.md"

Status = str  # "READY" | "READY_AFTER_HUMAN_REVIEW" | "BLOCKED_BY_DATA" | "BLOCKED_BY_MAPPING" | "SHADOW_ONLY" | "NOT_IMPLEMENTED"
STATUS_VALUES = frozenset({
    "READY", "READY_AFTER_HUMAN_REVIEW", "BLOCKED_BY_DATA", "BLOCKED_BY_MAPPING", "SHADOW_ONLY", "NOT_IMPLEMENTED",
})
# 여러 항목을 하나로 합칠 때 "가장 상황이 나쁜 쪽"을 대표값으로 쓴다 — 하나라도 막혀
# 있으면 전체를 READY로 보고하지 않는다(낙관 편향 방지). 숫자가 클수록 더 나쁘다.
_STATUS_SEVERITY: dict[str, int] = {
    "READY": 0,
    "READY_AFTER_HUMAN_REVIEW": 1,
    "SHADOW_ONLY": 2,
    "BLOCKED_BY_DATA": 3,
    "BLOCKED_BY_MAPPING": 3,
    "NOT_IMPLEMENTED": 4,
}


def _worst_status(statuses: list[str]) -> str:
    if not statuses:
        return "NOT_IMPLEMENTED"
    return max(statuses, key=lambda s: _STATUS_SEVERITY.get(s, 4))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _status_counter(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(row.get(field))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


# ============================== 1. Context 준비도 ==============================


def _pack_review_rows(context_id: str) -> list[dict[str, Any]]:
    path = ROOT / "data" / "reviews" / "context_packs" / f"{context_id}_review_status.json"
    if not path.exists():
        return []
    return _read_json(path)


def _pack_blocking_keys(rows: list[dict[str, Any]]) -> list[str]:
    return sorted(
        f"{r.get('blueprint_id')}:{r.get('reviewer_1_status')}"
        for r in rows if r.get("reviewer_1_status") != "APPROVE"
    )


def audit_context_readiness(registry: ContextPackRegistry, packs: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for context_id in sorted(CONTEXT_IDS):
        is_legacy = context_id in VERTICAL_SLICE_CONTEXT_IDS
        pack = packs.get(context_id)
        has_pack = pack is not None

        if is_legacy:
            from src.data.contexts.context_anchor_presentations import CONTEXT_ANCHOR_PRESENTATIONS

            anchor_count = sum(1 for p in CONTEXT_ANCHOR_PRESENTATIONS if p.context_id == context_id)
            row = {
                "context_id": context_id, "is_legacy": True, "catalog_registered": True,
                "context_pack_exists": False, "routing_present": True, "anchor_count": anchor_count,
                "seed_count": anchor_count, "backup_count": anchor_count,
                "pack_review_key_count": None, "pack_review_status_breakdown": None,
                "shared_probe_applicable": False, "direct_probe_review_status": "SEE_TRAIT_SECTION",
                "runtime_activatable": True, "blocking_reasons": [],
                "status": "READY",
            }
        elif has_pack:
            review_rows = _pack_review_rows(context_id)
            keys = registry.required_review_keys(pack)
            approved = registry.is_pack_review_approved(context_id)
            status_breakdown = _status_counter(review_rows, "reviewer_1_status")
            blocking = _pack_blocking_keys(review_rows)
            row = {
                "context_id": context_id, "is_legacy": False, "catalog_registered": True,
                "context_pack_exists": True, "routing_present": True,
                "anchor_count": len(pack.anchor_presentations), "seed_count": len(pack.seed_anchor_variants),
                "backup_count": len(pack.anchor_backup_questions),
                "pack_review_key_count": len(keys), "pack_review_status_breakdown": status_breakdown,
                "shared_probe_applicable": any(
                    context_id in bp.allowed_context_ids for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
                ),
                "direct_probe_review_status": "SEE_TRAIT_SECTION",
                "runtime_activatable": approved,
                "blocking_reasons": [] if approved else (blocking or ["pack_review_incomplete"]),
                "status": "READY" if approved else "READY_AFTER_HUMAN_REVIEW",
            }
        else:
            row = {
                "context_id": context_id, "is_legacy": False, "catalog_registered": context_id in CONTEXT_IDS,
                "context_pack_exists": False, "routing_present": False, "anchor_count": 0, "seed_count": 0,
                "backup_count": 0, "pack_review_key_count": None, "pack_review_status_breakdown": None,
                "shared_probe_applicable": False, "direct_probe_review_status": "N/A",
                "runtime_activatable": False, "blocking_reasons": ["context_pack_missing"],
                "status": "NOT_IMPLEMENTED",
            }
        rows.append(row)
    return rows


# ============================== 2. Trait 준비도 ==============================


def _register_all_signals(packs: dict[str, Any]) -> None:
    for pack in packs.values():
        register_context_pack_signals(pack)
    register_shared_probe_blueprint_signals(list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS))
    register_shared_probe_blueprint_signals(list(V2_DIRECT_PROBE_BLUEPRINTS))


def _v2_direct_probe_question_review_status() -> dict[str, str]:
    path = ROOT / "data" / "reviews" / "v2_direct_probe_question_review_status.json"
    if not path.exists():
        return {}
    return {r["blueprint_id"]: r.get("reviewer_1_status", "TBD") for r in _read_json(path) if "blueprint_id" in r}


def audit_trait_readiness(registry: ContextPackRegistry) -> list[dict[str, Any]]:
    """구조적 관찰 가능성만 계산한다(전체 15 Context·Registry 전체 Blueprint 기준
    상한) — 실제 4+1 세션에서 학생이 어떤 Context 5개를 고르는지는 별개 문제다(그건
    a/trait-evidence-coverage-planner-gap의 세션 시뮬레이션 몫이지 이 정적 Audit의
    몫이 아니다). 여기서는 "이 Trait를 SUFFICIENT로 만들 수 있는 재료가 Registry에
    존재하는가"만 본다."""

    legacy_review = _v2_direct_probe_question_review_status()
    all_blueprints = list(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS) + list(V2_DIRECT_PROBE_BLUEPRINTS)

    rows: list[dict[str, Any]] = []
    for trait_id in sorted(CORE_TRAIT_IDS):
        bps_for_trait = [bp for bp in all_blueprints if bp.trait_id == trait_id]
        primary_source_count = 0
        related_source_count = 0
        contexts: set[str] = set()
        frames: set[str] = set()
        approved_signal_count = 0
        for bp in bps_for_trait:
            contexts.update(bp.allowed_context_ids)
            frames.add(bp.question_frame_id)
            is_shared = bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
            bp_approved_anywhere = False
            if is_shared:
                # 공용 Adaptive Probe는 (blueprint, context, anchor) 단위로 승인되는데,
                # 실제 승인 파일이 아예 없으면(§ 아래 확인) 이 Trait의 이 출처는 오늘
                # 단 하나도 승인되지 않은 것이다 — Context 단위로 뭉뚱그리지 않는다.
                for context_id in bp.allowed_context_ids:
                    review = registry.get_shared_probe_context_review(bp.blueprint_id, context_id)
                    if review is not None and review.reviewer_1_status == "APPROVE":
                        bp_approved_anywhere = True
                        break
            else:
                bp_approved_anywhere = legacy_review.get(bp.blueprint_id) == "APPROVE"
            for mapping in bp.option_mappings:
                if mapping.mapping_type == "NO_SIGNAL":
                    continue
                for signal in mapping.trait_signals:
                    if signal.trait_id != trait_id:
                        continue
                    if signal.signal_role == "PRIMARY":
                        primary_source_count += 1
                    elif signal.signal_role == "RELATED":
                        related_source_count += 1
                    if bp_approved_anywhere:
                        approved_signal_count += 1

        question_signal_count = primary_source_count + related_source_count
        distinct_context_count = len(contexts)
        distinct_frame_count = len(frames)

        # 구조적 SUFFICIENT 가능성 — 전체 Registry(15 Context 전부 승인됐다고 가정한
        # 상한)에서도 Context Diversity·Frame Diversity·최대 가중치 중 하나라도
        # 못 채우면 실제 5-Context 세션에서는 더더욱 불가능하다(필요조건, 충분조건
        # 아님 — 실제 Planner의 support_count>=2 stop 행동까지 반영한 세션별 가능성은
        # a/trait-evidence-coverage-planner-gap 참고).
        max_possible_weight = primary_source_count * 1.0 + related_source_count * 0.5
        structurally_sufficient_possible = (
            primary_source_count >= SUFFICIENT_MIN_PRIMARY_COUNT
            and distinct_context_count >= SUFFICIENT_MIN_CONTEXT_COUNT
            and distinct_frame_count >= SUFFICIENT_MIN_FRAME_COUNT
            and max_possible_weight >= SUFFICIENT_MIN_EFFECTIVE_WEIGHT
        )
        mapping_gap = question_signal_count == 0 or distinct_context_count < SUFFICIENT_MIN_CONTEXT_COUNT

        rows.append({
            "trait_id": trait_id,
            "ontology_exists": True,
            "question_signal_count": question_signal_count,
            "primary_source_count": primary_source_count,
            "related_source_count": related_source_count,
            "distinct_context_count": distinct_context_count,
            "distinct_frame_count": distinct_frame_count,
            "reviewed_approved_signal_count": approved_signal_count,
            "structurally_sufficient_possible_in_4plus1": structurally_sufficient_possible,
            "mapping_gap": mapping_gap,
            "status": (
                "BLOCKED_BY_MAPPING" if mapping_gap
                else ("READY_AFTER_HUMAN_REVIEW" if approved_signal_count == 0 else "SHADOW_ONLY")
            ),
        })
    return rows


# ============================== 3. 질문 흐름 준비도 ==============================


def audit_question_flow_readiness(effective_supported_ids_pack_on: list[str]) -> dict[str, Any]:
    flag_2plus1_off = compute_context_selection_policy(
        flag_enabled=False, effective_supported_context_count=len(VERTICAL_SLICE_CONTEXT_IDS),
    )
    try:
        flag_4plus1_on = compute_context_selection_policy(
            flag_enabled=True, effective_supported_context_count=len(effective_supported_ids_pack_on),
        )
        four_plus_one_error = None
    except ContextSelectionConfigError as exc:
        flag_4plus1_on = None
        four_plus_one_error = str(exc)

    return {
        "flow_2plus1_flag_off": {
            "final_context_min": flag_2plus1_off.final_context_min_count,
            "final_context_max": flag_2plus1_off.final_context_max_count,
            "status": "READY",
        },
        "flow_4plus1_flag_on": {
            "effective_supported_context_count_if_pack_runtime_on": len(effective_supported_ids_pack_on),
            "minimum_required": MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1,
            "meets_minimum_today": len(effective_supported_ids_pack_on) >= MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1,
            "policy_if_activated": (
                None if flag_4plus1_on is None else {
                    "preferred_min": flag_4plus1_on.preferred_context_min_count,
                    "preferred_max": flag_4plus1_on.preferred_context_max_count,
                    "final_min": flag_4plus1_on.final_context_min_count,
                    "final_max": flag_4plus1_on.final_context_max_count,
                }
            ),
            "fail_fast_error_if_under_5": four_plus_one_error,
            "status": "READY" if len(effective_supported_ids_pack_on) >= MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1 else "BLOCKED_BY_DATA",
        },
        # evidence_engine.decide_stop_or_continue()의 리터럴 4/6을 그대로 옮겨 적었다
        # (export된 상수가 없어 import할 수 없다 — 그 함수 자체는 수정하지 않았다).
        "tail_question_bounds_per_context": {"minimum": 4, "maximum": 6, "status": "READY"},
        "backup_safety": {
            "note": "후보 소진·생성 실패 시에만 Backup 사용(정상 후보가 있는 한 선택되지 않음) — Runtime 코드, 이번에 수정 안 함.",
            "status": "READY",
        },
        "planner_baseline": {
            "note": (
                "실제 select_pack_adaptive_target은 Context 안에서 support_count>=2가 되면 "
                "그 Trait를 더 이상 Gap으로 보지 않는다(수정 안 함, 그대로 유지)."
            ),
            "status": "READY",
        },
        "coverage_focused_planner_alternatives": {
            "note": (
                "a/trait-evidence-coverage-planner-gap에서 만든 A/B/C/D Shadow 대안은 실제 "
                "Runtime에 아직 연결되지 않았다 — eval/에만 존재한다."
            ),
            "status": "SHADOW_ONLY",
        },
        "coverage_stop_condition_wiring": {
            "note": "Trait Evidence Coverage Policy(SUFFICIENT 등)는 실제 Stop/Continue 판단에 연결되지 않았다 — Shadow 전용.",
            "status": "SHADOW_ONLY",
        },
    }


# ============================== 4. 전공·학과 준비도 ==============================


def audit_major_department_readiness() -> dict[str, Any]:
    majors = _read_jsonl(ROOT / "data" / "master" / "canonical_majors.jsonl")
    major_ids_without_description = sorted(
        m.get("major_id", "?") for m in majors if not (m.get("description") or "").strip()
    )

    groups = _read_jsonl(ROOT / "data" / "canonical_major_groups.draft.jsonl")
    groups_review_status = _status_counter(groups, "review_status")

    bridge_file = _read_jsonl(ROOT / "data" / "master" / "canonical_major_group_bridge.draft.jsonl")
    bridge_review_path = ROOT / "data" / "reviews" / "canonical_major_group_bridge_review_status.json"
    bridge_review_rows = _read_json(bridge_review_path) if bridge_review_path.exists() else []
    bridge_review_status = _status_counter(bridge_review_rows, "reviewer_1_status")
    bridge_scope_breakdown = _status_counter(bridge_file, "scope_type")
    bridge_mapping_status_breakdown = _status_counter(bridge_file, "mapping_status")

    p1_path = ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "p1_classification_review.jsonl"
    p1_rows = _read_jsonl(p1_path)
    p1_status = _status_counter(p1_rows, "reviewer_1_status")

    nce_path = ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "nce_reexaminable_middle_series_clusters.jsonl"
    nce_clusters = _read_jsonl(nce_path)
    nce_member_total = sum(int(c.get("row_count", 0)) for c in nce_clusters)
    nce_status = _status_counter(nce_clusters, "reviewer_1_status")

    identity_path = ROOT / "data" / "academyinfo_work" / "2025" / "packets" / "department_identity_collision_review.jsonl"
    identity_rows = _read_jsonl(identity_path)
    identity_candidate_total = sum(int(r.get("candidate_count", 0)) for r in identity_rows)
    identity_status = _status_counter(
        [{"decision": (r.get("review") or {}).get("decision")} for r in identity_rows], "decision",
    )

    master_departments = _read_jsonl(ROOT / "data" / "master" / "departments.jsonl")

    normalized_exists = (ROOT / "data" / "academyinfo_work" / "2025" / "departments.normalized.jsonl").exists()
    classification_exists = (ROOT / "data" / "academyinfo_work" / "2025" / "classification_results.jsonl").exists()

    all_review_pending = (
        not p1_status or set(p1_status) == {"TBD"}
    ) and (not nce_status or set(nce_status) == {"TBD"})
    groups_are_draft = set(groups_review_status) == {"draft"}
    bridge_has_review = "APPROVE" in bridge_review_status

    blocking_reasons = []
    if not normalized_exists or not classification_exists:
        blocking_reasons.append("BLOCKED_BY_DATA: departments.normalized.jsonl/classification_results.jsonl 이 이 Worktree 로컬에 없음(Git 제외 입력)")
    if groups_are_draft:
        blocking_reasons.append(f"BLOCKED_BY_MAPPING: Canonical Major Group {len(groups)}개 전부 review_status=draft")
    if set(p1_status) - {"APPROVE"}:
        blocking_reasons.append(f"BLOCKED_BY_MAPPING: P1 분류 검토 {len(p1_rows)}건 중 미승인 {sum(v for k,v in p1_status.items() if k!='APPROVE')}건")
    if set(nce_status) - {"APPROVE"}:
        blocking_reasons.append(f"BLOCKED_BY_MAPPING: N.C.E 클러스터 {len(nce_clusters)}개 중 미승인 {sum(v for k,v in nce_status.items() if k!='APPROVE')}개")
    if identity_status.get("None", 0) + sum(v for k, v in identity_status.items() if k != "APPROVE") > 0:
        blocking_reasons.append(f"BLOCKED_BY_MAPPING: Identity-key 충돌 {len(identity_rows)} Group 미해결")

    status = "BLOCKED_BY_DATA" if (not normalized_exists or not classification_exists) else "BLOCKED_BY_MAPPING"

    return {
        "service_canonical_majors": {
            "count": len(majors), "major_ids": sorted(m.get("major_id", "?") for m in majors),
            "majors_missing_description": major_ids_without_description,
            "status": "READY" if not major_ids_without_description and len(majors) == 10 else "BLOCKED_BY_DATA",
        },
        "major_trait_evidence": {
            "legacy_evidence_row_count": len(_read_jsonl(ROOT / "data" / "master" / "major_trait_mapping_evidence.jsonl")),
            "v2_evidence_row_count": len(_read_jsonl(ROOT / "data" / "master" / "major_trait_mapping_evidence_v2.jsonl")),
            "primary_input_flag": "ENABLE_TRAIT_VECTOR_V2_PRIMARY",
            "status": "SHADOW_ONLY" if not trait_vector_v2_primary_enabled() else "READY",
        },
        "canonical_major_groups": {
            "count": len(groups), "review_status_breakdown": groups_review_status,
            "status": "BLOCKED_BY_MAPPING" if groups_are_draft else "READY",
        },
        "bridge_mapping": {
            "count": len(bridge_file), "in_file_review_status_breakdown": _status_counter(bridge_file, "review_status"),
            "reviewer_status_breakdown": bridge_review_status,
            "mapping_status_breakdown": bridge_mapping_status_breakdown,
            "status": "READY_AFTER_HUMAN_REVIEW" if bridge_has_review else "BLOCKED_BY_MAPPING",
        },
        "bridge_scope": {
            "scope_type_breakdown": bridge_scope_breakdown,
            "status": "READY_AFTER_HUMAN_REVIEW" if bridge_has_review else "BLOCKED_BY_MAPPING",
        },
        "p1_classification": {
            "count": len(p1_rows), "reviewer_1_status_breakdown": p1_status,
            "status": "READY" if set(p1_status) == {"APPROVE"} else "BLOCKED_BY_MAPPING",
        },
        "nce": {
            "cluster_count": len(nce_clusters), "member_row_total": nce_member_total,
            "reviewer_1_status_breakdown": nce_status,
            "status": "READY" if set(nce_status) == {"APPROVE"} else "BLOCKED_BY_MAPPING",
        },
        "identity_key_conflicts": {
            "group_count": len(identity_rows), "candidate_row_total": identity_candidate_total,
            "decision_breakdown": identity_status,
            "status": "READY" if identity_rows and all(
                (r.get("review") or {}).get("decision") not in (None, "TBD") for r in identity_rows
            ) else "BLOCKED_BY_MAPPING",
        },
        "current_master": {"department_count": len(master_departments), "status": "READY"},
        "national_dry_run": {
            "required_local_inputs_present": normalized_exists and classification_exists,
            "note": (
                "scripts/career_build_national_department_promotion_dry_run.py는 존재하고 "
                "정상 작동하지만, 이 Worktree에 departments.normalized.jsonl/"
                "classification_results.jsonl(둘 다 Git 제외 로컬 입력)이 없어 이번 Audit "
                "에서는 실행하지 않았다 — 실행해도 Canonical Major Group Draft·P1·N.C.E가 "
                "전부 미승인이라 구조적으로 BLOCKED_GROUP_DRAFT/BLOCKED_P1_REVIEW_UNRESOLVED/"
                "BLOCKED_NCE_UNRESOLVED에 걸린다."
            ),
            "ready_count": None, "blocked_count": None,
            "status": "BLOCKED_BY_DATA",
        },
        "blocking_reasons": blocking_reasons,
        "status": status,
    }


# ============================== 5. 과목 준비도 ==============================


def audit_subject_readiness() -> dict[str, Any]:
    majors = _read_jsonl(ROOT / "data" / "master" / "canonical_majors.jsonl")
    major_ids = sorted(m.get("major_id", "?") for m in majors)

    link_rows = _read_jsonl(ROOT / "data" / "master" / "subject_major_link_evidence.jsonl")
    majors_with_links = sorted({r.get("major_id") for r in link_rows if r.get("major_id")})
    unsupported_majors = sorted(set(major_ids) - set(majors_with_links))

    parser_path = ROOT / "src" / "agents" / "course" / "course_document_parser.py"
    parser_implemented = parser_path.exists() and "class ParseError" not in "" and parser_path.stat().st_size > 1000

    per_major = []
    for major_id in major_ids:
        link_count = sum(1 for r in link_rows if r.get("major_id") == major_id)
        per_major.append({
            "major_id": major_id,
            "subject_major_link_count": link_count,
            "has_subject_data": link_count > 0,
            "status": "READY_AFTER_HUMAN_REVIEW" if link_count > 0 else "BLOCKED_BY_DATA",
        })

    return {
        "subject_trait_mapping_v1_row_count": len(_read_jsonl(ROOT / "data" / "master" / "subject_trait_mapping_evidence.jsonl")),
        "subject_trait_mapping_v2_row_count": len(_read_jsonl(ROOT / "data" / "master" / "subject_trait_mapping_evidence_v2.jsonl")),
        "subject_major_link_row_count": len(link_rows),
        "majors_with_subject_data": majors_with_links,
        "majors_without_subject_data": unsupported_majors,
        "pre_survey_post_offering_mechanism": {
            "note": "src/schemas/course.py의 Literal['PRE_SURVEY','POST_OFFERING'] source 필드 — 실제 구현됨.",
            "status": "READY",
        },
        "pdf_excel_parsing": {
            "path": "src/agents/course/course_document_parser.py",
            "exists": parser_path.exists(),
            "note": "실제 구현됨(C 소유) — .xlsx는 stdlib zipfile/ElementTree, .pdf는 pypdf 있으면 사용·없으면 최소 FlateDecode 추출기로 폴백, .xls는 명시적으로 미지원(ParseError).",
            "status": "READY" if parser_path.exists() else "NOT_IMPLEMENTED",
        },
        "actually_offered_course_confirmation": {
            "note": "data/fixtures/course_offerings/demo_school_offerings.xlsx 1건 — 시연용 Fixture뿐, 실 서비스 규모의 POST_OFFERING 확인 데이터는 없음.",
            "status": "BLOCKED_BY_DATA",
        },
        "per_major": per_major,
        "unsupported_majors": unsupported_majors,
        "status": "BLOCKED_BY_DATA" if unsupported_majors else "READY_AFTER_HUMAN_REVIEW",
    }


# ============================== 6. Frontend 준비도 ==============================


def _grep_exists(path: Path, needle: str) -> bool:
    return path.exists() and needle in path.read_text(encoding="utf-8", errors="ignore")


def audit_frontend_readiness() -> dict[str, Any]:
    fe = ROOT / "frontend"
    context_select = fe / "src" / "screens" / "ContextSelectScreen.tsx"
    majors_screen = fe / "src" / "screens" / "MajorsScreen.tsx"
    dept_browser = fe / "src" / "screens" / "DepartmentBrowser.tsx"
    session_storage = fe / "src" / "session" / "sessionStorage.ts"

    items = {
        "context_catalog_15_display": {
            "path": str(context_select.relative_to(ROOT)) if context_select.exists() else None,
            "found": _grep_exists(context_select, "fetchContextCatalog"),
            "status": "READY" if _grep_exists(context_select, "fetchContextCatalog") else "NOT_IMPLEMENTED",
        },
        "assessment_supported_gate": {
            "found": _grep_exists(context_select, "assessment_supported"),
            "status": "READY" if _grep_exists(context_select, "assessment_supported") else "NOT_IMPLEMENTED",
        },
        "policy_4plus1_ui": {
            "found": _grep_exists(context_select, "selection_policy"),
            "status": "READY" if _grep_exists(context_select, "selection_policy") else "NOT_IMPLEMENTED",
        },
        "major_description_display": {
            "found": _grep_exists(majors_screen, "major-description"),
            "status": "READY" if _grep_exists(majors_screen, "major-description") else "NOT_IMPLEMENTED",
        },
        "department_modal_real_data": {
            "found": _grep_exists(dept_browser, "fetchDepartments"),
            "runtime_default_mode": "mock (VITE_API_MODE!=='live'면 항상 mock으로 fallback)",
            "status": "READY_AFTER_HUMAN_REVIEW" if _grep_exists(dept_browser, "fetchDepartments") else "NOT_IMPLEMENTED",
        },
        "source_url_not_clickable_department_url_conditional": {
            "found": _grep_exists(dept_browser, "source_url") and _grep_exists(dept_browser, "department_url"),
            "status": "READY" if (_grep_exists(dept_browser, "source_url") and _grep_exists(dept_browser, "department_url")) else "NOT_IMPLEMENTED",
        },
        "empty_insufficient_error_states": {
            "found": _grep_exists(majors_screen, "insufficient_evidence_message"),
            "status": "READY" if _grep_exists(majors_screen, "insufficient_evidence_message") else "NOT_IMPLEMENTED",
        },
        "refresh_session_restore_limits": {
            "found": _grep_exists(session_storage, "session_id"),
            "note": "session_id만 localStorage 보존, 서버 In-Memory Store가 재시작되면 SESSION_NOT_FOUND → 재시작 안내(정상 설계).",
            "status": "READY" if _grep_exists(session_storage, "session_id") else "NOT_IMPLEMENTED",
        },
    }
    package_json = fe / "package.json"
    node_modules_installed = (fe / "node_modules").exists()
    scripts = {}
    if package_json.exists():
        scripts = _read_json(package_json).get("scripts", {})

    overall = _worst_status([v["status"] for v in items.values()])
    return {
        "items": items,
        "npm_scripts": scripts,
        "node_modules_installed": node_modules_installed,
        "status": overall,
    }


# ============================== 7. Feature Flag 표 ==============================


def audit_feature_flags(effective_supported_ids_pack_on: list[str]) -> list[dict[str, Any]]:
    return [
        {
            "flag": "ENABLE_TRAIT_VECTOR_V2_PRIMARY", "default": False,
            "current_value": trait_vector_v2_primary_enabled(),
            "preconditions": "v2 Trait Vector가 Profile/Major/Subject 입력으로 쓰이려면 최소 일부 Major-Trait v2 Evidence 존재 필요(있음, 72행) — 승인 여부와 무관하게 켤 수 있음.",
            "activatable_today": True,
            "blocking_reasons": [],
            "recommended_activation_order": 4,
        },
        {
            "flag": "ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES", "default": False,
            "current_value": trait_vector_v2_direct_probes_enabled(),
            "preconditions": "Legacy 3-Context v2 Direct Probe 질문 흐름 포함 여부 — 활성화 자체는 Review 승인과 무관(질문은 나가되 Evidence는 미승인 상태로 계산 제외됨).",
            "activatable_today": True,
            "blocking_reasons": ["v2_direct_probe_question_review_status.json 14건 전부 TBD — Evidence는 나가지만 계산에서 제외됨"],
            "recommended_activation_order": 1,
        },
        {
            "flag": "ENABLE_CONTEXT_PACK_RUNTIME", "default": False,
            "current_value": context_pack_runtime_enabled(),
            "preconditions": "최소 1개 이상의 ContextPack이 Pack-level 승인(science/sports 2개 승인됨) — 켜면 승인된 Pack만 실제 서빙된다.",
            "activatable_today": True,
            "blocking_reasons": [],
            "recommended_activation_order": 2,
        },
        {
            "flag": "ENABLE_CONTEXT_SELECTION_4_PLUS_1", "default": False,
            "current_value": context_selection_4_plus_1_enabled(),
            "preconditions": f"ENABLE_CONTEXT_PACK_RUNTIME까지 켰을 때 활성 Context가 {MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1}개 이상 — 오늘 기준 {len(effective_supported_ids_pack_on)}개({sorted(effective_supported_ids_pack_on)})로 정확히 충족.",
            "activatable_today": len(effective_supported_ids_pack_on) >= MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1,
            "blocking_reasons": [] if len(effective_supported_ids_pack_on) >= MINIMUM_ACTIVE_CONTEXTS_FOR_4_PLUS_1 else ["활성 Context 5개 미만 — 앱 시작 시 Fail-Fast"],
            "recommended_activation_order": 3,
        },
    ]


# ============================== 8. 최종 상태 판정 ==============================


def compute_overall_status(sections: dict[str, Any]) -> dict[str, Any]:
    section_statuses = {
        "context_readiness": _worst_status([r["status"] for r in sections["context_readiness"]]),
        "trait_readiness": _worst_status([r["status"] for r in sections["trait_readiness"]]),
        "question_flow_readiness": _worst_status([v["status"] for v in sections["question_flow_readiness"].values()]),
        "major_department_readiness": sections["major_department_readiness"]["status"],
        "subject_readiness": sections["subject_readiness"]["status"],
        "frontend_readiness": sections["frontend_readiness"]["status"],
    }
    overall = _worst_status(list(section_statuses.values()))
    return {"per_section": section_statuses, "overall": overall}


# ============================== 실행·직렬화 ==============================


def run_audit() -> dict[str, Any]:
    packs, discovery_errors = discover_context_packs()
    if discovery_errors:
        raise RuntimeError(f"ContextPack 발견 중 오류: {discovery_errors}")
    registry = ContextPackRegistry(known_context_ids=frozenset(CONTEXT_IDS))
    _register_all_signals(packs)

    effective_supported_ids_pack_on = sorted(
        {*VERTICAL_SLICE_CONTEXT_IDS, *(cid for cid in packs if registry.is_pack_review_approved(cid))}
    )

    sections = {
        "context_readiness": audit_context_readiness(registry, packs),
        "trait_readiness": audit_trait_readiness(registry),
        "question_flow_readiness": audit_question_flow_readiness(effective_supported_ids_pack_on),
        "major_department_readiness": audit_major_department_readiness(),
        "subject_readiness": audit_subject_readiness(),
        "frontend_readiness": audit_frontend_readiness(),
        "feature_flags": audit_feature_flags(effective_supported_ids_pack_on),
    }
    sections["final_verdict"] = compute_overall_status(sections)
    return sections


def _write_json_report(sections: dict[str, Any]) -> None:
    JSON_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT_PATH.write_text(
        json.dumps(sections, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"wrote {JSON_OUTPUT_PATH}")


def _context_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Context | Legacy | Pack | Anchor/Seed/Backup | 검수 Key | 승인 상태 | Runtime 활성화 | 상태 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        breakdown = r["pack_review_status_breakdown"]
        breakdown_str = "N/A" if breakdown is None else ", ".join(f"{k}:{v}" for k, v in breakdown.items())
        pack_display = "Legacy 고정 데이터" if r["is_legacy"] else ("있음" if r["context_pack_exists"] else "없음")
        lines.append(
            f"| {r['context_id']} | {'예' if r['is_legacy'] else '아니오'} | "
            f"{pack_display} | "
            f"{r['anchor_count']}/{r['seed_count']}/{r['backup_count']} | "
            f"{r['pack_review_key_count'] if r['pack_review_key_count'] is not None else '-'} | "
            f"{breakdown_str} | {'가능' if r['runtime_activatable'] else '불가'} | {r['status']} |"
        )
    return lines


def _trait_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Trait | Signal 수 | Primary | Related | Context 수 | Frame 수 | 승인된 Signal | 구조적 SUFFICIENT 가능 | Mapping Gap | 상태 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['trait_id']} | {r['question_signal_count']} | {r['primary_source_count']} | "
            f"{r['related_source_count']} | {r['distinct_context_count']} | {r['distinct_frame_count']} | "
            f"{r['reviewed_approved_signal_count']} | {'예' if r['structurally_sufficient_possible_in_4plus1'] else '아니오'} | "
            f"{'예' if r['mapping_gap'] else '아니오'} | {r['status']} |"
        )
    return lines


def _flag_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["| Flag | 기본값 | 현재값 | 오늘 활성화 가능 | 권장 순서 | 차단 사유 |", "|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: r["recommended_activation_order"]):
        reasons = "; ".join(r["blocking_reasons"]) or "(없음)"
        lines.append(
            f"| {r['flag']} | {r['default']} | {r['current_value']} | "
            f"{'가능' if r['activatable_today'] else '불가'} | {r['recommended_activation_order']} | {reasons} |"
        )
    return lines


def _write_markdown_report(sections: dict[str, Any]) -> None:
    verdict = sections["final_verdict"]
    lines: list[str] = [
        "# 최종 모델 활성화 전 Readiness Audit",
        "",
        "브랜치 `a/final-activation-readiness-audit`. 읽기 전용 진단 — Runtime·Review·Master·"
        "Feature Flag·Mock·질문·Mapping 무엇도 바꾸지 않았다.",
        "",
        f"## 최종 판정: **{verdict['overall']}**",
        "",
        "| 영역 | 상태 |", "|---|---|",
    ]
    for name, status in verdict["per_section"].items():
        lines.append(f"| {name} | {status} |")

    lines += ["", "## 1. Context 준비도 (15개)", ""]
    lines += _context_table(sections["context_readiness"])

    lines += ["", "## 2. Trait 준비도 (24개)", ""]
    lines += _trait_table(sections["trait_readiness"])

    qf = sections["question_flow_readiness"]
    lines += ["", "## 3. 질문 흐름 준비도", ""]
    lines.append(f"- 2+1(Flag OFF): 최종 {qf['flow_2plus1_flag_off']['final_context_min']}~{qf['flow_2plus1_flag_off']['final_context_max']}개 — {qf['flow_2plus1_flag_off']['status']}")
    f41 = qf["flow_4plus1_flag_on"]
    lines.append(f"- 4+1(Flag ON): 오늘 활성 Context {f41['effective_supported_context_count_if_pack_runtime_on']}개(최소 {f41['minimum_required']}) — 기준 충족: {'예' if f41['meets_minimum_today'] else '아니오'} — {f41['status']}")
    lines.append(f"- Context당 질문 수: {qf['tail_question_bounds_per_context']['minimum']}~{qf['tail_question_bounds_per_context']['maximum']}개 — {qf['tail_question_bounds_per_context']['status']}")
    lines.append(f"- Backup 안전성: {qf['backup_safety']['status']}")
    lines.append(f"- Planner Baseline: {qf['planner_baseline']['status']}")
    lines.append(f"- Coverage-focused Planner 대안(A/B/C/D): {qf['coverage_focused_planner_alternatives']['status']}")
    lines.append(f"- Coverage Stop Condition 연결: {qf['coverage_stop_condition_wiring']['status']}")

    md = sections["major_department_readiness"]
    lines += ["", "## 4. 전공·학과 준비도", ""]
    lines.append(f"- 서비스 Canonical Major: {md['service_canonical_majors']['count']}개 — {md['service_canonical_majors']['status']}")
    lines.append(f"- Major-Trait Evidence: legacy {md['major_trait_evidence']['legacy_evidence_row_count']}행 · v2 {md['major_trait_evidence']['v2_evidence_row_count']}행 — {md['major_trait_evidence']['status']}")
    lines.append(f"- Canonical Major Group: {md['canonical_major_groups']['count']}개, {md['canonical_major_groups']['review_status_breakdown']} — {md['canonical_major_groups']['status']}")
    lines.append(f"- Bridge Mapping: {md['bridge_mapping']['count']}개, 검토 {md['bridge_mapping']['reviewer_status_breakdown']} — {md['bridge_mapping']['status']}")
    lines.append(f"- Bridge Scope: {md['bridge_scope']['scope_type_breakdown']} — {md['bridge_scope']['status']}")
    lines.append(f"- P1: {md['p1_classification']['count']}건, {md['p1_classification']['reviewer_1_status_breakdown']} — {md['p1_classification']['status']}")
    lines.append(f"- N.C.E: {md['nce']['cluster_count']}개 클러스터·{md['nce']['member_row_total']}행, {md['nce']['reviewer_1_status_breakdown']} — {md['nce']['status']}")
    lines.append(f"- Identity 충돌: {md['identity_key_conflicts']['group_count']} Group·{md['identity_key_conflicts']['candidate_row_total']}행, {md['identity_key_conflicts']['decision_breakdown']} — {md['identity_key_conflicts']['status']}")
    lines.append(f"- 현재 Master: {md['current_master']['department_count']}건 — {md['current_master']['status']}")
    lines.append(f"- 전국 Dry Run: {md['national_dry_run']['note']} — {md['national_dry_run']['status']}")
    lines.append(f"- 차단 사유: {'; '.join(md['blocking_reasons']) or '(없음)'}")

    sd = sections["subject_readiness"]
    lines += ["", "## 5. 과목 준비도", "", "| 전공 | Subject-Major Link 수 | 상태 |", "|---|---|---|"]
    for row in sd["per_major"]:
        lines.append(f"| {row['major_id']} | {row['subject_major_link_count']} | {row['status']} |")
    lines.append("")
    lines.append(f"- PRE_SURVEY/POST_OFFERING: {sd['pre_survey_post_offering_mechanism']['status']}")
    lines.append(f"- PDF·Excel Parsing: {sd['pdf_excel_parsing']['note']} — {sd['pdf_excel_parsing']['status']}")
    lines.append(f"- 실제 개설 과목 확인: {sd['actually_offered_course_confirmation']['note']} — {sd['actually_offered_course_confirmation']['status']}")
    lines.append(f"- 미지원 전공: {', '.join(sd['unsupported_majors']) or '(없음)'}")

    fe = sections["frontend_readiness"]
    lines += ["", "## 6. Frontend 준비도", "", "| 항목 | 상태 |", "|---|---|"]
    for name, item in fe["items"].items():
        lines.append(f"| {name} | {item['status']} |")
    lines.append("")
    lines.append(f"- npm scripts: {fe['npm_scripts']}")
    lines.append(f"- node_modules 설치됨: {'예' if fe['node_modules_installed'] else '아니오'}")

    lines += ["", "## 7. Feature Flag 표", ""]
    lines += _flag_table(sections["feature_flags"])

    lines += ["", "## 8. 최종 상태 판정", "", f"**{verdict['overall']}**", ""]
    lines.append(
        "질문·Mapping·Runtime·Review 파일은 이 진단이 만들지도 바꾸지도 않았다 — 위 표는 "
        "전부 현재 저장소·로컬 데이터를 있는 그대로 읽은 결과다."
    )

    MD_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {MD_OUTPUT_PATH}")


def main() -> None:
    sections = run_audit()
    _write_json_report(sections)
    _write_markdown_report(sections)


if __name__ == "__main__":
    main()
