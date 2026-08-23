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

Pack이 merge되고 검수(APPROVED)까지 끝나야 `assessment_supported`가 true가 된다
(`ContextPackRegistry.assessment_supported_context_ids()`, Fail-Closed). 배치 순서
(`src/services/context_pack_registry.py::CONTEXT_ACTIVATION_BATCHES`):

- 1차: business, science, sports
- 2차: making, volunteer, writing, travel
- 3차: art_design, cooking, fashion_beauty, history_humanities, law_politics

**2.7단계 시점 한계**: `assessment_supported_context_ids()`는 준비돼 있지만 아직
`main.py`의 실제 질문 흐름 게이트(`/assessment/context-select`,
`/assessment/context-confirm`, Context Vector/Trait Coverage Matrix 기반 Contrast
선택)에는 배선되지 않았다 — 그 게이트들은 `VERTICAL_SLICE_CONTEXT_IDS`(3개 고정)를
그대로 쓴다. 새 Context가 실제로 서빙되려면 Context Vector·Trait Coverage Matrix
확장(A 소유)이 먼저 필요하다. Pack을 먼저 만들어 두는 것은 안전하다 — Registry가
Fail-Closed이므로 Pack이 있어도 검수 전에는 무엇도 자동으로 활성화되지 않는다.
