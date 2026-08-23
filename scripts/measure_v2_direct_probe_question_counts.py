"""V2 Direct Probe 문항 수 재측정 — 2026-08-23 Trait Ontology v2(2.1단계) §14.

10개 고정 Persona(RELATED Hypothesis 0~5개, 이미 MODERATE인 Trait 포함, 이미 Target
Probe한 Trait 포함, 사용할 Context Blueprint가 없는 Trait, 모든 후보 소진)를 실제
`/assessment` API로 실행해 Direct Probe 문항 수가 실제로 Evidence에 따라 달라지는지
측정한다. LLM은 항상 꺼서 결정론적으로 만든다.

각 Persona는 "5개 Hypothesis 기반 Trait에 몇 개나 RELATED Evidence를 인위적으로
심어두는가"로 재현한다 — 실제 Legacy 21문항 답변 패턴으로 정확히 N개를 만들어내는
조합을 매번 새로 찾는 대신(가능하지만 조합이 제한적이고 조사 비용이 크다), 이미
Legacy가 실제로 끝난 세션에 결정론적으로 RELATED Evidence 레코드를 추가해 원하는
Hypothesis 개수를 정확히 재현한다 — 이후의 Direct Probe Phase 진입·후보 선택·질문
서빙·답변 처리는 전부 실제 API 경로를 그대로 탄다(Selector·Generator 자체를 Mock하지
않는다).

실행: PYTHONPATH=. ./.venv/bin/python scripts/measure_v2_direct_probe_question_counts.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # noqa: E402

os.environ["ENABLE_TRAIT_VECTOR_V2_DIRECT_PROBES"] = "true"

from fastapi.testclient import TestClient  # noqa: E402

import src.api.main as main_module  # noqa: E402
from src.api.main import app  # noqa: E402
from src.ids import generate_evidence_id  # noqa: E402
from src.schemas.evidence import AppliedTraitSignal, EvidenceOrigin, EvidenceRecord  # noqa: E402

client = TestClient(app)

HYPOTHESIS_TRAITS = [
    "systems_thinking", "detail_orientation", "persistence_completion",
    "uncertainty_tolerance", "opinion_expression",
]


def _new_session(final_contexts=("game", "media", "school_life")) -> str:
    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {c: 5 for c in final_contexts}},
    )
    client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": list(final_contexts[:2])},
    )
    client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": list(final_contexts)},
    )
    return session_id


def _finish_legacy(session_id: str) -> None:
    """Legacy 3개 Context가 끝나는 순간 멈춘다 — Feature Flag가 켜져 있으면 그 시점
    바로 다음 next-question 호출이 V2 Direct Probe로 들어가므로, 그 전에 멈춰야
    이 함수 호출 뒤에 합성 Evidence를 주입하는 게 의미가 있다(주입 전에 Direct Probe가
    이미 다 끝나버리면 후보 계산 시점에 반영이 안 된다)."""

    for _ in range(60):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            if body["assessment_complete"]:
                return
            continue
        state = main_module._store.load(session_id)
        if state.current_question_family_id == "v2_direct_probe":
            return  # Legacy는 이미 끝났다 — 여기서 멈추고 호출자가 Evidence를 주입하게 한다.
        question = body["question"]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            return


def _clear_organic_v2_signals(session_id: str) -> None:
    """옵션[0]만 계속 고르는 `_finish_legacy()`도 실제로는 Seed 답변에서 organic하게
    systems_thinking/persistence_completion RELATED Signal을 만들어낸다(1.5단계부터
    이미 그렇다). Persona별로 "정확히 N개 Trait에만 RELATED가 있다"를 깨끗하게
    재현하려면, 실제 Legacy Evidence는 그대로 두되(Legacy 계산은 이 필드를 안 읽으므로
    영향 없음) `applied_trait_signals_v2`만 전부 비워서 v2 계산의 출발점을 0으로
    만든다."""

    state = main_module._store.load(session_id)
    state.evidence_ledger = [
        r.model_copy(update={"applied_trait_signals_v2": [], "trait_signal_mapping_source_v2": None})
        for r in state.evidence_ledger
    ]
    main_module._store.save(state)


def _inject_related_evidence(session_id: str, trait_id: str, index: int) -> None:
    state = main_module._store.load(session_id)
    state.evidence_ledger.append(
        EvidenceRecord(
            evidence_id=generate_evidence_id(), answer_id=f"ans_synthetic_{trait_id}_{index}",
            question_id=f"q_synthetic_{trait_id}_{index}", question_frame_id="problem_check",
            option_role_id="synthetic_role", option_text="합성 답변",
            applied_primary_trait_delta={}, evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
            context="game", source_type="seed_question", generator_version="v1",
            quality_gate_status="passed",
            applied_trait_signals_v2=[AppliedTraitSignal(trait_id=trait_id, signal_role="RELATED", weight=0.33)],
        )
    )
    main_module._store.save(state)


def _run_direct_probe_phase(session_id: str) -> dict:
    selected_order: list[str] = []
    hypothesis_questions = 0
    exploration_questions = 0
    for _ in range(20):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        body = r.json()
        if body["status"] == "CONTEXT_EARLY_TERMINATED":
            break
        state = main_module._store.load(session_id)
        if state.current_question_family_id != "v2_direct_probe":
            break
        target = state.current_v2_probe_target_trait_id
        selected_order.append(target)
        if target in HYPOTHESIS_TRAITS:
            hypothesis_questions += 1
        else:
            exploration_questions += 1
        question = body["question"]
        ar = client.post(
            "/assessment/answer",
            json={
                "session_id": session_id, "question_id": question["question_id"],
                "selected_option_id": question["options"][0]["option_id"],
            },
        )
        if ar.json()["next_action"] == "ASSESSMENT_COMPLETE":
            break
    state = main_module._store.load(session_id)
    return {
        "selected_order": selected_order,
        "hypothesis_questions": hypothesis_questions,
        "exploration_questions": exploration_questions,
        "total_direct_probe": len(selected_order),
        "total_questions": len(state.answers),
        "termination_phase": state.v2_probe_phase,
    }


def main() -> None:
    with patch.object(main_module, "_llm_client", None):
        results = []

        # Persona 1: RELATED Hypothesis 0개.
        sid = _new_session()
        _finish_legacy(sid)
        _clear_organic_v2_signals(sid)
        results.append(("Persona 1 — Hypothesis 0개", _run_direct_probe_phase(sid)))

        # Persona 2~6: RELATED Hypothesis N개(1~5).
        for n in range(1, 6):
            sid = _new_session()
            _finish_legacy(sid)
            _clear_organic_v2_signals(sid)
            for trait_id in HYPOTHESIS_TRAITS[:n]:
                _inject_related_evidence(sid, trait_id, 1)
            results.append((f"Persona {n + 1} — Hypothesis {n}개", _run_direct_probe_phase(sid)))

        # Persona 7: 이미 MODERATE인 Trait 포함(제외돼야 함). RELATED만으로는 MODERATE에
        # 절대 도달하지 않으므로(§9 "한 번의 답변으로 강한 Trait가 되면 안 된다" —
        # RELATED 승격은 최대 LIMITED), 실제로 PRIMARY Evidence 2개(서로 다른 Context)를
        # 직접 주입해 MODERATE를 재현한다 — Direct Probe를 두 번 거친 것과 동등한 상태.
        sid = _new_session()
        _finish_legacy(sid)
        _clear_organic_v2_signals(sid)
        for trait_id in HYPOTHESIS_TRAITS[:2]:
            _inject_related_evidence(sid, trait_id, 1)
        state = main_module._store.load(sid)
        for i, context in enumerate(("game", "media"), start=1):
            state.evidence_ledger.append(
                EvidenceRecord(
                    evidence_id=generate_evidence_id(), answer_id=f"ans_synthetic_primary_{i}",
                    question_id=f"q_synthetic_primary_{i}", question_frame_id=f"frame_{i}",
                    option_role_id="synthetic_primary_role", option_text="합성 PRIMARY 답변",
                    applied_primary_trait_delta={}, evidence_origin=EvidenceOrigin.V2_DIRECT_PROBE,
                    context=context, source_type="v2_direct_probe_question", generator_version="v1",
                    quality_gate_status="passed",
                    applied_trait_signals_v2=[
                        AppliedTraitSignal(trait_id="systems_thinking", signal_role="PRIMARY", weight=1.0)
                    ],
                )
            )
        main_module._store.save(state)
        results.append(("Persona 7 — 이미 MODERATE인 Trait 포함", _run_direct_probe_phase(sid)))

        # Persona 8: 이미 Target Probe한 Trait 포함(재질문 없어야 함).
        sid = _new_session()
        _finish_legacy(sid)
        _clear_organic_v2_signals(sid)
        for trait_id in HYPOTHESIS_TRAITS[:2]:
            _inject_related_evidence(sid, trait_id, 1)
        state = main_module._store.load(sid)
        state.v2_probed_trait_ids = [HYPOTHESIS_TRAITS[0]]
        main_module._store.save(state)
        results.append(("Persona 8 — 이미 Target Probe한 Trait 포함", _run_direct_probe_phase(sid)))

        # Persona 9: 사용할 Context Blueprint가 없는 Trait. 참고: Vertical Slice는 최종
        # Context를 항상 3개 중 최소 2개로 강제하므로(§5-1), systems_thinking처럼
        # game/school_life 둘 중 하나라도 있으면 되는 Trait는 실제 API 흐름으로는 "쓸
        # Blueprint가 아예 없는" 상태를 만들 수 없다(3개 중 2개를 고르면 game·school_life
        # 중 최소 하나는 항상 포함된다) — 이 사실 자체가 §14 측정 결과다. Selector
        # 로직만 독립적으로 확인하기 위해 정상 세션을 만든 뒤 final_contexts를 강제로
        # media 하나로 바꾼다(API로는 도달 불가능한 상태를 의도적으로 재현).
        sid = _new_session()
        _finish_legacy(sid)
        _clear_organic_v2_signals(sid)
        _inject_related_evidence(sid, "systems_thinking", 1)
        state = main_module._store.load(sid)
        state.final_contexts = ["media"]
        main_module._store.save(state)
        results.append(("Persona 9 — Context 불일치 Trait 제외(API로는 도달 불가, 강제 재현)", _run_direct_probe_phase(sid)))

        # Persona 10: 모든 후보 소진(전부 이미 probe함).
        sid = _new_session()
        _finish_legacy(sid)
        _clear_organic_v2_signals(sid)
        state = main_module._store.load(sid)
        from src.data.questions.trait_v2_direct_probe_blueprints import V2_DIRECT_PROBE_TARGET_TRAIT_IDS

        state.v2_probe_phase = "V2_DIRECT_PROBE"
        state.v2_probed_trait_ids = list(V2_DIRECT_PROBE_TARGET_TRAIT_IDS)
        main_module._store.save(state)
        results.append(("Persona 10 — 모든 후보 소진", _run_direct_probe_phase(sid)))

    print(f"{'Persona':40} {'선택된 후보':45} {'Hyp':>4} {'Expl':>5} {'V2합':>5} {'전체':>5} {'종료':>10}")
    for name, r in results:
        print(
            f"{name:40} {str(r['selected_order']):45} {r['hypothesis_questions']:>4} "
            f"{r['exploration_questions']:>5} {r['total_direct_probe']:>5} {r['total_questions']:>5} "
            f"{r['termination_phase']:>10}"
        )


if __name__ == "__main__":
    main()
