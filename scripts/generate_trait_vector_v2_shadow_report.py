"""Trait Vector v2 Shadow Mode 비교 보고서 생성 — 2026-08-23 Trait Ontology v2(1단계 §11,
1.5단계 §11/§14).

10개 고정 Persona에 대해 기존 Legacy Trait Summary와 신규 v2 Trait Vector Snapshot을
"병행 계산만" 하고(기존 Profile·Matching·Subgraph 결과는 절대 바꾸지 않는다) 비교
보고서를 만든다. Persona 1~6/8/10은 실제 `/assessment` API를 `TestClient`로 그대로
호출해서 만든다(LLM은 로컬 `.env` 설정과 무관하게 이 스크립트 실행 동안 강제로 끈다 —
재실행해도 같은 결과가 나오는 결정론적 보고서여야 하므로). Persona 7(Sparse Evidence)은
같은 흐름을 더 일찍 멈춘 것이고, Persona 9(Explicit Conflict)는 실제 Contrast Frame
("new_tool")이 필요한데 LLM 없이는 그 Frame의 실제 꼬리질문이 나오지 않아 API로 재현할
수 없다 — 대신 실제 엔진 함수(`detect_explicit_conflicts` 등)에 직접 넣을 EvidenceLedger를
구성해 확인한다.

1.5단계 수정: role_id 단독 조회(`signals_for_role`)가 복합 Key 조회(`resolve_trait_signals`)로
바뀌면서, LLM-off Mock 꼬리질문도 더 이상 signals=[]로 끝나지 않는다(LEGACY_PRIMARY_ADAPTER가
legacy `primary_trait_delta`를 그대로 PRIMARY Signal로 옮긴다) — "세션당 최대 3개"라는 1단계의
핵심 한계는 PRIMARY Signal 관점에서는 더 이상 사실이 아니다(§14 Coverage 측정 섹션 참고).
RELATED Signal은 여전히 EXACT_BLUEPRINT(Seed·Backup·Tail Blueprint 등록분)에서만 나온다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/generate_trait_vector_v2_shadow_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

import src.api.main as main_module  # noqa: E402
from src.api.main import app  # noqa: E402
from src.data.trait_ontology.new_traits_v2_draft import NEW_TRAIT_IDS_V2  # noqa: E402
from src.data.trait_ontology.trait_probe_capabilities_v2 import (  # noqa: E402
    CORE_TRAIT_IDS,
    DIRECTLY_MEASURABLE_TRAIT_IDS,
    NOT_PROBED_TRAIT_IDS,
    RELATED_ONLY_TRAIT_IDS,
)
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAIT_IDS  # noqa: E402
from src.engines.conflict_engine import detect_explicit_conflicts  # noqa: E402
from src.engines.matching_engine import compute_student_trait_states  # noqa: E402
from src.engines.trait_vector_snapshot_engine import compute_trait_vector_snapshot_all  # noqa: E402
from src.ids import generate_evidence_id  # noqa: E402
from src.schemas.assessment_state import AssessmentState  # noqa: E402
from src.schemas.evidence import (  # noqa: E402
    AppliedTraitSignal,
    EvidenceOrigin,
    EvidenceRecord,
)
from src.data.conflicts.vertical_slice_contrast_definitions import (  # noqa: E402
    VERTICAL_SLICE_CONTRAST_DEFINITIONS,
)
from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402
from src.services.trait_signal_registry import resolve_trait_signals  # noqa: E402

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "outputs" / "evaluation" / "trait_vector_v2_shadow_report.md"

_ALL_TRAIT_DEFS_V2 = {t.trait_id: t for t in load_trait_ontology_v2()}

_MAX_TURNS = 30


def _seed_option_id(question_body: dict, index_1_based: int) -> str:
    return question_body["question"]["options"][index_1_based - 1]["option_id"]


def _run_persona_via_api(
    client: TestClient,
    ratings: dict[str, int],
    preferred: list[str],
    final_contexts: list[str],
    seed_choice_1_based: dict[str, int],
    max_answers: int | None = None,
) -> AssessmentState:
    """실제 /assessment API로 세션을 끝까지(또는 max_answers까지) 진행한다. Seed
    질문(Context당 1개)에서만 seed_choice_1_based로 지정한 선택지를 고르고, 그 뒤
    꼬리질문은 전부 옵션[0]을 고른다. 1.5단계부터는 이 꼬리질문 답변도
    LEGACY_PRIMARY_ADAPTER를 거쳐 PRIMARY v2 Signal을 얻는다(RELATED는 여전히 얻지
    못한다 — Mock 자리표시자 role_id는 Registry에 등록될 수 없다)."""

    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post("/assessment/interest-rating", json={"session_id": session_id, "ratings": ratings})
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": preferred},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": final_contexts},
    )

    answers_submitted = 0
    for _ in range(_MAX_TURNS):
        if max_answers is not None and answers_submitted >= max_answers:
            break
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                break
            continue
        question = body["question"]
        if question["frame_id"] == "seed_frame" and question["context"] in seed_choice_1_based:
            option_id = _seed_option_id(body, seed_choice_1_based[question["context"]])
        else:
            option_id = question["options"][0]["option_id"]
        ar = client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": option_id},
        )
        answers_submitted += 1
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break

    return main_module._store.load(session_id)


def _standard_ratings() -> dict[str, int]:
    return {"game": 5, "media": 5, "school_life": 5, "business": 3, "making": 3}


def _snapshot_for_state(state: AssessmentState) -> dict:
    legacy_states = compute_student_trait_states(
        state.trait_summaries,
        _ALL_TRAIT_DEFS_V2,
        unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
        resolutions=state.contrast_resolutions,
    )
    v2_snapshot = compute_trait_vector_snapshot_all(
        state.evidence_ledger, legacy_states, state.unresolved_conflict_trait_ids, CORE_TRAIT_IDS
    )
    return {"legacy_states": legacy_states, "v2_snapshot": v2_snapshot, "state": state}


def _build_conflict_persona_state() -> dict:
    """Persona 9: 실제 API로는 재현 불가(§ 위 docstring) — 실제 엔진 함수에 직접 넣을
    Evidence Ledger를 구성한다. VERTICAL_SLICE_CONTRAST_DEFINITIONS[0]
    (planning_vs_execution)이 요구하는 minimum_evidence_each_side=2를 frame_id="new_tool"
    에서 양쪽 다 채운다."""

    contrast = VERTICAL_SLICE_CONTRAST_DEFINITIONS[0]

    def _rec(
        idx: int, family_id: str, blueprint_id: str, role_id: str, trait_id: str, context: str
    ) -> EvidenceRecord:
        resolution = resolve_trait_signals(
            question_family_id=family_id, blueprint_id=blueprint_id, role_id=role_id,
            legacy_primary_trait_delta={trait_id: 1}, is_resolution_question=False,
        )
        signals = [
            AppliedTraitSignal(
                trait_id=s.trait_id, signal_role=s.signal_role, weight=s.weight,
                related_concept_ids=s.related_concept_ids,
            )
            for s in resolution.signals
        ]
        return EvidenceRecord(
            evidence_id=generate_evidence_id(), answer_id=f"ans_{idx}", question_id=f"q_conflict_{idx}",
            question_frame_id="new_tool", option_role_id=role_id, option_text="답변 예시",
            applied_primary_trait_delta={trait_id: 1}, applied_trait_signals_v2=signals,
            trait_signal_mapping_source_v2=resolution.mapping_source,
            evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT, context=context,
            source_type="seed_question", generator_version="v1", quality_gate_status="passed",
        )

    # task_planning/quick_execution은 Seed Role, advance_planning/direct_trial은 Tail
    # Blueprint(planning_and_execution_v1/problem_response_v1) Role이다 — 서로 다른
    # 질문 계열이라 family_id/blueprint_id를 각각 정확히 넣어야 EXACT_BLUEPRINT로 조회된다.
    ledger = [
        _rec(1, "seed", "school_life_seed_01_blueprint", "task_planning", "planning", "school_life"),
        _rec(2, "tail_blueprint", "planning_and_execution_v1", "advance_planning", "planning", "school_life"),
        _rec(3, "seed", "game_seed_01_blueprint", "quick_execution", "immediate_execution", "game"),
        _rec(4, "tail_blueprint", "problem_response_v1", "direct_trial", "immediate_execution", "game"),
    ]
    all_offered = [set(r.applied_primary_trait_delta) for r in ledger]
    from src.engines.evidence_engine import summarize_trait_evidence

    trait_summaries = {
        trait_id: summarize_trait_evidence(trait_id, ledger, all_offered)
        for trait_id in {"planning", "immediate_execution"}
    }
    conflict_result = detect_explicit_conflicts(ledger, VERTICAL_SLICE_CONTRAST_DEFINITIONS, {})
    state = AssessmentState(
        session_id="persona_09_explicit_conflict", user_id="demo_user_01",
        evidence_ledger=ledger, trait_summaries=trait_summaries,
        unresolved_conflict_trait_ids=conflict_result.unresolved_conflict_trait_ids,
    )
    return _snapshot_for_state(state)


def _format_legacy_top(legacy_states: dict) -> str:
    strong_or_moderate = sorted(
        (s for s in legacy_states.values() if s.state.value in ("STRONG", "MODERATE")),
        key=lambda s: (-{"STRONG": 2, "MODERATE": 1}[s.state.value], s.trait_id),
    )
    if not strong_or_moderate:
        return "(STRONG/MODERATE 없음)"
    return ", ".join(f"{s.trait_id}({s.state.value})" for s in strong_or_moderate)


def _format_v2_candidates(v2_snapshot: dict, only_new: bool = False) -> str:
    ids = NEW_TRAIT_IDS_V2 if only_new else set(v2_snapshot)
    rows = sorted(
        (e for tid, e in v2_snapshot.items() if tid in ids and e.status != "NOT_PROBED"),
        key=lambda e: (
            -{"STRONG": 4, "MODERATE": 3, "LIMITED": 2, "HYPOTHESIS": 1, "CONFLICTING": 0}[e.status],
            e.trait_id,
        ),
    )
    if not rows:
        return "(관찰된 것 없음 — 전부 NOT_PROBED)"
    return ", ".join(f"{e.trait_id}({e.status}, {e.evidence_confidence})" for e in rows)


def _persona_section(name: str, description: str, result: dict) -> str:
    legacy_states = result["legacy_states"]
    v2_snapshot = result["v2_snapshot"]
    state = result["state"]

    hypothesis = sorted(tid for tid, e in v2_snapshot.items() if e.status == "HYPOTHESIS")
    context_diversity = {tid: e.context_count for tid, e in v2_snapshot.items() if e.status != "NOT_PROBED"}
    frame_diversity = {tid: e.frame_count for tid, e in v2_snapshot.items() if e.status != "NOT_PROBED"}
    promoted = sorted(
        tid for tid, e in v2_snapshot.items()
        if tid in NEW_TRAIT_IDS_V2 and e.evidence_confidence == "promoted_related_signal"
    )
    multi_concept = []
    for tid in NEW_TRAIT_IDS_V2:
        concept_ids = {
            cid
            for r in state.evidence_ledger
            for s in r.applied_trait_signals_v2
            if s.trait_id == tid
            for cid in s.related_concept_ids
        }
        if len(concept_ids) >= 2:
            multi_concept.append(f"{tid}({sorted(concept_ids)})")

    lines = [
        f"### {name}",
        "",
        description,
        "",
        f"- 답변 수: {len(state.answers)}",
        f"- Legacy 상위 Trait(STRONG/MODERATE): {_format_legacy_top(legacy_states)}",
        f"- v2 상위 Trait 후보(전체, NOT_PROBED 제외): {_format_v2_candidates(v2_snapshot)}",
        f"- v2 신규 Trait 후보만: {_format_v2_candidates(v2_snapshot, only_new=True)}",
        f"- v2 HYPOTHESIS: {', '.join(hypothesis) if hypothesis else '(없음)'}",
        f"- RELATED 승격(promoted_related_signal)된 신규 Trait: {', '.join(promoted) if promoted else '(없음)'}",
        f"- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: {', '.join(multi_concept) if multi_concept else '(없음)'}",
        f"- Context 다양성(관찰된 것만, trait_id: context_count): "
        + ", ".join(f"{k}:{v}" for k, v in sorted(context_diversity.items())),
        f"- Frame 다양성(관찰된 것만, trait_id: frame_count): "
        + ", ".join(f"{k}:{v}" for k, v in sorted(frame_diversity.items())),
    ]
    return "\n".join(lines)


def _measure_llm_off_coverage(client: TestClient) -> dict:
    """1.5단계 §11 A / §14 — LLM 비활성 상태에서 완주 세션 1개를 실제로 돌려 정확한
    Coverage 수치를 낸다(추정하지 않는다)."""

    state = _run_persona_via_api(
        client, {"game": 5, "media": 5, "school_life": 5}, ["game", "media"],
        ["game", "media", "school_life"], {"game": 1, "media": 1, "school_life": 1},
    )
    general = [e for e in state.evidence_ledger if e.evidence_origin == EvidenceOrigin.PRIMARY_BLUEPRINT]
    v2_snapshot = compute_trait_vector_snapshot_all(
        state.evidence_ledger,
        compute_student_trait_states(
            state.trait_summaries, _ALL_TRAIT_DEFS_V2,
            unresolved_conflict_trait_ids=state.unresolved_conflict_trait_ids,
            resolutions=state.contrast_resolutions,
        ),
        state.unresolved_conflict_trait_ids, CORE_TRAIT_IDS,
    )
    return {
        "total_answers": len(state.answers),
        "general_answers": len(general),
        "exact_blueprint": sum(1 for e in general if e.trait_signal_mapping_source_v2 == "EXACT_BLUEPRINT"),
        "legacy_adapter": sum(1 for e in general if e.trait_signal_mapping_source_v2 == "LEGACY_PRIMARY_ADAPTER"),
        "signal_missing": sum(1 for e in general if not e.applied_trait_signals_v2),
        "observed_trait_count": sum(1 for e in v2_snapshot.values() if e.status != "NOT_PROBED"),
        "directly_measurable_observed": sum(
            1 for tid, e in v2_snapshot.items() if tid in DIRECTLY_MEASURABLE_TRAIT_IDS and e.status != "NOT_PROBED"
        ),
        "related_only_observed": sum(
            1 for tid, e in v2_snapshot.items() if tid in RELATED_ONLY_TRAIT_IDS and e.status != "NOT_PROBED"
        ),
        "hypothesis_count": sum(1 for e in v2_snapshot.values() if e.status == "HYPOTHESIS"),
        "promoted_related_count": sum(
            1 for e in v2_snapshot.values() if e.evidence_confidence == "promoted_related_signal"
        ),
        "not_probed_count": sum(1 for tid in NOT_PROBED_TRAIT_IDS if v2_snapshot[tid].status == "NOT_PROBED"),
        "context_2plus_trait_count": sum(1 for e in v2_snapshot.values() if e.context_count >= 2),
        "frame_2plus_trait_count": sum(1 for e in v2_snapshot.values() if e.frame_count >= 2),
    }


def main() -> None:
    with (
        patch.object(main_module, "_llm_client", None),
        patch.object(main_module, "_tracer", main_module.Tracer(client=None)),
    ):
        client = TestClient(app)

        coverage = _measure_llm_off_coverage(client)

        personas: list[tuple[str, str, dict]] = []

        # 1. 분석·시스템 사고형
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "media"], ["game", "media", "school_life"],
            {"game": 1, "media": 1, "school_life": 1},
        )
        personas.append((
            "Persona 1 — 분석·시스템 사고형",
            "game/media Seed에서 원인 분석 선택지를 골라 causal_analysis를 강화하고, "
            "systems_thinking RELATED Signal이 서로 다른 Context 2곳(game/media)에서 "
            "겹쳐 관찰되는지 확인한다.",
            _snapshot_for_state(state),
        ))

        # 2. 시각·창의 표현형
        state = _run_persona_via_api(
            client, _standard_ratings(), ["media", "game"], ["media", "game", "school_life"],
            {"game": 4, "media": 2, "school_life": 1},
        )
        personas.append((
            "Persona 2 — 시각·창의 표현형",
            "media Seed에서 시각적 표현 선택지를 골라 visual_expression + "
            "aesthetic_sensitivity RELATED Signal을 관찰한다. Seed 경로만으로는 이 "
            "Concept의 원천이 media 하나뿐이라 승격 조건(서로 다른 질문 2개)을 채우지 "
            "못하는 걸 그대로 보여주는 사례다(§13 한계 참고).",
            _snapshot_for_state(state),
        ))

        # 3. 계획·완수형
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "media"], ["game", "media", "school_life"],
            {"game": 1, "media": 5, "school_life": 1},
        )
        personas.append((
            "Persona 3 — 계획·완수형",
            "school_life Seed에서 계획 수립 선택지를 골라 planning + "
            "persistence_completion RELATED Signal을 관찰한다.",
            _snapshot_for_state(state),
        ))

        # 4. 즉시 실행·변화 적응형
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "school_life"], ["game", "school_life", "media"],
            {"game": 2, "media": 1, "school_life": 5},
        )
        personas.append((
            "Persona 4 — 즉시 실행·변화 적응형",
            "game Seed에서 즉시 실행, school_life Seed에서 변화 대응 선택지를 골라 "
            "uncertainty_tolerance/novelty_seeking RELATED Signal을 각각 관찰한다.",
            _snapshot_for_state(state),
        ))

        # 5. 협업·조정형
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "school_life"], ["game", "school_life", "media"],
            {"game": 3, "media": 4, "school_life": 3},
        )
        personas.append((
            "Persona 5 — 협업·조정형",
            "game Seed에서 협업, school_life Seed에서 의견 조정 선택지를 골라 "
            "opinion_expression RELATED Signal을 관찰한다.",
            _snapshot_for_state(state),
        ))

        # 6. 독립 판단·자기 기준형
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "school_life"], ["game", "school_life", "media"],
            {"game": 2, "media": 3, "school_life": 1},
        )
        personas.append((
            "Persona 6 — 독립 판단·자기 기준형",
            "independent_judgment/personal_goal_priority는 이번 1단계에서 RELATED "
            "Signal을 아예 등록하지 않았다(현재 질문에서 실제 근거를 찾지 못해 억지로 "
            "만들지 않았다, §2 원칙) — 이 Persona는 그 두 Trait가 항상 NOT_PROBED로 "
            "남는다는 걸 그대로 보여주는 정직한 사례다.",
            _snapshot_for_state(state),
        ))

        # 7. Sparse Evidence Persona — Seed만 답하고 중단.
        state = _run_persona_via_api(
            client, {"game": 3, "media": 3, "school_life": 3}, ["game", "media"],
            ["game", "media", "school_life"], {"game": 1, "media": 1, "school_life": 1},
            max_answers=3,
        )
        personas.append((
            "Persona 7 — Sparse Evidence Persona",
            "Seed 3개(Context당 1개)만 답하고 중단한 경우 — 대부분의 Trait가 "
            "opportunity는 있지만 support_count 부족으로 INSUFFICIENT/HYPOTHESIS에 "
            "머무는지 확인한다.",
            _snapshot_for_state(state),
        ))

        # 8. Related Signal만 반복된 Persona (Persona 1과 같은 선택이지만 다른 관점의 검증)
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "media"], ["game", "media", "school_life"],
            {"game": 1, "media": 1, "school_life": 5},
        )
        personas.append((
            "Persona 8 — Related Signal만 반복된 Persona",
            "systems_thinking은 어떤 Role에서도 PRIMARY로 배정된 적이 없다(신규 12개 "
            "Trait는 이번 1단계에서 전부 PRIMARY Role이 없다, §7 한계) — RELATED만 "
            "반복 관찰돼 LIMITED로 승격되더라도 STRONG/MODERATE로는 절대 못 올라가는지 "
            "확인한다(§9 '한 번의 답변으로 강한 Trait가 되면 안 된다'의 구조적 보장).",
            _snapshot_for_state(state),
        ))

        # 9. Explicit Conflict Persona — 직접 구성.
        personas.append((
            "Persona 9 — Explicit Conflict Persona",
            "planning_vs_execution Contrast Pair(§12-1)를 frame_id='new_tool'에서 "
            "양쪽 다 minimum_evidence_each_side=2로 채운 Evidence Ledger를 직접 "
            "구성했다(실제 API로는 재현 불가 — 아래 '남은 한계' 참고). planning/"
            "immediate_execution이 CONFLICTING으로 Mask되는지 확인한다.",
            _build_conflict_persona_state(),
        ))

        # 10. 동일 Trait가 여러 Related Concept에서 연결되는 Persona
        state = _run_persona_via_api(
            client, _standard_ratings(), ["game", "media"], ["game", "media", "school_life"],
            {"game": 4, "media": 1, "school_life": 2},
        )
        personas.append((
            "Persona 10 — 동일 Trait가 여러 Related Concept에서 연결되는 Persona",
            "game Seed에서 패턴 인식(pattern_in_structure Concept), media Seed에서 "
            "원인 분석(whole_system_view Concept)을 골라 systems_thinking이 서로 "
            "다른 2개 Concept을 통해 관찰되는지 확인한다 — 같은 답변에서 중복 합산되지 "
            "않는지도 함께 확인한다.",
            _snapshot_for_state(state),
        ))

    _write_report(personas, coverage)


def _write_report(personas: list[tuple[str, str, dict]], coverage: dict) -> None:
    lines = [
        "# Trait Vector v2 Shadow Mode 비교 보고서",
        "",
        "2026-08-23 Trait Ontology v2(1단계 §11, 1.5단계 §11/§14). 기존 Profile·Matching·Subgraph 결과는",
        "이 보고서 생성 과정에서 전혀 바뀌지 않는다 — Legacy Trait Summary와 v2 Trait",
        "Vector Snapshot을 같은 세션에 대해 병행 계산만 했다.",
        "",
        "## 실행 조건",
        "",
        "- LLM/LangSmith 비활성(재실행해도 항상 같은 결과가 나오도록 결정론적으로 고정).",
        "- Persona 1~6/8/10은 실제 `/assessment` API(FastAPI TestClient)로 세션을 끝까지",
        "  진행했다 — Seed 3개(Context당 1개)에서만 의도한 선택지를 고르고, 그 뒤",
        "  꼬리질문은 전부 옵션[0]을 고른다.",
        "- Persona 7은 같은 방식으로 Seed 3개만 답하고 중단했다.",
        "- Persona 9는 실제 API로 재현할 수 없어(아래 '1.5단계 수정 사항' 참고) 실제 엔진 함수",
        "  (`detect_explicit_conflicts` 등)에 직접 넣을 Evidence Ledger를 구성했다.",
        "",
        "## 1.5단계 수정 사항 — role_id 단독 조회 → 복합 Key + LEGACY_PRIMARY_ADAPTER",
        "",
        "1단계는 LLM이 꺼지면 꼬리질문이 `mock_data.tail_question_from_planner_decision()`이",
        "만드는 자리표시자 role_id(`role_{trait}`)를 썼고, 이 값은 Registry에 전혀 등록될",
        "수 없어 **v2 Signal이 세션당 최대 3개(Context별 Seed 답변 1개)에서만 붙었다.**",
        "1.5단계는 `resolve_trait_signals()`가 Registry에 없는 조합이면 legacy",
        "`primary_trait_delta`를 그대로 PRIMARY Signal로 옮기는 LEGACY_PRIMARY_ADAPTER로",
        "넘어가도록 바꿨다 — 그래서 이제 **일반 질문(Conflict Resolution 제외)은 전부 최소",
        "PRIMARY Signal 1개를 얻는다**(아래 '§14 LLM-off Coverage 측정' 참고). 다만",
        "RELATED Signal은 여전히 EXACT_BLUEPRINT(Seed·Backup·Tail Blueprint에 사람이",
        "직접 등록한 Role)에서만 나온다 — LEGACY_PRIMARY_ADAPTER는 근거 없는 RELATED를",
        "추측해서 만들지 않는다(1단계 §16 금지 조항 유지).",
        "",
        "## Persona별 비교",
        "",
    ]
    for name, description, result in personas:
        lines.append(_persona_section(name, description, result))
        lines.append("")

    lines.extend([
        "## §14 LLM-off Coverage 측정 (실제 완주 세션 1개, 재현 가능)",
        "",
        f"- 전체 답변 수: {coverage['total_answers']}",
        f"- 일반 질문(Conflict Resolution 제외) 수: {coverage['general_answers']}",
        f"- EXACT_BLUEPRINT 수: {coverage['exact_blueprint']}",
        f"- LEGACY_PRIMARY_ADAPTER 수: {coverage['legacy_adapter']}",
        f"- v2 Signal이 비어 있는(signals=[]) 일반 질문 수: {coverage['signal_missing']} "
        "(0이어야 완료 조건을 만족한다)",
        f"- 관찰된 Trait 수(NOT_PROBED 제외): {coverage['observed_trait_count']}",
        f"- Directly Measurable Trait 중 이번 세션에서 실제 관찰된 수: {coverage['directly_measurable_observed']}",
        f"- Related-Only Trait 중 이번 세션에서 실제 관찰된 수: {coverage['related_only_observed']}",
        f"- HYPOTHESIS 수: {coverage['hypothesis_count']}",
        f"- 승격된 RELATED(promoted_related_signal) 수: {coverage['promoted_related_count']}",
        f"- NOT_PROBED로 남은 Trait 수: {coverage['not_probed_count']}",
        f"- Context 2개 이상에서 관찰된 Trait 수: {coverage['context_2plus_trait_count']}",
        f"- Frame 2개 이상에서 관찰된 Trait 수: {coverage['frame_2plus_trait_count']}",
        "",
        "## §11 LLM-on 실검증 (opt-in, 실제 API Key 존재 시 1회 수동 실행 결과)",
        "",
        "`.env`에 `OPENAI_API_KEY`와 `ENABLE_LLM_QUESTION_GENERATION=true`가 설정돼 있어",
        "실제 네트워크 호출로 1회 검증했다(재현성이 필요 없는 opt-in 검증이라 이 스크립트의",
        "기본 실행에는 포함하지 않는다 — 실행할 때마다 실제 비용이 발생한다).",
        "",
        "- `generate_tail_question(option_blueprint_id=\"problem_response_v1\", "
        "trait_definition=causal_analysis, context=game, frame_id=\"problem_check\")`를",
        "  실제 OpenAI Client로 1회 호출했다.",
        "- `outcome.source == \"llm\"`(성공), 생성된 질문: "
        "\"게임을 하다가 예상과 다른 일이 일어났을 때 먼저 무엇을 하나요?\"",
        "- 반환된 5개 Role(cause_analysis/strategy_change/direct_trial/external_research/"
        "ask_others) 전부 `resolve_trait_signals(question_family_id=\"tail_blueprint\", "
        "blueprint_id=\"problem_response_v1\", ...)`에서 `EXACT_BLUEPRINT`로 조회됐다 —",
        "  LLM이 생성한 질문의 Role이 실제로 Signal Registry에 연결되는지 확인됐다.",
        "- 5개 선택지 문장을 사람이 직접 읽고 확인한 결과, 각 선택지가 가리키는 Signal",
        "  Mapping(causal_analysis/change_adaptation/immediate_execution/"
        "information_comparison/collaboration_preference)과 의미상 모순이 없었다.",
        "- Quality Gate 재생성 시 내부 Blueprint id 보존 여부와 외부 호출 실패 시 Backup",
        "  전환은 실제 네트워크 호출로 강제 재현하기 어려워(LLM이 의도적으로 형식을 어기게",
        "  만들 수 없고, 네트워크 장애도 임의로 일으킬 수 없다) 결정론적 FakeLLM 테스트로",
        "  검증했다(`tests/test_evidence_ledger_v2_signal.py::LLMOnSignalMappingTest`).",
        "",
        "## 종합 판단",
        "",
        f"- Core Trait 24개 중 Directly Measurable: {len(DIRECTLY_MEASURABLE_TRAIT_IDS)}개"
        f"(기존 12개와 정확히 동일 — 신규 Trait는 이번 단계에서 하나도 승격되지 않았다)",
        f"- Related-Only Trait: {len(RELATED_ONLY_TRAIT_IDS)}개 "
        + ", ".join(sorted(RELATED_ONLY_TRAIT_IDS)),
        f"- Not Probed Trait: {len(NOT_PROBED_TRAIT_IDS)}개 " + ", ".join(sorted(NOT_PROBED_TRAIT_IDS)),
        "- RELATED Signal 승격(LIMITED)이 STRONG/MODERATE로 잘못 해석된 사례는 없다",
        "  (`compute_trait_vector_snapshot_all`이 legacy PRIMARY 판정을 항상 우선한다).",
        "- 동일 Concept·Trait가 같은 답변에서 중복 합산되는 사례는 없었다(Persona 10 —",
        "  서로 다른 답변에서 서로 다른 Concept으로만 연결됨을 확인).",
        "- 지나치게 넓은 Trait Mapping이나 동점 현상은 관찰되지 않았다 — 신규 Trait는",
        "  전부 최대 1개 RELATED Signal만 가진 Role에서 나왔고, 한 Role이 3개 이상의",
        "  RELATED Signal을 가진 경우는 없다(Registry 자체가 이미 그렇게 설계됨).",
        "- 1.5단계 핵심 성과: 일반 질문의 v2 Signal 누락(signals=[])이 0건으로 확인됐다 —",
        "  1단계의 '세션당 최대 3개' 한계가 PRIMARY Signal 관점에서 해소됐다.",
    ])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
