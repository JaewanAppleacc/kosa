# Context Pack 개발 가이드 — 2026-08-23 Trait Ontology v2(2.7단계) §1/§2

이 문서는 Context 확장 에이전트(business/science/sports 등 새 Context를 만드는
에이전트)를 위한 것이다. **아래 절차만 따르면 다른 어떤 공유 파일도 열 필요가
없다.**

## 1. 할 일

1. `src/data/context_packs/` 아래에 **새 파일 하나**를 만든다. 파일명은 자유지만
   `_`로 시작하면 안 된다(`_`로 시작하는 파일은 자동 발견 대상에서 제외된다 —
   `_example_pack_builder.py` 참고).
2. 그 파일 안에 최상위 상수 `CONTEXT_PACK: ContextPack`를 정의한다.
3. `PYTHONPATH=. ./.venv/bin/python -c "from src.services.context_pack_registry import discover_context_packs; print(discover_context_packs())"`
   로 자기 Pack이 오류 없이 발견되는지 확인한다.
4. Pack이 다루는 질문·선택지의 검수 상태 파일
   `data/reviews/context_packs/<context_id>_review_status.json`을 만들고, 전부
   `reviewer_1_status: "TBD"`로 시작한다(§6 "Claude가 Context 질문을 자동 APPROVE
   하지 않는다" — 사람이 검수 페이지에서 직접 채워야 한다).

`src/data/context_packs/__init__.py`도, `src/services/context_pack_registry.py`도,
`src/api/main.py`도 수정하지 않는다 — `ContextPackRegistry`가 디렉터리를 자동으로
훑는다(`pkgutil.iter_modules`).

## 2. ContextPack이 요구하는 것

`src/schemas/context_pack.py`의 `ContextPack`을 보라. 요약:

| 필드 | 개수 | 비고 |
|---|---|---|
| `routing_blueprint` | 1 | `ContextRoutingBlueprint` — Option은 Trait Signal이 없어야 한다(`primary_trait_delta={}`) |
| `anchor_presentations` | 정확히 5 | `ContextAnchorPresentation` |
| `seed_anchor_variants` | Anchor당 정확히 1 | `ContextPackSeedAnchorQuestion` — 완전히 자기 완결적(role_id→Trait Delta를 이 Pack이 직접 갖는다, 기존 3개 Vertical Slice Context처럼 외부 Legacy Seed Question을 참조하지 않는다) |
| `anchor_backup_questions` | Anchor당 정확히 1 | `ContextPackAnchorBackupQuestion` — LLM 실패 시 Fallback |
| `option_mapping_rationales` | Option 전부 | `OptionMappingRationale` — `trait_id=None`이면 NO_SIGNAL(Trait를 억지로 붙이지 않는다) |
| `direct_probe_candidates` | 0개 이상 | `V2DirectProbeBlueprint`(기존 타입 재사용) |

Fail-Fast 검증(Pydantic `model_validator`, import 즉시 발생):
- Context ID 일치(routing/anchor/seed/backup/direct_probe 전부 Pack의 `context_id`와 같아야 함)
- Anchor 정확히 5개, 중복 없음
- Routing Option의 Anchor 집합 == `anchor_presentations`의 Anchor 집합(미등록 Anchor 참조 차단)
- Seed/Backup이 Anchor마다 정확히 1개
- `question_id`/`option_id` Pack 전역 유일, `role_id` 질문 내부 유일
- `option_mapping_rationales`가 실제 Option 목록과 정확히 1:1
- Rationale의 `trait_id`가 실제 `primary_trait_delta`와 일치

**Pack 밖의 정본과 비교하는 검증**(24개 Trait Ontology 존재 여부, `context_id`가
`CONTEXT_DEFINITIONS`에 등록됐는지, 검수 승인 상태)은 Schema가 아니라
`ContextPackRegistry`(서비스 계층)가 한다 — Pack을 만들 때 Schema 검증만 통과해도
Registry가 별도로 걸러낼 수 있다는 뜻이다. `registry.ontology_errors()`/
`registry.discovery_errors()`로 원인을 확인하라.

## 3. 중앙 파일 소유권 (A 소유, 수정 금지)

다음 파일은 A(중앙 구조·통합 담당)가 소유한다. Context 확장 에이전트는 **절대
수정하지 않는다** — 수정이 필요하면 A에게 요청한다.

- `src/api/main.py`
- `src/data/contexts/context_definitions.py`
- `src/services/feature_flags.py`
- `src/schemas/assessment_state.py`
- `src/services/context_pack_registry.py`
- `outputs/mock_api/*`
- `src/review_ui/*`

## 4. 예제

`src/data/context_packs/_example_pack_builder.py::build_example_context_pack()`을
참고하라 — 실제 Pack이 아니라(자동 발견 대상 아님) 구조를 보여주는 참고용 Fixture다.
`tests/test_context_pack_schema.py`가 이 예제로 정상/오류 케이스를 모두 검증한다.

## 5. 활성화 배치

**2026-08-24 갱신 — 2.8/2.9단계에서 아래 "2.7단계 시점 한계"는 이미 해소됐다.**
`ContextPackRegistry`/`ContextPackRuntime`은 더 이상 대기 중인 계산기가 아니라
`src/api/main.py`의 실제 Assessment 질문 흐름(`/contexts`, `/assessment/
context-select`, `/assessment/context-confirm`, `/assessment/next-question`,
`/assessment/answer`)에 실제로 연결돼 있다(`main.py`의 `_effective_supported_
context_ids()`·`_context_pack_runtime`·`_serve_pack_context_question()` 참고). 이
문서는 이제 그 실제 배선을 그대로 서술한다 — Context 제작 에이전트가 코드를 다시
읽지 않고도 정확한 그림을 가질 수 있도록.

배치 순서 정본은 `src/data/contexts/context_activation_batches.py::
CONTEXT_ACTIVATION_BATCHES`다(`src/services/context_pack_registry.py`가 같은 이름으로
재노출하므로 기존 `from src.services.context_pack_registry import
CONTEXT_ACTIVATION_BATCHES` 호출부도 그대로 동작한다 — 순환 참조를 피하려고 2.9단계에서
정의 위치만 옮겼다):

- 1차: business, science, sports
- 2차: making, volunteer, writing, travel
- 3차: art_design, cooking, fashion_beauty, history_humanities, law_politics

**실제 활성화 조건(전부 AND, Fail-Closed — 하나라도 안 맞으면 그 Context는 존재하지
않는 것처럼 취급된다)**:

1. **Feature Flag OFF(`ENABLE_CONTEXT_PACK_RUNTIME` 기본값)면 위 12개 Context는
   전혀 관여하지 않는다.** `/contexts`·`/assessment/context-select`·
   `/assessment/context-confirm`이 지원한다고 답하는 Context는 기존
   `VERTICAL_SLICE_CONTEXT_IDS`(game/media/school_life) 3개뿐이다 — 새 Pack이 몇 개
   merge·승인됐든 그대로다.
2. **Feature Flag가 ON이어도, 그 Pack이 검수 승인(APPROVED)되지 않았으면 여전히
   지원 목록에 없다.** `ContextPackRegistry.assessment_supported_context_ids()`가
   `is_pack_review_approved()`(§1의 검수 Key 11개 전부 APPROVED)를 만족하는 Pack만
   Fail-Closed로 추가한다 — merge 자체는 활성화를 의미하지 않는다.
3. **질문 흐름 구조는 Routing → Anchor 선택 → Seed → Adaptive Tail(최소 4개·최대
   6개) → (후보 소진 시) Anchor Backup 순이다.** `/assessment/next-question`이 이
   Context에 처음 진입하면 `ContextPackRuntime.get_routing_question()`을 먼저 내고,
   학생이 고른 Option으로 Anchor 하나를 확정한 뒤에만 그 Anchor의 Seed를 낸다. 그
   다음부터는 `context_pack_adaptive_planner`가 Evidence Coverage를 보고 Native/
   Shared Direct Probe 후보 중 하나를 고르되, LLM이 꺼져 있거나 재생성까지 실패하면
   (신규 Pack Context는 `allow_base_question_fallback=False`라 Legacy 원본 문구를
   대신 노출하지 않는다) 그 Anchor의 검수된 Backup으로 넘어가고, Backup도 소진되면
   Context가 조기 종료된다.
4. **승인되지 않은 Pack뿐 아니라, 승인된 Pack 안의 개별 Signal도 별도로
   Fail-Closed 게이트를 한 번 더 거친다.** `src/services/trait_signal_review_gate.py`
   가 Seed/Anchor Backup/Native Direct Probe Evidence를 Pack 자체 검수 상태로,
   공용 Adaptive Probe Evidence를 `(blueprint_id, context_id, anchor_id)` 단위
   검수 상태로 각각 다시 확인한다 — 검수가 REVISE/HOLD/TBD로 되돌아가면 이미 쌓인
   Evidence Ledger는 그대로 두되 Career Profile·전공 매칭 같은 Primary 계산에서만
   조용히 제외된다(Ledger 원본은 절대 지우지 않는다).
5. **실제 서비스에서 이 12개가 학생에게 보이려면, 배치 단위로 사람이 직접 검수
   페이지(`src/review_ui/`)에서 각 질문을 APPROVE해야 한다.** Claude나 이 Harness류
   진단 도구가 그 판정을 대신 채우지 않는다 — `data/reviews/context_packs/
   <context_id>_review_status.json`은 Pack이 merge된 시점에 전부 `reviewer_1_status:
   "TBD"`로 시작하고, 실제 사람이 배치 순서대로 검토를 끝내기 전까지는 계속 그
   상태로 남는다.

이 다섯 조건을 `eval/context_pack_matrix_diagnostics.py`(2026-08-24,
`a/contextpack-matrix-eval`)가 임시 Fixture로 직접 검증했다 — 실제 12개 Pack 모두
Routing 1·Anchor 5·Seed 5·Backup 5·검수 Key 11개 구조를 갖췄고, 실제 검수 파일은
전부 TBD이며, Flag OFF와 "Flag ON이지만 미승인" 두 경우 모두 지원 Context가 기존
3개로 그대로 유지됨을 확인했다(`outputs/evaluation/context_pack_matrix_report.md`
참고). Pack을 먼저 만들어 두는 것은 여전히 안전하다 — 위 Fail-Closed 조건들 때문에
merge와 검수 사이에는 아무것도 자동으로 활성화되지 않는다.
