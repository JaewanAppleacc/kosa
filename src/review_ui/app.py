"""V2 Direct Probe 검수 UI — 내부 전용 FastAPI App — 2026-08-23 Trait Ontology
v2(2.4단계) §2/§10.

`src/api/main.py`(공개 서비스 API)와 완전히 별개의 App이다. 이 파일을 `src/api/main.py`의
Router로 등록하지 않는다 — `scripts/run_v2_direct_probe_review_ui.py`가 이 App을 직접
`127.0.0.1`에만 바인딩해서 띄운다. 학생 답변이나 개인정보는 다루지 않는다 — 검수
대상은 고정 Blueprint·Mapping과 두 검토자의 판단뿐이다.

이 App은 어떤 항목도 스스로 승인하지 않는다 — `review_service`가 그대로 반영한다."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.data.contexts.context_definitions import CONTEXT_IDS
from src.data.questions.context_pack_shared_probe_blueprints import CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS
from src.review_ui import canonical_major_group_bridge_review_service as cmgbrs
from src.review_ui import context_pack_review_service as cprs
from src.review_ui import review_service as rs
from src.review_ui.schemas import (
    AnchorPreviewResponse,
    BackupAnchorPreviewResponse,
    BackupQuestionListResponse,
    BridgeReviewListResponse,
    ContextPackListResponse,
    QuestionListResponse,
    RoutingQuestionListResponse,
    SeedAnchorQuestionListResponse,
    SharedProbeListResponse,
    SummaryResponse,
    UpdateBridgeReviewRequest,
    UpdateContextPackReviewRequest,
    UpdateOptionReviewRequest,
    UpdateQuestionReviewRequest,
    UpdateReviewResponse,
    UpdateSharedProbeReviewRequest,
)
from src.services.context_pack_registry import ContextPackRegistry
from src.services.trait_ontology_v2 import load_trait_ontology_v2

_STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="V2 Direct Probe Review (Internal, Local Only)",
    description=(
        "개발자용 로컬 전용 검수 도구 — 학생용 서비스 API(src/api/main.py)와 완전히 분리돼 "
        "있다. 127.0.0.1에만 바인딩해서 실행해야 한다."
    ),
)


def _http_error(status_code: int, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"error": message})


# 2026-08-23 Trait Ontology v2(2.8단계) §9 — `src/api/main.py`의 Registry와는 완전히
# 별개 인스턴스다(서로 다른 FastAPI App이라 공유하지 않는다 — Department/Subject
# Repository와 달리 이 인스턴스는 파일을 읽기만 하므로 별도로 만들어도 비용이 낮다).
# 여기서는 검수 화면이 목적이라 승인 여부와 무관하게 발견된 Pack을 전부 보여준다
# (Fail-Closed 게이트는 `main.py`의 Runtime 쪽에만 적용된다).
_context_pack_registry = ContextPackRegistry(known_context_ids=frozenset(CONTEXT_IDS))
_trait_definitions_by_id = {t.trait_id: t for t in load_trait_ontology_v2()}


# 2.4단계 §13: 매 요청마다 `rs.QUESTION_REVIEW_PATH`/`rs.OPTION_REVIEW_PATH`를 모듈
# 속성으로 "그때그때" 다시 읽는다(함수 기본 인자로 한 번만 바인딩하지 않는다) — 그래야
# 테스트가 `unittest.mock.patch("src.review_ui.review_service.QUESTION_REVIEW_PATH", ...)`
# 로 임시 파일 경로를 주입했을 때 이 App도 실제로 그 경로를 쓴다(커밋된 실제 JSON을
# 절대 건드리지 않고 테스트할 수 있다).


@app.get("/internal/review/v2/questions", response_model=QuestionListResponse)
def get_questions() -> QuestionListResponse:
    questions, q_rev, o_rev = rs.build_question_list(
        question_path=rs.QUESTION_REVIEW_PATH, option_path=rs.OPTION_REVIEW_PATH,
    )
    return QuestionListResponse(
        questions=questions, question_review_revision=q_rev, option_review_revision=o_rev,
    )


@app.get("/internal/review/v2/summary", response_model=SummaryResponse)
def get_summary() -> SummaryResponse:
    return rs.build_summary(question_path=rs.QUESTION_REVIEW_PATH, option_path=rs.OPTION_REVIEW_PATH)


@app.patch("/internal/review/v2/questions/{blueprint_id}", response_model=UpdateReviewResponse)
def patch_question(blueprint_id: str, payload: UpdateQuestionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_question_review(
            blueprint_id=blueprint_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, question_path=rs.QUESTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


@app.patch(
    "/internal/review/v2/questions/{blueprint_id}/options/{role_id}", response_model=UpdateReviewResponse,
)
def patch_option(blueprint_id: str, role_id: str, payload: UpdateOptionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_option_review(
            blueprint_id=blueprint_id, role_id=role_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, option_path=rs.OPTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


# 2.5단계 §10 — Context Routing 검수 Endpoint. v2 Direct Probe(위)와 완전히 별개
# 경로다 — Routing 질문은 Trait Mapping이 없으므로 별도 응답 Schema
# (`RoutingQuestionListResponse`)를 쓴다. 여기서도 매 요청마다
# `rs.ROUTING_QUESTION_REVIEW_PATH`가 아니라 store 모듈의 경로 상수를 직접 참조한다 —
# 테스트가 `unittest.mock.patch`로 경로를 바꿔 끼우면 이 App도 그 경로를 그대로 쓴다.


@app.get("/internal/review/v2/routing-questions", response_model=RoutingQuestionListResponse)
def get_routing_questions() -> RoutingQuestionListResponse:
    return rs.build_routing_question_list(
        question_path=rs.ROUTING_QUESTION_REVIEW_PATH, option_path=rs.ROUTING_OPTION_REVIEW_PATH,
    )


@app.patch("/internal/review/v2/routing-questions/{blueprint_id}", response_model=UpdateReviewResponse)
def patch_routing_question(blueprint_id: str, payload: UpdateQuestionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_routing_question_review(
            blueprint_id=blueprint_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, question_path=rs.ROUTING_QUESTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


@app.patch(
    "/internal/review/v2/routing-questions/{blueprint_id}/options/{role_id}",
    response_model=UpdateReviewResponse,
)
def patch_routing_option(blueprint_id: str, role_id: str, payload: UpdateOptionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_routing_option_review(
            blueprint_id=blueprint_id, role_id=role_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, option_path=rs.ROUTING_OPTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


# 2.5.1단계 §11 — Anchor Preview. Routing 질문에서 Anchor 하나를 고르면 실제 첫
# 후속 질문(Seed Anchor Variant)을 그대로 보여준다. 읽기 전용(GET)이라 검수 상태
# 파일을 전혀 건드리지 않는다.


@app.get("/internal/review/v2/anchor-preview", response_model=AnchorPreviewResponse)
def get_anchor_preview(context_id: str, anchor_id: str) -> AnchorPreviewResponse:
    try:
        return rs.build_anchor_preview(context_id, anchor_id)
    except rs.UnknownAnchorError as exc:
        raise _http_error(422, str(exc)) from exc


# 2.5.2단계 §12 — Seed Anchor Variant 검수 Endpoint. v2 Direct Probe·Routing과 완전히
# 별개 경로다.


@app.get("/internal/review/v2/seed-anchor-questions", response_model=SeedAnchorQuestionListResponse)
def get_seed_anchor_questions() -> SeedAnchorQuestionListResponse:
    return rs.build_seed_anchor_question_list(
        question_path=rs.SEED_ANCHOR_QUESTION_REVIEW_PATH, option_path=rs.SEED_ANCHOR_OPTION_REVIEW_PATH,
    )


@app.patch(
    "/internal/review/v2/seed-anchor-questions/{context_id}/{anchor_id}", response_model=UpdateReviewResponse,
)
def patch_seed_anchor_question(
    context_id: str, anchor_id: str, payload: UpdateQuestionReviewRequest,
) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_seed_anchor_question_review(
            context_id=context_id, anchor_id=anchor_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, question_path=rs.SEED_ANCHOR_QUESTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


@app.patch(
    "/internal/review/v2/seed-anchor-questions/{context_id}/{anchor_id}/options/{role_id}",
    response_model=UpdateReviewResponse,
)
def patch_seed_anchor_option(
    context_id: str, anchor_id: str, role_id: str, payload: UpdateOptionReviewRequest,
) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_seed_anchor_option_review(
            context_id=context_id, anchor_id=anchor_id, role_id=role_id, reviewer=payload.reviewer,
            status=payload.status, comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, option_path=rs.SEED_ANCHOR_OPTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


# 2.5.3단계 §10/§11/§14 — Backup Question 검수 Endpoint.


@app.get("/internal/review/v2/backup-questions", response_model=BackupQuestionListResponse)
def get_backup_questions() -> BackupQuestionListResponse:
    return rs.build_backup_question_list(
        question_path=rs.BACKUP_QUESTION_REVIEW_PATH, option_path=rs.BACKUP_OPTION_REVIEW_PATH,
    )


@app.get("/internal/review/v2/backup-questions/{question_id}/anchor-preview", response_model=BackupAnchorPreviewResponse)
def get_backup_anchor_preview(question_id: str, context_id: str, anchor_id: str | None = None) -> BackupAnchorPreviewResponse:
    try:
        return rs.build_backup_anchor_preview(question_id, context_id, anchor_id)
    except (rs.UnknownBlueprintError, rs.UnknownAnchorError) as exc:
        raise _http_error(422, str(exc)) from exc


@app.patch("/internal/review/v2/backup-questions/{question_id}", response_model=UpdateReviewResponse)
def patch_backup_question(question_id: str, payload: UpdateQuestionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_backup_question_review(
            question_id=question_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, question_path=rs.BACKUP_QUESTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


@app.patch(
    "/internal/review/v2/backup-questions/{question_id}/options/{role_id}", response_model=UpdateReviewResponse,
)
def patch_backup_option(question_id: str, role_id: str, payload: UpdateOptionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_backup_option_review(
            question_id=question_id, role_id=role_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, option_path=rs.BACKUP_OPTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


# 2.5.4단계 §7/§10 — Anchor Backup Question 검수 Endpoint. 기존 Backup Endpoint와
# 완전히 별도 경로·검수 상태 파일이다.


@app.get("/internal/review/v2/anchor-backup-questions", response_model=BackupQuestionListResponse)
def get_anchor_backup_questions() -> BackupQuestionListResponse:
    return rs.build_anchor_backup_question_list(
        question_path=rs.ANCHOR_BACKUP_QUESTION_REVIEW_PATH, option_path=rs.ANCHOR_BACKUP_OPTION_REVIEW_PATH,
    )


@app.get(
    "/internal/review/v2/anchor-backup-questions/{question_id}/anchor-preview",
    response_model=BackupAnchorPreviewResponse,
)
def get_anchor_backup_anchor_preview(
    question_id: str, context_id: str, anchor_id: str | None = None,
) -> BackupAnchorPreviewResponse:
    try:
        return rs.build_anchor_backup_anchor_preview(question_id, context_id, anchor_id)
    except (rs.UnknownBlueprintError, rs.UnknownAnchorError) as exc:
        raise _http_error(422, str(exc)) from exc


@app.patch("/internal/review/v2/anchor-backup-questions/{question_id}", response_model=UpdateReviewResponse)
def patch_anchor_backup_question(question_id: str, payload: UpdateQuestionReviewRequest) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_anchor_backup_question_review(
            question_id=question_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, question_path=rs.ANCHOR_BACKUP_QUESTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


@app.patch(
    "/internal/review/v2/anchor-backup-questions/{question_id}/options/{role_id}",
    response_model=UpdateReviewResponse,
)
def patch_anchor_backup_option(
    question_id: str, role_id: str, payload: UpdateOptionReviewRequest,
) -> UpdateReviewResponse:
    try:
        final_status, new_revision = rs.update_anchor_backup_option_review(
            question_id=question_id, role_id=role_id, reviewer=payload.reviewer, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
            expected_revision=payload.expected_revision, option_path=rs.ANCHOR_BACKUP_OPTION_REVIEW_PATH,
        )
    except rs.StaleRevisionError as exc:
        raise _http_error(409, str(exc)) from exc
    except (rs.UnknownBlueprintError, rs.UnknownRoleError, rs.InvalidReviewStatusError) as exc:
        raise _http_error(422, str(exc)) from exc
    return UpdateReviewResponse(ok=True, final_status=final_status, new_revision=new_revision)


# 2026-08-23 Trait Ontology v2(2.8단계) §9 — ContextPack(business 등, T·S·L이 병렬로
# 추가) 검수 Endpoint. Context마다 이 파일을 고칠 필요가 없다 — `ContextPackRegistry`가
# `src/data/context_packs/`를 자동으로 훑는다(위 인스턴스 생성 시점).


@app.get("/internal/review/v2/context-packs", response_model=ContextPackListResponse)
def get_context_packs() -> ContextPackListResponse:
    return cprs.build_context_pack_list(_context_pack_registry, _trait_definitions_by_id)


# 2026-08-23 Trait Ontology v2(2.9단계) §5/§11 — ContextPack 공용 Adaptive Probe
# Blueprint(신규 12개 Context가 공유) 검수 Endpoint. Context별 목록과 완전히 별개
# 경로다 — 이 Blueprint는 특정 Context 하나가 아니라 여러 Context가 동시에 참조한다.
# 아래 일반 `{context_id}/{key:path}` PATCH보다 먼저 등록해야 한다 — Starlette는 경로를
# 등록 순서대로 매칭하므로, 순서가 바뀌면 "shared-probes"가 context_id로 잘못 잡힌다.


@app.get("/internal/review/v2/context-packs/shared-probes", response_model=SharedProbeListResponse)
def get_shared_probes() -> SharedProbeListResponse:
    trait_definitions = {t.trait_id: t for t in load_trait_ontology_v2()}
    return cprs.build_shared_probe_list(_context_pack_registry, CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS, trait_definitions)


@app.patch(
    "/internal/review/v2/context-packs/shared-probes/{blueprint_id}/{context_id}", response_model=UpdateReviewResponse,
)
def patch_shared_probe_review(
    blueprint_id: str, context_id: str, payload: UpdateSharedProbeReviewRequest,
) -> UpdateReviewResponse:
    try:
        return cprs.update_shared_probe_review(
            _context_pack_registry, CONTEXT_PACK_SHARED_PROBE_BLUEPRINTS, blueprint_id, context_id,
            status=payload.status, comment=payload.comment,
            approved_anchor_ids=payload.approved_anchor_ids, excluded_anchor_ids=payload.excluded_anchor_ids,
            resolution_note=payload.resolution_note,
        )
    except (
        cprs.UnknownSharedProbeError, cprs.UnknownSharedProbeContextError,
        cprs.UnknownAnchorIdError, cprs.SharedProbeAnchorListValidationError,
    ) as exc:
        raise _http_error(422, str(exc)) from exc


@app.patch(
    "/internal/review/v2/context-packs/{context_id}/{key:path}", response_model=UpdateReviewResponse,
)
def patch_context_pack_review(
    context_id: str, key: str, payload: UpdateContextPackReviewRequest,
) -> UpdateReviewResponse:
    try:
        return cprs.update_context_pack_review(
            _context_pack_registry, context_id, key, status=payload.status,
            comment=payload.comment, resolution_note=payload.resolution_note,
        )
    except (cprs.UnknownContextPackError, cprs.UnknownReviewKeyError) as exc:
        raise _http_error(422, str(exc)) from exc


# 2026-08-24 지시서(a/canonical-major-bridge-review-ui) — 44개 Canonical Major
# Group Bridge Draft 검수 Endpoint. Master Draft(canonical_major_group_bridge.
# draft.jsonl)는 읽기만 하고 절대 쓰지 않는다 — PATCH는 별도 파일(data/reviews/
# canonical_major_group_bridge_review_status.json)에만 반영된다. 이 App의 다른
# Endpoint와 마찬가지로 Runtime Matching·Department 조회 어디에도 연결되지 않는다
# (이 파일을 import하는 학생 공개 API 코드는 없다).


@app.get("/internal/review/v2/canonical-major-group-bridge", response_model=BridgeReviewListResponse)
def get_canonical_major_group_bridge() -> BridgeReviewListResponse:
    return cmgbrs.build_bridge_review_list(review_status_path=cmgbrs.BRIDGE_REVIEW_STATUS_PATH)


@app.patch(
    "/internal/review/v2/canonical-major-group-bridge/{review_key}", response_model=UpdateReviewResponse,
)
def patch_canonical_major_group_bridge_review(
    review_key: str, payload: UpdateBridgeReviewRequest,
) -> UpdateReviewResponse:
    try:
        return cmgbrs.update_bridge_review(
            review_key, status=payload.status, comment=payload.comment, resolution_note=payload.resolution_note,
            review_status_path=cmgbrs.BRIDGE_REVIEW_STATUS_PATH,
        )
    except cmgbrs.UnknownBridgeReviewKeyError as exc:
        raise _http_error(422, str(exc)) from exc


@app.get("/")
def index() -> FileResponse:
    return FileResponse(_STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
