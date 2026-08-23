"""ContextPack Matrix Diagnostics — 12 신규 Context × 5 Anchor Runtime 안전성 진단 Harness.

지시서(2026-08-24, `a/contextpack-matrix-eval`)의 목적은 신규 Pack을 승인하는 것이
아니라, **임시(temp) 검수 데이터**로 12개 Context × 5개 Anchor = 60개 조합의 실제
Assessment Runtime 흐름(Registry → Routing → Anchor → Seed → Adaptive Probe 후보 →
Shared/Native Direct Probe → Backup Fallback → Answer → Evidence Ledger → Trait Vector
Snapshot → Context 종료)이 격리·Fail-Closed·결정론성 관점에서 안전한지 진단하는
것이다.

절대 하지 않는 것(지시서 "절대 금지" 그대로):
- 실제 `data/reviews/context_packs/*.json`, 실제 `data/reviews/
  context_pack_shared_probes_review_status.json`을 읽기 전용 이외의 방식으로 건드리지
  않는다 — 이 파일이 쓰는 모든 승인 Fixture는 `tempfile`/`with TemporaryDirectory()`
  안에서만 존재하고 프로세스 종료 시 사라진다.
- 어떤 ContextPack도 자동 APPROVE하지 않는다(실제 파일에는 아무것도 쓰지 않는다 —
  임시 파일에 "APPROVE"를 쓰는 것은 진단용 시뮬레이션일 뿐, 실제 검수 판정이 아니다).
- 질문·선택지·Trait Mapping을 수정하지 않는다 — Pack 정본은 전혀 손대지 않고 오직
  읽기만 한다. LLM Stub이 만드는 문구는 세션 실행 중에만 존재하는 휘발성 값이다.
- `src/api/main.py`·Registry·Runtime·Review UI 코드를 수정하지 않는다 — 이 파일은
  그 코드를 `unittest.mock.patch`로 "무엇을 참조하는지"만 스위치하는 진단 도구다
  (기존 `tests/test_context_pack_review_gate_e2e.py` 등과 동일한 패턴).
- Feature Flag 기본값을 바꾸지 않는다 — `os.environ`을 이 프로세스 실행 동안만
  일시적으로 설정하고 항상 원래 상태로 복원한다.

버그가 발견되면 이 Harness에서 바로 고치지 않는다 — 재현 결과와 보고서만 남긴다(지시서
§Harness 설계 원칙).

실행: PYTHONPATH=. ./.venv/bin/python -m eval.context_pack_matrix_diagnostics
결과: outputs/evaluation/context_pack_matrix_report.{json,md}
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from unittest.mock import patch

import src.api.main as main_module
from src.api.main import app
from src.data.contexts.context_activation_batches import ALL_BATCH_CONTEXT_IDS, CONTEXT_ACTIVATION_BATCHES
from src.data.contexts.context_definitions import CONTEXT_IDS, VERTICAL_SLICE_CONTEXT_IDS
from src.data.questions.context_pack_shared_probe_blueprints import CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
from src.llm.protocols import LLMCallError
from src.schemas.evidence import EvidenceOrigin, EvidenceRecord
from src.schemas.question import GeneratedOption, GeneratedQuestion
from src.services.context_pack_registry import ContextPackRegistry
from src.services.context_pack_runtime import ContextPackRuntime
from src.services.trait_signal_review_gate import is_evidence_signal_approved
from src.tracing.tracer import Tracer

OUT_DIR = Path(__file__).resolve().parent.parent / "outputs" / "evaluation"
JSON_REPORT_PATH = OUT_DIR / "context_pack_matrix_report.json"
MD_REPORT_PATH = OUT_DIR / "context_pack_matrix_report.md"

# 2개 필수(정확히 2개, MINIMUM==MAXIMUM_PREFERRED_CONTEXT_COUNT_VERTICAL_SLICE) 중
# 하나를 채우는 데 쓰는 기존 Legacy 동반 Context. game 자체의 질문 흐름은 검사 대상이
# 아니다 — 오직 "대상 Context가 confirm 가능한 조합을 만들기 위한 자리 채우기"용이다.
_COMPANION_CONTEXT_ID = "game"
# 안전 상한 — Routing(1) + Seed(1) + Tail(최대 6) + 여유 = 8이면 충분하다. 이보다 많은
# 왕복이 필요하면 "무한 루프 없음"·"질문 수 상한 준수"가 깨졌다는 신호로 본다.
_MAX_HTTP_ROUNDTRIPS_PER_COMBO = 16


# --------------------------------------------------------------------------- #
# 공용 유틸리티
# --------------------------------------------------------------------------- #


@contextlib.contextmanager
def _env(**kwargs: str | None):
    """kwargs 값이 None이면 그 환경변수를 제거하고, 문자열이면 그 값으로 설정한다.
    블록이 끝나면 원래 상태(있었으면 원래 값, 없었으면 다시 제거)로 정확히 복원한다 —
    이 프로세스 실행 동안만 Feature Flag를 조작하고 "기본값을 바꾸지 않는다"는 요구를
    지키기 위한 유일한 통로다."""

    _sentinel = object()
    saved: dict[str, Any] = {k: os.environ.get(k, _sentinel) for k in kwargs}
    try:
        for key, value in kwargs.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, original in saved.items():
            if original is _sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = original


def _error_code(response) -> str | None:
    try:
        detail = response.json().get("detail")
    except Exception:  # noqa: BLE001 — 진단 도구 자체가 응답 파싱 실패로 죽으면 안 된다.
        return f"UNPARSEABLE_BODY_status={response.status_code}"
    if isinstance(detail, dict):
        return detail.get("error_code") or f"HTTP_{response.status_code}"
    return f"HTTP_{response.status_code}"


def _classify_get(response) -> str:
    if response.status_code == 200:
        return "OK"
    return _error_code(response) or f"ERROR_{response.status_code}"


# --------------------------------------------------------------------------- #
# 결정론적 로컬 Stub LLM Client — 실제 네트워크 호출을 전혀 하지 않는다
# --------------------------------------------------------------------------- #

# `v2_direct_probe_generator._build_user_prompt()`가 만드는 고정 문구에서 Role
# 목록·context_id·frame_id만 정규식으로 되짚어 읽는다 — Blueprint 객체 자체는 Stub에
# 전달되지 않으므로(Protocol이 문자열만 받는다) 프롬프트 텍스트가 유일한 정보원이다.
_ROLE_REFERENCE_LINE = re.compile(r"^- (?P<role>[A-Za-z0-9_]+): ", re.MULTILINE)
_CONTEXT_FIELD = re.compile(r'context 필드에는 "(?P<context>[a-z0-9_]+)"를')
_FRAME_FIELD = re.compile(r'frame_id 필드에는 "(?P<frame>[a-z0-9_]+)"를')


class DeterministicStubLLMClient:
    """§3 보조 검증 전용 — 실제 LLM·네트워크를 전혀 호출하지 않는 순수 로컬 객체다.
    `ChatLLMClient` Protocol(`complete_structured`)만 구현하고, 이미 검토된 Blueprint의
    Role 순서를 그대로 유지한 중립 placeholder 문장을 만든다(질문 내용 품질은 이
    Harness의 검증 대상이 아니다 — `outputs/evaluation/v2_direct_probe_llm_quality_report.md`
    가 그 몫이다). 이 Stub은 Pack 정본을 전혀 수정하지 않는다 — 세션이 끝나면 사라지는
    응답 텍스트만 만든다."""

    def complete_structured(self, *, system_prompt: str, user_prompt: str, response_model):
        role_ids = _ROLE_REFERENCE_LINE.findall(user_prompt)
        context_match = _CONTEXT_FIELD.search(user_prompt)
        frame_match = _FRAME_FIELD.search(user_prompt)
        if not role_ids or context_match is None or frame_match is None:
            raise LLMCallError("stub LLM이 user_prompt에서 role_id/context/frame_id를 파싱하지 못했다")
        question = GeneratedQuestion(
            context=context_match.group("context"), target_traits=[], frame_id=frame_match.group("frame"),
            question_text="결정론적 Stub 질문 문구(harness 전용 — 실제 서비스에 노출되지 않음)",
            options=[GeneratedOption(role_id=role, text=f"{role} 선택지(harness stub)") for role in role_ids],
        )
        return response_model(question=question, secondary_trait_hypotheses_from_previous_answer=[])


# --------------------------------------------------------------------------- #
# 보고서 Schema
# --------------------------------------------------------------------------- #


class PackStructureAudit(BaseModel):
    discovered: bool
    routing_count: int | None = None
    anchor_count: int | None = None
    seed_count: int | None = None
    backup_count: int | None = None
    review_key_count: int | None = None


class AuditResult(BaseModel):
    """§1 "현재 상태 감사" — 실제(수정하지 않은) Registry·검수 파일을 읽기 전용으로만
    조회한 결과."""

    batch_definition: dict[str, list[str]]
    discovered_context_ids: list[str]
    discovery_errors: dict[str, str]
    ontology_errors: dict[str, str]
    per_pack_structure: dict[str, PackStructureAudit]
    real_review_all_tbd: dict[str, bool | None]  # None = 검수 파일 자체가 없음(Fail-Closed와 동치)
    shared_probe_blueprint_count: int
    shared_probe_allowed_context_ids: dict[str, list[str]]
    flag_off_supported_context_ids: list[str]
    flag_off_matches_vertical_slice_only: bool
    flag_on_but_unapproved_supported_context_ids: list[str]
    flag_on_unapproved_still_matches_vertical_slice_only: bool


class FailClosedCheckResult(BaseModel):
    """§2 "임시 검수 환경" 요구사항 — 승인되지 않은 Pack은 Fail-Closed인지, 승인된
    Pack만 assessment_supported에 포함되는지를 임시(temp) Fixture로 직접 검증한다.
    전부 임시 디렉터리에서만 동작하고 실제 검수 파일은 전혀 건드리지 않는다."""

    target_context_id: str
    unapproved_pack_excluded_from_supported: bool
    unapproved_pack_rejected_at_context_select: bool
    unapproved_pack_rejected_error_code: str | None
    unapproved_pack_signal_excluded_by_gate: bool
    unapproved_shared_probe_anchor_excluded_from_candidates: bool
    approved_shared_probe_anchor_included_in_candidates: bool
    approved_pack_included_when_fully_approved: bool


class ComboResult(BaseModel):
    """§5 "각 조합별 기록" — 질문 원문·학생 답변 원문은 절대 담지 않는다(구조적 결과만)."""

    context_id: str
    anchor_id: str
    llm_mode: Literal["OFF", "DETERMINISTIC_STUB"] = "OFF"
    routing_ok: bool = False
    seed_ok: bool = False
    adaptive_candidate_pool_size: int = 0
    adaptive_question_count: int = 0
    shared_probe_count: int = 0
    native_probe_count: int = 0
    backup_used: bool = False
    evidence_trait_ids: list[str] = Field(default_factory=list)
    no_signal_count: int = 0
    profile_status: str = "NOT_RUN"
    major_status: str = "NOT_RUN"
    department_status: str = "NOT_RUN"
    subject_status: str = "NOT_RUN"
    subgraph_status: str = "NOT_RUN"
    failure_stage: str | None = None
    failure_reason_code: str | None = None
    # §3 검증 항목을 그대로 필드화한 격리·안전성 플래그.
    no_cross_context_leak: bool = True
    no_cross_anchor_leak: bool = True
    routing_answer_not_in_evidence: bool = True
    review_gate_applied: bool = True
    no_legacy_question_leak: bool = True
    no_infinite_loop: bool = True
    idempotent_replay_ok: bool = True
    advanced_to_next_context_ok: bool = True


class SummarySection(BaseModel):
    total_combinations: int
    normal_completion_count: int
    evidence_insufficient_count: int
    fail_closed_count: int
    actual_error_count: int
    legacy_question_leak_count: int
    anchor_mismatch_count: int
    unapproved_signal_reflected_count: int
    infinite_loop_or_cap_exceeded: bool


class MatrixReport(BaseModel):
    audit: AuditResult
    fail_closed_checks: FailClosedCheckResult
    combos: list[ComboResult]
    summary: SummarySection
    # 12개 Context 각각 1개 Anchor — 결정론적 로컬 Stub LLM으로 실제 Adaptive Tail
    # 다회 진행을 보조 검증한다(§3 run_supplementary_stub_matrix 참고). 주 60개 조합과
    # 별도로 취급한다 — summary 집계에는 포함하지 않는다.
    supplementary_stub_llm_combos: list[ComboResult] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# §1 감사
# --------------------------------------------------------------------------- #


def run_audit() -> AuditResult:
    """실제 `data/reviews/context_packs/*.json`을 읽기 전용으로만 연다(쓰지 않는다).
    `main_module._context_pack_registry`는 앱 시작 시점에 이미 만들어진 실제(운영과
    동일한) Registry다 — 이 함수는 그것을 재사용만 하고 새로 만들지 않는다."""

    registry = main_module._context_pack_registry
    packs = {p.context_id: p for p in registry.all_packs()}
    batch_definition = {
        str(batch_id): sorted(context_ids) for batch_id, context_ids in sorted(CONTEXT_ACTIVATION_BATCHES.items())
    }

    per_pack_structure: dict[str, PackStructureAudit] = {}
    real_review_all_tbd: dict[str, bool | None] = {}
    for context_id in sorted(ALL_BATCH_CONTEXT_IDS):
        pack = packs.get(context_id)
        if pack is None:
            per_pack_structure[context_id] = PackStructureAudit(discovered=False)
            real_review_all_tbd[context_id] = None
            continue
        per_pack_structure[context_id] = PackStructureAudit(
            discovered=True,
            routing_count=1,
            anchor_count=len(pack.anchor_presentations),
            seed_count=len(pack.seed_anchor_variants),
            backup_count=len(pack.anchor_backup_questions),
            review_key_count=len(registry.required_review_keys(pack)),
        )
        review_path = registry.review_status_path_for(context_id)
        if not review_path.exists():
            real_review_all_tbd[context_id] = None
        else:
            raw = json.loads(review_path.read_text(encoding="utf-8"))
            real_review_all_tbd[context_id] = all(row.get("reviewer_1_status") == "TBD" for row in raw)

    shared_probe_allowed = {
        bp.blueprint_id: sorted(bp.allowed_context_ids) for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
    }

    with _env(ENABLE_CONTEXT_PACK_RUNTIME=None):
        flag_off_supported = sorted(main_module._effective_supported_context_ids())

    with _env(ENABLE_CONTEXT_PACK_RUNTIME="true"):
        flag_on_unapproved_supported = sorted(main_module._effective_supported_context_ids())

    return AuditResult(
        batch_definition=batch_definition,
        discovered_context_ids=sorted(packs),
        discovery_errors=dict(sorted(registry.discovery_errors().items())),
        ontology_errors=dict(sorted(registry.ontology_errors().items())),
        per_pack_structure=per_pack_structure,
        real_review_all_tbd=real_review_all_tbd,
        shared_probe_blueprint_count=len(CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS),
        shared_probe_allowed_context_ids=dict(sorted(shared_probe_allowed.items())),
        flag_off_supported_context_ids=flag_off_supported,
        flag_off_matches_vertical_slice_only=flag_off_supported == sorted(VERTICAL_SLICE_CONTEXT_IDS),
        flag_on_but_unapproved_supported_context_ids=flag_on_unapproved_supported,
        flag_on_unapproved_still_matches_vertical_slice_only=(
            flag_on_unapproved_supported == sorted(VERTICAL_SLICE_CONTEXT_IDS)
        ),
    )


# --------------------------------------------------------------------------- #
# §2 임시 검수 환경
# --------------------------------------------------------------------------- #


def _approve_rows_for_pack(registry: ContextPackRegistry, pack) -> list[dict]:
    return [
        {
            "blueprint_id": key, "reviewer_1_status": "APPROVE", "reviewer_1_comment": "temp-eval-harness",
            "reviewer_2_status": "TBD", "reviewer_2_comment": "", "resolution_note": "",
        }
        for key in sorted(registry.required_review_keys(pack))
    ]


def _write_pack_approval(registry: ContextPackRegistry, review_dir: Path, pack) -> None:
    review_dir.mkdir(parents=True, exist_ok=True)
    path = review_dir / f"{pack.context_id}_review_status.json"
    path.write_text(json.dumps(_approve_rows_for_pack(registry, pack), ensure_ascii=False, indent=2), encoding="utf-8")


def _write_shared_probe_approval(
    shared_path: Path, rows: list[dict],
) -> None:
    shared_path.parent.mkdir(parents=True, exist_ok=True)
    shared_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def build_fully_approved_temp_registry(tmp_root: Path) -> ContextPackRegistry:
    """12개 실제 Pack을 전부 '임시로' 전부 승인한 Registry를 만든다. 실제
    `data/reviews/context_packs/*.json`·실제 공용 Probe 검수 파일은 전혀 열지 않는다
    (전용 임시 경로만 `review_status_dir`/`shared_probe_review_status_path`로
    주입한다) — 파일 안의 "APPROVE"는 이 프로세스 실행 동안만 존재하는 시뮬레이션
    값이다."""

    review_dir = tmp_root / "context_packs_reviews"
    shared_path = tmp_root / "shared_probes_review.json"
    registry = ContextPackRegistry(
        known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=review_dir,
        shared_probe_review_status_path=shared_path,
    )

    for pack in registry.all_packs():
        _write_pack_approval(registry, review_dir, pack)

    shared_rows: list[dict] = []
    for bp in CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS:
        for context_id in sorted(bp.allowed_context_ids):
            pack = registry.get_pack(context_id)
            if pack is None:
                continue
            anchor_ids = sorted(a.anchor_id for a in pack.anchor_presentations)
            shared_rows.append(
                {
                    "blueprint_id": bp.blueprint_id, "context_id": context_id, "reviewer_1_status": "APPROVE",
                    "reviewer_1_comment": "temp-eval-harness", "approved_anchor_ids": anchor_ids,
                    "excluded_anchor_ids": [], "resolution_note": "", "revision": "1",
                }
            )
    _write_shared_probe_approval(shared_path, shared_rows)
    return registry


def run_fail_closed_checks(tmp_root: Path) -> FailClosedCheckResult:
    """§2 "승인되지 않은 Pack은 Fail-Closed인지"·"승인된 Pack만 assessment_supported에
    포함되는지"를 전용 임시 Registry로 직접 검증한다. `business`(활성화 1차 배치)를
    대상으로 쓴다 — 실제 12개 Pack 중 하나일 뿐, 이 선택 자체가 결과에 영향을 주지
    않는다(다른 Pack도 동일한 Registry 로직을 공유한다)."""

    target_context_id = "business"
    review_dir = tmp_root / "reviews"
    shared_path = tmp_root / "shared.json"
    registry = ContextPackRegistry(
        known_context_ids=frozenset(CONTEXT_IDS), review_status_dir=review_dir,
        shared_probe_review_status_path=shared_path,
    )
    pack = registry.get_pack(target_context_id)
    if pack is None:
        raise RuntimeError(
            f"{target_context_id!r} Pack이 discover되지 않았다 — Fail-Closed 검증 자체를 수행할 수 없다"
        )

    # (1) 검수 파일이 아예 없는 상태 — Registry 레벨에서 제외돼야 한다.
    with _env(ENABLE_CONTEXT_PACK_RUNTIME="true"):
        supported_before = registry.assessment_supported_context_ids(list(VERTICAL_SLICE_CONTEXT_IDS))
    unapproved_excluded = target_context_id not in supported_before

    # (2) HTTP 레벨 — context-select가 이 미승인 Context를 422로 거부해야 한다.
    runtime = ContextPackRuntime(registry, lambda: True, frozenset(VERTICAL_SLICE_CONTEXT_IDS))
    client = TestClient(app)
    select_rejected = False
    select_error_code: str | None = None
    with (
        patch.object(main_module, "_context_pack_registry", registry),
        patch.object(main_module, "_context_pack_runtime", runtime),
        patch.object(main_module, "_llm_client", None),
        patch.object(main_module, "_tracer", Tracer(client=None)),
        _env(ENABLE_CONTEXT_PACK_RUNTIME="true"),
    ):
        r = client.post("/assessment/session")
        session_id = r.json()["session_id"]
        client.post(
            "/assessment/interest-rating",
            json={"session_id": session_id, "ratings": {_COMPANION_CONTEXT_ID: 4, target_context_id: 5}},
        )
        r = client.post(
            "/assessment/context-select",
            json={
                "session_id": session_id,
                "selected_preferred_context_ids": [_COMPANION_CONTEXT_ID, target_context_id],
            },
        )
        select_rejected = r.status_code == 422
        select_error_code = _error_code(r)

    # (3) Signal 게이트 레벨 — 승인되지 않은 상태에서 Evidence가 있다고 가정해도
    # 게이트가 거부해야 한다(순수 함수 직접 호출, 세션·State를 만들지 않는다).
    seed = pack.seed_anchor_variants[0]
    seed_option = seed.question.options[0]
    synthetic_evidence = EvidenceRecord(
        evidence_id="ev_fail_closed_check", answer_id="ans_fail_closed_check",
        question_id=seed.question.question_id, question_frame_id=seed.question.frame_id,
        option_role_id=seed_option.role_id, option_text=seed_option.text,
        applied_primary_trait_delta=seed_option.primary_trait_delta, evidence_origin=EvidenceOrigin.PRIMARY_BLUEPRINT,
        context=target_context_id, source_type="pack_context_seed_question", generator_version="v1",
        quality_gate_status="passed", source_question_family_id="seed",
        source_blueprint_id=f"{seed.question.question_id}_blueprint",
    )
    signal_excluded = not is_evidence_signal_approved(
        synthetic_evidence, {target_context_id: seed.anchor_id}, registry
    )

    # (4) Shared Probe: Context는 승인, 특정 Anchor만 미승인 — 그 Anchor에서는 후보에서
    # 빠지고 승인된 Anchor에서는 후보에 남아야 한다.
    _write_pack_approval(registry, review_dir, pack)
    blueprint = CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS[0]
    anchor_ids = sorted(a.anchor_id for a in pack.anchor_presentations)
    approved_anchor, excluded_anchor = anchor_ids[0], anchor_ids[-1]
    _write_shared_probe_approval(
        shared_path,
        [
            {
                "blueprint_id": blueprint.blueprint_id, "context_id": target_context_id,
                "reviewer_1_status": "APPROVE", "reviewer_1_comment": "temp-eval-harness",
                "approved_anchor_ids": [approved_anchor], "excluded_anchor_ids": [excluded_anchor],
                "resolution_note": "", "revision": "1",
            }
        ],
    )
    approved_candidates = {
        bp.blueprint_id for bp in registry.shared_probe_blueprints_for_context(target_context_id, approved_anchor)
    }
    excluded_candidates = {
        bp.blueprint_id for bp in registry.shared_probe_blueprints_for_context(target_context_id, excluded_anchor)
    }
    anchor_excluded_ok = blueprint.blueprint_id not in excluded_candidates
    anchor_included_ok = blueprint.blueprint_id in approved_candidates

    # (5) 대조군 — Pack이 완전히 승인되면 supported에 포함돼야 한다(이미 (4)에서 Pack
    # 자체는 전부 APPROVE로 썼다).
    with _env(ENABLE_CONTEXT_PACK_RUNTIME="true"):
        supported_after = registry.assessment_supported_context_ids(list(VERTICAL_SLICE_CONTEXT_IDS))
    approved_included = target_context_id in supported_after

    return FailClosedCheckResult(
        target_context_id=target_context_id,
        unapproved_pack_excluded_from_supported=unapproved_excluded,
        unapproved_pack_rejected_at_context_select=select_rejected,
        unapproved_pack_rejected_error_code=select_error_code,
        unapproved_pack_signal_excluded_by_gate=signal_excluded,
        unapproved_shared_probe_anchor_excluded_from_candidates=anchor_excluded_ok,
        approved_shared_probe_anchor_included_in_candidates=anchor_included_ok,
        approved_pack_included_when_fully_approved=approved_included,
    )


# --------------------------------------------------------------------------- #
# §3 12 Context × 5 Anchor Matrix
# --------------------------------------------------------------------------- #


def _routing_option_for_anchor(routing_blueprint, anchor_id: str) -> dict:
    mapping = next(m for m in routing_blueprint.option_mappings if m.context_anchor == anchor_id)
    option = next(o for o in routing_blueprint.base_question.options if o.role_id == mapping.role_id)
    return {"option_id": option.option_id, "role_id": option.role_id}


def run_combo(
    client: TestClient, registry: ContextPackRegistry, context_id: str, anchor_id: str,
    llm_mode: Literal["OFF", "DETERMINISTIC_STUB"] = "OFF",
) -> ComboResult:
    result = ComboResult(context_id=context_id, anchor_id=anchor_id, llm_mode=llm_mode)
    pack = registry.get_pack(context_id)
    if pack is None:
        result.failure_stage = "PACK_NOT_DISCOVERED"
        result.failure_reason_code = "pack_missing_in_temp_registry"
        return result

    expected_seed_qid = next(s.question.question_id for s in pack.seed_anchor_variants if s.anchor_id == anchor_id)
    backup_entry = next((b for b in pack.anchor_backup_questions if b.anchor_id == anchor_id), None)
    expected_backup_qid = backup_entry.question.question_id if backup_entry is not None else None
    native_blueprint_ids = {p.blueprint_id for p in pack.direct_probe_candidates}
    # §3 "Adaptive Probe 후보 조회" — Runtime과 완전히 같은 함수로, 실제 서빙 여부(LLM
    # 상태)와 무관하게 이 Anchor에서 후보 풀이 실제로 존재하는지부터 확인한다.
    result.adaptive_candidate_pool_size = len(
        registry.shared_probe_blueprints_for_context(context_id, anchor_id)
    ) + len(native_blueprint_ids)

    r = client.post("/assessment/session")
    session_id = r.json()["session_id"]
    client.post(
        "/assessment/interest-rating",
        json={"session_id": session_id, "ratings": {_COMPANION_CONTEXT_ID: 4, context_id: 5}},
    )
    r = client.post(
        "/assessment/context-select",
        json={"session_id": session_id, "selected_preferred_context_ids": [_COMPANION_CONTEXT_ID, context_id]},
    )
    if r.status_code != 200:
        result.failure_stage = "CONTEXT_SELECT"
        result.failure_reason_code = _error_code(r)
        return result
    r = client.post(
        "/assessment/context-confirm",
        json={"session_id": session_id, "final_context_ids": [context_id, _COMPANION_CONTEXT_ID]},
    )
    if r.status_code != 200:
        result.failure_stage = "CONTEXT_CONFIRM"
        result.failure_reason_code = _error_code(r)
        return result

    turn = 0
    idempotent_checked = False
    for roundtrip in range(1, _MAX_HTTP_ROUNDTRIPS_PER_COMBO + 1):
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        if r.status_code != 200:
            result.failure_stage = "NEXT_QUESTION"
            result.failure_reason_code = _error_code(r)
            return result
        body = r.json()
        status = body["status"]

        if status == "CONTEXT_EARLY_TERMINATED":
            break

        question = body.get("question")
        if question is None:
            result.failure_stage = "NEXT_QUESTION_EMPTY"
            result.failure_reason_code = f"status={status}"
            return result

        if question["context"] != context_id:
            result.no_cross_context_leak = False
            result.no_legacy_question_leak = result.no_legacy_question_leak and question["context"] not in (
                "game", "media", "school_life",
            )

        state = main_module._store.load(session_id)
        family = state.current_question_family_id
        blueprint_id = state.current_question_blueprint_id

        if family == "context_routing":
            result.routing_ok = True
            option = _routing_option_for_anchor(pack.routing_blueprint, anchor_id)
            ar = client.post(
                "/assessment/answer",
                json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": option["option_id"]},
            )
            if ar.status_code != 200:
                result.failure_stage = "ROUTING_ANSWER"
                result.failure_reason_code = _error_code(ar)
                return result
            continue

        if family == "seed":
            if question["question_id"] != expected_seed_qid:
                result.no_cross_anchor_leak = False
            else:
                result.seed_ok = True
            if not idempotent_checked:
                r2 = client.post("/assessment/next-question", params={"session_id": session_id})
                idempotent_checked = True
                result.idempotent_replay_ok = r2.status_code == 200 and r2.json() == body
            selected = question["options"][turn % 5]
        elif family == "pack_backup":
            result.backup_used = True
            if expected_backup_qid is None or question["question_id"] != expected_backup_qid:
                result.no_cross_anchor_leak = False
            selected = question["options"][turn % 5]
        elif family == "pack_direct_probe":
            result.adaptive_question_count += 1
            candidate_ids = {
                c.blueprint_id for c in registry.shared_probe_blueprints_for_context(context_id, anchor_id)
            } | native_blueprint_ids
            if blueprint_id not in candidate_ids:
                result.no_cross_anchor_leak = False
            if blueprint_id in native_blueprint_ids:
                result.native_probe_count += 1
            else:
                result.shared_probe_count += 1
            selected = question["options"][turn % 5]
        else:
            result.failure_stage = "UNEXPECTED_FAMILY"
            result.failure_reason_code = f"family={family}"
            return result

        if not selected.get("primary_trait_delta"):
            result.no_signal_count += 1

        ar = client.post(
            "/assessment/answer",
            json={"session_id": session_id, "question_id": question["question_id"], "selected_option_id": selected["option_id"]},
        )
        if ar.status_code != 200:
            result.failure_stage = "ANSWER"
            result.failure_reason_code = _error_code(ar)
            return result
        turn += 1
    else:
        result.no_infinite_loop = False
        result.failure_stage = "LOOP_CAP_EXCEEDED"
        result.failure_reason_code = f"exceeded_{_MAX_HTTP_ROUNDTRIPS_PER_COMBO}_roundtrips"
        return result

    state = main_module._store.load(session_id)
    context_evidence = [e for e in state.evidence_ledger if e.context == context_id]
    result.evidence_trait_ids = sorted({trait_id for e in context_evidence for trait_id in e.applied_primary_trait_delta})
    result.routing_answer_not_in_evidence = all(
        e.source_question_family_id != "context_routing" for e in state.evidence_ledger
    )
    result.review_gate_applied = all(
        is_evidence_signal_approved(e, state.context_anchor_choices, registry) for e in context_evidence
    )

    if body["assessment_complete"]:
        result.advanced_to_next_context_ok = True
    else:
        r = client.post("/assessment/next-question", params={"session_id": session_id})
        result.advanced_to_next_context_ok = r.status_code == 200

    _run_section4(client, session_id, result)
    return result


def _run_section4(client: TestClient, session_id: str, result: ComboResult) -> None:
    """§4 Profile·전공·과목 후속 흐름. 결과가 비어 있어도 억지로 Fixture를 채우지
    않는다 — Evidence 부족은 EVIDENCE_NOT_READY/빈 목록으로 그대로 기록한다."""

    r = client.get(f"/profile/{session_id}")
    result.profile_status = _classify_get(r)

    r = client.get(f"/majors/{session_id}")
    if r.status_code != 200:
        result.major_status = _classify_get(r)
        result.department_status = "SKIPPED"
        result.subject_status = "SKIPPED"
    else:
        body = r.json()
        majors = list(body.get("relevant_majors", [])) + list(body.get("explore_together_majors", []))
        if not majors:
            result.major_status = "INSUFFICIENT_EVIDENCE"
            result.department_status = "SKIPPED_NO_MAJOR"
            result.subject_status = "SKIPPED_NO_MAJOR"
        else:
            result.major_status = "OK"
            top_major_id = majors[0]["major_id"]
            dr = client.get(f"/departments/{top_major_id}")
            result.department_status = "OK" if dr.status_code == 200 else _classify_get(dr)
            sr = client.get(f"/subjects/{session_id}", params={"selected_major_id": top_major_id})
            result.subject_status = _classify_get(sr)

    gr = client.get(f"/subgraph/{session_id}")
    result.subgraph_status = _classify_get(gr)


def run_matrix(tmp_root: Path) -> tuple[ContextPackRegistry, list[ComboResult]]:
    registry = build_fully_approved_temp_registry(tmp_root)
    runtime = ContextPackRuntime(registry, lambda: True, frozenset(VERTICAL_SLICE_CONTEXT_IDS))
    client = TestClient(app)
    combos: list[ComboResult] = []
    with (
        patch.object(main_module, "_context_pack_registry", registry),
        patch.object(main_module, "_context_pack_runtime", runtime),
        patch.object(main_module, "_llm_client", None),
        patch.object(main_module, "_trace_client", None),
        patch.object(main_module, "_tracer", Tracer(client=None)),
        _env(ENABLE_CONTEXT_PACK_RUNTIME="true", ENABLE_TRAIT_VECTOR_V2_PRIMARY="true"),
    ):
        for batch_id in sorted(CONTEXT_ACTIVATION_BATCHES):
            for context_id in sorted(CONTEXT_ACTIVATION_BATCHES[batch_id]):
                pack = registry.get_pack(context_id)
                if pack is None:
                    combos.append(
                        ComboResult(
                            context_id=context_id, anchor_id="(unknown)", failure_stage="PACK_NOT_DISCOVERED",
                            failure_reason_code="pack_missing_in_temp_registry", no_infinite_loop=True,
                        )
                    )
                    continue
                for anchor in pack.anchor_presentations:
                    combos.append(run_combo(client, registry, context_id, anchor.anchor_id))
    return registry, combos


def run_supplementary_stub_matrix(tmp_root: Path) -> list[ComboResult]:
    """주 60개 조합(§3)은 실제 LLM OFF로 돌린다 — Backup Fallback으로 즉시 수렴하므로
    (`generate_v2_direct_probe_question`이 `allow_base_question_fallback=False`로
    호출돼 LLM이 없으면 항상 None), 어떤 Native/Shared Direct Probe 질문도 실제로
    "서빙"되는 경로까지는 도달하지 못한다(§3 "LLM OFF에서도 결정론적 종료"를 정확히
    보여주는 결과이지 결함이 아니다 — 자세한 내용은 보고서 §6 참고).

    이 보조 섹션은 `DeterministicStubLLMClient`(순수 로컬 객체, 네트워크 호출 없음)로
    12개 Context 각각의 첫 번째 Anchor 1개씩(총 12개 조합)만 추가로 돌려서, Adaptive
    Tail이 실제로 여러 번(최대 6개) 진행될 때도 Context/Anchor 격리와 Review Gate가
    깨지지 않는지 확인한다. 여전히 외부 LLM·네트워크 호출은 전혀 없다."""

    registry = build_fully_approved_temp_registry(tmp_root)
    runtime = ContextPackRuntime(registry, lambda: True, frozenset(VERTICAL_SLICE_CONTEXT_IDS))
    client = TestClient(app)
    combos: list[ComboResult] = []
    with (
        patch.object(main_module, "_context_pack_registry", registry),
        patch.object(main_module, "_context_pack_runtime", runtime),
        patch.object(main_module, "_llm_client", DeterministicStubLLMClient()),
        patch.object(main_module, "_trace_client", None),
        patch.object(main_module, "_tracer", Tracer(client=None)),
        _env(ENABLE_CONTEXT_PACK_RUNTIME="true", ENABLE_TRAIT_VECTOR_V2_PRIMARY="true"),
    ):
        for batch_id in sorted(CONTEXT_ACTIVATION_BATCHES):
            for context_id in sorted(CONTEXT_ACTIVATION_BATCHES[batch_id]):
                pack = registry.get_pack(context_id)
                if pack is None:
                    continue
                first_anchor = pack.anchor_presentations[0]
                combos.append(run_combo(client, registry, context_id, first_anchor.anchor_id, llm_mode="DETERMINISTIC_STUB"))
    return combos


# --------------------------------------------------------------------------- #
# 요약·보고서 조립
# --------------------------------------------------------------------------- #


def _classify_combo(combo: ComboResult) -> Literal["OK", "EVIDENCE_INSUFFICIENT", "FAIL_CLOSED", "ERROR"]:
    reason = (combo.failure_reason_code or "").upper()
    if combo.failure_stage is None:
        if combo.profile_status == "EVIDENCE_NOT_READY" or combo.major_status == "INSUFFICIENT_EVIDENCE":
            return "EVIDENCE_INSUFFICIENT"
        return "OK"
    if "EVIDENCE_NOT_READY" in reason:
        return "EVIDENCE_INSUFFICIENT"
    if combo.failure_stage in ("CONTEXT_SELECT", "CONTEXT_CONFIRM") and "VALIDATION_ERROR" in reason:
        # 이번 60개 조합은 전부 임시로 완전 승인된 상태로 실행하므로, 여기 도달하면
        # 승인 로직이 예상과 다르게 동작했다는 뜻이다 — Fail-Closed가 아니라 오류로 센다.
        return "ERROR"
    return "ERROR"


def build_summary(combos: list[ComboResult]) -> SummarySection:
    buckets = [_classify_combo(c) for c in combos]
    return SummarySection(
        total_combinations=len(combos),
        normal_completion_count=buckets.count("OK"),
        evidence_insufficient_count=buckets.count("EVIDENCE_INSUFFICIENT"),
        fail_closed_count=buckets.count("FAIL_CLOSED"),
        actual_error_count=buckets.count("ERROR"),
        legacy_question_leak_count=sum(1 for c in combos if not c.no_cross_context_leak or not c.no_legacy_question_leak),
        anchor_mismatch_count=sum(1 for c in combos if not c.no_cross_anchor_leak),
        unapproved_signal_reflected_count=sum(1 for c in combos if not c.review_gate_applied),
        infinite_loop_or_cap_exceeded=any(not c.no_infinite_loop for c in combos),
    )


def _render_markdown(report: MatrixReport) -> str:
    lines: list[str] = []
    lines.append("# ContextPack Matrix Diagnostics — 12 Context × 5 Anchor")
    lines.append("")
    lines.append(
        "진단 전용 보고서다 — 이 실행에서 어떤 ContextPack·Shared Probe도 실제로 "
        "APPROVE되지 않았다(모든 승인은 `tempfile` 임시 경로에서만 이뤄졌다). "
        "질문 원문·학생 답변 원문은 담지 않는다."
    )
    lines.append("")

    lines.append("## 1. 감사 요약")
    lines.append("")
    lines.append(f"- 활성화 배치 정본: {report.audit.batch_definition}")
    lines.append(f"- 발견된 Context Pack: {report.audit.discovered_context_ids} ({len(report.audit.discovered_context_ids)}개)")
    lines.append(f"- discovery_errors: {report.audit.discovery_errors or '(없음)'}")
    lines.append(f"- ontology_errors: {report.audit.ontology_errors or '(없음)'}")
    lines.append(
        f"- Flag OFF 지원 Context: {report.audit.flag_off_supported_context_ids} "
        f"(기존 3개와 일치: {report.audit.flag_off_matches_vertical_slice_only})"
    )
    lines.append(
        f"- Flag ON이지만 실제 검수 파일이 전부 TBD일 때 지원 Context: "
        f"{report.audit.flag_on_but_unapproved_supported_context_ids} "
        f"(기존 3개와 일치: {report.audit.flag_on_unapproved_still_matches_vertical_slice_only})"
    )
    lines.append(f"- Shared Probe Blueprint 개수: {report.audit.shared_probe_blueprint_count}")
    lines.append("")
    lines.append("| context_id | 발견 | Routing | Anchor | Seed | Backup | 검수 Key | 실제 검수 전부 TBD |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for context_id, structure in sorted(report.audit.per_pack_structure.items()):
        tbd = report.audit.real_review_all_tbd.get(context_id)
        tbd_label = "TBD(파일없음=Fail-Closed와 동치)" if tbd is None else ("예" if tbd else "**아니오(검토 진행됨)**")
        lines.append(
            f"| {context_id} | {'예' if structure.discovered else '**아니오**'} | "
            f"{structure.routing_count if structure.discovered else '-'} | "
            f"{structure.anchor_count if structure.discovered else '-'} | "
            f"{structure.seed_count if structure.discovered else '-'} | "
            f"{structure.backup_count if structure.discovered else '-'} | "
            f"{structure.review_key_count if structure.discovered else '-'} | {tbd_label} |"
        )
    lines.append("")

    lines.append("## 2. Fail-Closed 직접 검증 (임시 Fixture)")
    lines.append("")
    fc = report.fail_closed_checks
    lines.append(f"- 대상 Context: `{fc.target_context_id}`")
    lines.append(f"- 미승인 Pack이 assessment_supported에서 제외됨: {fc.unapproved_pack_excluded_from_supported}")
    lines.append(
        f"- 미승인 Pack Context 선택이 422로 거부됨: {fc.unapproved_pack_rejected_at_context_select} "
        f"(error_code={fc.unapproved_pack_rejected_error_code})"
    )
    lines.append(f"- 미승인 Signal이 Review Gate에서 제외됨: {fc.unapproved_pack_signal_excluded_by_gate}")
    lines.append(
        f"- 미승인 Anchor의 Shared Probe가 후보에서 제외됨: "
        f"{fc.unapproved_shared_probe_anchor_excluded_from_candidates}"
    )
    lines.append(
        f"- 승인된 Anchor의 Shared Probe는 후보에 포함됨: "
        f"{fc.approved_shared_probe_anchor_included_in_candidates}"
    )
    lines.append(f"- 완전 승인 후 assessment_supported에 포함됨(대조군): {fc.approved_pack_included_when_fully_approved}")
    lines.append("")

    lines.append("## 3. 60개 조합 요약")
    lines.append("")
    lines.append(
        "**4개 항목은 서로 배타적인 결과 분류다** — \"정상 종료\"는 Runtime 흐름"
        "(Routing→Anchor→Seed→Backup Fallback→Context 종료)뿐 아니라 후속 Major "
        "Matching까지 최소 기준을 채운 경우만 센다. \"Evidence 부족\"은 Runtime 흐름 "
        "자체는 끝까지 정상이었지만(routing_ok/seed_ok 등 전부 정상) 단일 Context 답변 "
        "몇 개만으로는 `/majors`의 최소 사용 가능 Trait/Vector Group 기준을 못 채운 "
        "경우다 — 이는 결함이 아니라 설계상 예상된 결과다(지시서 §4 \"모든 Context–Anchor "
        "조합이 충분한 Evidence를 만들 필요는 없다\")."
    )
    lines.append("")
    s = report.summary
    lines.append(f"- 총 조합: {s.total_combinations}")
    lines.append(f"- 정상 종료: {s.normal_completion_count}")
    lines.append(f"- Evidence 부족(정상 결과로 취급): {s.evidence_insufficient_count}")
    lines.append(f"- Fail-Closed로 분류: {s.fail_closed_count}")
    lines.append(f"- 실제 오류: {s.actual_error_count}")
    lines.append(f"- Legacy/타 Context 질문 누출: {s.legacy_question_leak_count}")
    lines.append(f"- Anchor 불일치: {s.anchor_mismatch_count}")
    lines.append(f"- 승인되지 않은 Signal 반영: {s.unapproved_signal_reflected_count}")
    lines.append(f"- 무한 루프·상한 초과 발생: {s.infinite_loop_or_cap_exceeded}")
    lines.append("")

    lines.append("## 4. 조합별 상세")
    lines.append("")
    lines.append(
        "| context_id | anchor_id | routing | seed | adaptive | shared | backup | "
        "no_signal | evidence_traits | profile | major | dept | subject | subgraph | 상태 | failure |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for c in report.combos:
        bucket = _classify_combo(c)
        failure = f"{c.failure_stage}:{c.failure_reason_code}" if c.failure_stage else "-"
        lines.append(
            f"| {c.context_id} | {c.anchor_id} | {c.routing_ok} | {c.seed_ok} | {c.adaptive_question_count} | "
            f"{c.shared_probe_count} | {c.backup_used} | {c.no_signal_count} | "
            f"{','.join(c.evidence_trait_ids) or '(없음)'} | {c.profile_status} | {c.major_status} | "
            f"{c.department_status} | {c.subject_status} | {c.subgraph_status} | {bucket} | {failure} |"
        )
    lines.append("")

    isolation_failures = [
        c for c in report.combos
        if not c.no_cross_context_leak or not c.no_cross_anchor_leak or not c.routing_answer_not_in_evidence
        or not c.review_gate_applied or not c.idempotent_replay_ok or not c.advanced_to_next_context_ok
    ]
    lines.append("## 5. 격리·안전성 위반이 있는 조합")
    lines.append("")
    if not isolation_failures:
        lines.append("없음 — 60개 조합 전부 Context/Anchor 격리, Routing Evidence 미반영, Review Gate 적용, "
                      "멱등 재현, Context 전환이 정상이었다.")
    else:
        for c in isolation_failures:
            lines.append(
                f"- {c.context_id}/{c.anchor_id}: no_cross_context_leak={c.no_cross_context_leak}, "
                f"no_cross_anchor_leak={c.no_cross_anchor_leak}, "
                f"routing_answer_not_in_evidence={c.routing_answer_not_in_evidence}, "
                f"review_gate_applied={c.review_gate_applied}, idempotent_replay_ok={c.idempotent_replay_ok}, "
                f"advanced_to_next_context_ok={c.advanced_to_next_context_ok}"
            )
    lines.append("")

    lines.append("## 6. 보조 검증 — 결정론적 로컬 Stub LLM (실제 LLM·네트워크 호출 아님)")
    lines.append("")
    lines.append(
        "위 §3의 60개 조합은 실제 `_llm_client=None`(LLM OFF)으로 실행했다 — "
        "`generate_v2_direct_probe_question()`이 Pack Context에서는 "
        "`allow_base_question_fallback=False`로 호출되므로, LLM이 없으면 Adaptive Tail "
        "첫 시도에서 곧바로 그 Anchor의 (유일한) Backup으로 넘어가고, Backup까지 소진되면 "
        "`STOP_GENERATION_EXHAUSTED`로 Context가 끝난다 — 이게 버그가 아니라 "
        "\"LLM OFF에서도 결정론적으로 종료한다\"는 설계 그대로다. 그 결과 §3에서는 "
        "`adaptive_question_count`/`shared_probe_count`/`native_probe_count`가 항상 0이다."
    )
    lines.append(
        "그래서 이 §6은 순수 로컬 객체 `DeterministicStubLLMClient`(네트워크 호출 없음, "
        "Blueprint의 Role 순서만 그대로 유지하는 placeholder 문장 반환)로 12개 Context "
        "각각의 Anchor 1개씩(총 12개 조합)만 추가로 실행해, Adaptive Tail이 실제로 여러 번 "
        "진행될 때도 격리·Review Gate가 유지되는지 보조로 확인한다."
    )
    lines.append("")
    lines.append(
        "| context_id | anchor_id | adaptive_candidate_pool | adaptive_served | shared | native | backup | "
        "no_signal | evidence_traits | 격리 위반 |"
    )
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for c in report.supplementary_stub_llm_combos:
        violation = not (
            c.no_cross_context_leak and c.no_cross_anchor_leak and c.routing_answer_not_in_evidence
            and c.review_gate_applied and c.idempotent_replay_ok and c.advanced_to_next_context_ok
        )
        lines.append(
            f"| {c.context_id} | {c.anchor_id} | {c.adaptive_candidate_pool_size} | "
            f"{c.adaptive_question_count} | {c.shared_probe_count} | {c.native_probe_count} | "
            f"{c.backup_used} | {c.no_signal_count} | {','.join(c.evidence_trait_ids) or '(없음)'} | "
            f"{'있음' if violation else '없음'}{f' ({c.failure_stage}:{c.failure_reason_code})' if c.failure_stage else ''} |"
        )
    lines.append("")

    # 섹션마다 구분용 빈 줄을 append해온 결과, 마지막 요소도 ""라 join 후 개행이
    # 하나 남고 그 뒤에 다시 "\n"을 붙이면 EOF에 빈 줄이 하나 더 생긴다(2026-08-24
    # 검수 서버 재시작 전 점검에서 git show --check로 발견). rstrip으로 끝의 빈
    # 줄들을 걷어내고 정확히 한 개의 개행으로만 끝낸다.
    return "\n".join(lines).rstrip("\n") + "\n"


def build_report(
    audit: AuditResult, fail_closed: FailClosedCheckResult, combos: list[ComboResult],
    supplementary_combos: list[ComboResult] | None = None,
) -> MatrixReport:
    return MatrixReport(
        audit=audit, fail_closed_checks=fail_closed, combos=combos, summary=build_summary(combos),
        supplementary_stub_llm_combos=supplementary_combos or [],
    )


def _write_report(report: MatrixReport) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_REPORT_PATH.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    MD_REPORT_PATH.write_text(_render_markdown(report), encoding="utf-8")


def main() -> MatrixReport:
    audit = run_audit()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_root = Path(tmp)
        fail_closed = run_fail_closed_checks(tmp_root / "fail_closed")
        _registry, combos = run_matrix(tmp_root / "matrix")
        supplementary_combos = run_supplementary_stub_matrix(tmp_root / "supplementary_stub")
    report = build_report(audit, fail_closed, combos, supplementary_combos)
    _write_report(report)
    return report


if __name__ == "__main__":
    main()
