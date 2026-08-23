# Trait Ontology v2 검토 문서 (1단계 + 1.5단계, DRAFT — 2인 교차검토 전)

`data/master/trait_ontology_v2.jsonl`(24개)의 정본은 이 문서가 아니라 JSONL이다 —
이 문서는 신규 12개 Trait를 왜 이렇게 정의했는지, 어디까지 근거가 있는지, 아직 검토가
필요한 부분이 뭔지를 사람이 읽을 수 있게 남긴 검토 자료다.

## 1. 기존 12개는 그대로 유지

`src/data/trait_ontology/vertical_slice_traits.py`(`VERTICAL_SLICE_TRAITS`)의 ID·정의·
행동 지표는 이번 1단계에서 하나도 바꾸지 않았다. `career_build_trait_ontology_v2.py`는
이 12개를 그대로 옮기고 `review_status="team_reviewed"`(2026-08-20 확정 상태)만
채운다 — `tests/test_trait_ontology_v2.py::CoreTraitCountTest.
test_existing_trait_fields_unchanged_in_v2`가 이 사실을 회귀 테스트로 고정한다.

## 2. 신규 12개 Trait 요약

| trait_id | 분류 | grounding_type | 근거 |
|---|---|---|---|
| systems_thinking | 사고·분석 | ONET_PARTIAL | O*NET Skill 'Systems Analysis'(2.B.5.a) 항목명 확인 |
| creative_ideation | 창의·표현 | TEAM_DEFINED | (아래 "발견된 긴장" 참고) |
| verbal_expression | 창의·표현 | RIASEC_REFERENCE | Holland 'Artistic'(약함, 항목 단위 아님) |
| aesthetic_sensitivity | 창의·표현 | RIASEC_REFERENCE | Holland 'Artistic'(약함, 항목 단위 아님) |
| persistence_completion | 실행·관리 | ONET_PARTIAL | O*NET Work Style 'Persistence' 항목명 확인 |
| detail_orientation | 실행·관리 | ONET_PARTIAL | O*NET Work Style 'Attention to Detail' 항목명 확인 |
| novelty_seeking | 변화·도전 | TEAM_DEFINED | 공식 대응 항목 없음 |
| uncertainty_tolerance | 변화·도전 | TEAM_DEFINED | 'Stress Tolerance'와 인접하나 범위가 달라 팀 정의 유지 |
| challenge_seeking | 변화·도전 | ONET_PARTIAL | O*NET Work Style 'Achievement/Effort' 항목명 확인 |
| independent_judgment | 자율·의사결정 | ONET_PARTIAL | O*NET Work Style 'Independence' 항목명 확인 |
| opinion_expression | 자율·의사결정 | TEAM_DEFINED | 공식 대응 항목 없음("주장성" 자체를 다루는 항목 없음) |
| personal_goal_priority | 자율·의사결정 | TEAM_DEFINED | 공식 대응 항목 없음("이기적임"의 중립적 표현, §2 원칙 3) |

어떤 신규 Trait도 `ONET_STRONG`으로 표기하지 않았다(§2 원칙 5·6 — 부분적으로만
연결되는 항목을 검증된 심리 척도처럼 과장하지 않는다).

**Grounding 수치 재계산(1.5단계 §13, 정본 데이터에서 직접 계산 — 하드코딩하지 않음):**
`./.venv/bin/python -c "from src.services.trait_ontology_v2 import load_trait_ontology_v2 as f; from collections import Counter; d=[t for t in f() if t.review_status=='draft']; print(Counter(t.grounding_type for t in d))"`
결과 `ONET_PARTIAL=5, TEAM_DEFINED=5, RIASEC_REFERENCE=2`(합계 12) — 위 표와 일치한다.

## 3. 발견된 긴장(자동으로 고치지 않고 그대로 보고함, §2 원칙 7)

**`creative_ideation` vs `visual_expression`의 O*NET 근거 중복 위험.** 기존
`visual_expression`은 O*NET GWA 'Thinking Creatively'(4.A.2.b.2, "Developing,
designing, or creating new applications, ideas, relationships, systems, or
products, including artistic contributions.")를 `ONET_STRONG` 근거로 이미 인용하고
있다. `creative_ideation`(새로운 아이디어를 매체와 무관하게 떠올리는 경향)의 정의도
넓게 잡으면 같은 항목을 가리키게 된다. 이번 1단계에서는 `creative_ideation`을
"매체 무관 발상 자체"로 좁혀 같은 항목을 `ONET_STRONG`으로 중복 주장하지 않고
`TEAM_DEFINED`로 남겼다 — 이 구분(매체 유무)이 실제로 유효하고 충분히 다른
Trait인지, 아니면 `visual_expression`의 하위 개념으로 흡수돼야 하는지는 2인 검토
대상이다.

## 4. `personal_goal_priority` 중립적 정의 확인

지시서 §2 원칙 3 그대로: "공동 목표보다 개인 목표·자율적 기준을 상대적으로
우선하는 경향"으로만 정의했다. "이기적", "배려하지 않음" 같은 부정적 성격 단정
문구는 정의·행동 지표 어디에도 넣지 않았다(`tests/test_trait_ontology_v2.py::
TraitDefinitionFieldsTest.test_personal_goal_priority_definition_is_neutral_not_selfish_label`
로 회귀 테스트함).

## 5. Related Concept 8개 (`data/master/related_concepts_v2.jsonl`)

30~50개를 억지로 채우지 않고, 현재 3개 Context·기존 검토된 질문(Seed 15개 + Tail
Blueprint 15개 Role)에서 실제 근거를 찾을 수 있는 것만 정의했다:

| concept_id | PRIMARY Trait | SECONDARY Trait |
|---|---|---|
| whole_system_view | systems_thinking | causal_analysis |
| pattern_in_structure | systems_thinking | pattern_finding |
| visual_aesthetic_response | aesthetic_sensitivity | visual_expression |
| assertive_mediation | opinion_expression | opinion_mediation |
| plan_through_to_completion | persistence_completion | planning |
| proceeding_without_certainty | uncertainty_tolerance | immediate_execution |
| comparing_details_across_sources | detail_orientation | information_comparison |
| trying_new_approach_on_own | novelty_seeking | change_adaptation |

`systems_thinking`은 서로 다른 2개 Concept(`whole_system_view`/`pattern_in_structure`)
에서 연결된다 — 같은 Trait가 여러 Concept과 연결될 수 있다는 지시서 §3 규칙의 실제
사례다.

## 6. Active Trait 산정 — 1.5단계에서 전면 재설계됨 (§7)

**1단계 방식은 폐기했다.** `vertical_slice_active_traits.py`(role_id 개수만 세는
`VERTICAL_SLICE_ACTIVE_TRAIT_IDS`)는 "서로 다른 role_id 2개 ≈ 서로 다른 Frame·Context
2개"라는 성립하지 않는 가정을 썼다 — 파일 자체를 삭제하고
`src/data/trait_ontology/trait_probe_capabilities_v2.py`로 교체했다. 자세한 설계
이유·완료 보고는 1.5단계 완료 보고 §1~§10을 참고. 새 분류(실제 Blueprint·Context·
Frame을 각각 독립적으로 계산):

| 분류 | 개수 | Trait |
|---|---|---|
| `LEGACY_RUNTIME_ACTIVE_TRAIT_IDS`(Planner가 실제로 쓰는 유일한 집합) | 12 | 기존 12개와 정확히 동일 |
| `DIRECTLY_MEASURABLE_TRAIT_IDS`(v2 진단 전용) | 12 | 기존 12개와 정확히 동일(신규 0개) |
| `RELATED_ONLY_TRAIT_IDS` | 7 | aesthetic_sensitivity, detail_orientation, novelty_seeking, opinion_expression, persistence_completion, systems_thinking, uncertainty_tolerance |
| `NOT_PROBED_TRAIT_IDS` | 5 | challenge_seeking, creative_ideation, independent_judgment, personal_goal_priority, verbal_expression |

`DIRECTLY_MEASURABLE_TRAIT_IDS`가 신규 Trait를 하나도 포함하지 않는 이유: 신규
12개는 Registry 어디에도 PRIMARY로 등록돼 있지 않다(전부 RELATED뿐이거나 아예 없음)
— PRIMARY가 없으면 애초에 "직접 확인 가능"으로 분류하지 않는다(§7 정의 자체가
PRIMARY 존재를 전제).

## 7. §14 진단 — 질문 수 대비 실제 Trait 관찰 Coverage(LLM 미연동 기준, 1.5단계 재측정)

`outputs/evaluation/trait_vector_v2_shadow_report.md`의 "§14 LLM-off Coverage 측정"
섹션(완주 세션 1개 실측, 재현 가능)에서 그대로 옮긴 값:

- 전체 답변 수: 21, 일반 질문 수: 21
- EXACT_BLUEPRINT 3 / LEGACY_PRIMARY_ADAPTER 18 (v2 Signal이 비어 있는 질문: 0 —
  1.5단계 완료 조건 충족)
- 관찰된 Trait 수(NOT_PROBED 제외): 10 — Directly Measurable 8개, Related-Only 2개
- HYPOTHESIS 1개, 승격된 RELATED 1개, Context 2개 이상 관찰 5개, Frame 2개 이상
  관찰 8개
- 상위 Trait(causal_analysis/collaboration_preference/immediate_execution 등 기존
  12개 중심)는 Persona마다 안정적으로 STRONG/MODERATE로 유지됐다 — 신규 Trait가
  끼어들어 기존 순위를 흔드는 사례는 없었다(Shadow Mode이므로 애초에 Matching에
  반영되지 않기도 한다).

1단계의 "세션당 최대 3개(Seed만)" 한계는 **PRIMARY Signal 관점에서 해소됐다** —
LEGACY_PRIMARY_ADAPTER가 모든 일반 질문에 최소 PRIMARY 1개를 보장한다. 다만 RELATED
Signal(신규 Trait 승격의 유일한 경로)은 여전히 EXACT_BLUEPRINT(Seed·Backup·Tail
Blueprint 등록분)에서만 나온다 — 이 부분은 LLM을 켜서 실제 Tail Blueprint Role을
더 많이 서빙해야 개선된다(1.5단계 완료 보고 §14/§15 참고).

## 8. Major/Subject Mapping — 이번 단계에서 변경 없음

지시서 §12 원칙대로, 신규 12개 Trait에 대한 학과·과목 등급(EVIDENCED/UNMAPPED/
REVIEW_REQUIRED)을 이번 1단계에서 전혀 추가하지 않았다 — "필요하다면"이라는
표현이 명시적 요구가 아니라 선택 사항이라고 판단했고, 검증되지 않은 v2 Trait를
기존 정본 Mapping 파일(`data/master/major_trait_mapping_evidence.jsonl`/
`subject_trait_mapping_evidence.jsonl`)에 UNMAPPED Stub만이라도 섞으면 "왜 이
Trait만 먼저 등록됐는가"라는 불필요한 우선순위 오해를 만들 수 있다고 봐서
보류했다. v2가 정식 전환되는 2단계에서 Major/Subject Mapping 확장을 별도로 진행하는
것을 권장한다.

## 9. Subgraph 확장 가능성 — 설계만, 코드는 미수정

지시서 §13대로 이번 단계에서 `SubgraphResponse`/`SubgraphNode`/`SubgraphEdge`
Schema나 `KnowledgeSubgraphService`는 전혀 건드리지 않았다. 내부적으로는 다음 구조가
기존 Schema 확장만으로 표현 가능하다고 판단한다(코드로 만들지는 않음):

```text
Student --HAS_TRAIT--> CoreTrait --EXPRESSED_AS--> RelatedConcept
```

- `CoreTrait`는 기존 `NodeType`에 추가할 수 있는 이름 후보이고(현재 `Trait`와
  이름이 겹치므로 실제로는 기존 `Trait` NodeType을 그대로 재사용하는 편이 더
  안전해 보인다 — 새 이름을 만들 필요가 없을 수 있다는 뜻).
- `RelatedConcept`는 이미 `src/schemas/graph.py`의 `NodeType` Literal에 정의돼
  있다(2026-08-28 19차 이전부터 존재 — 이번에 추가한 게 아니다).
- `EXPRESSED_AS`는 새 `RelationType` 값이 필요하다(현재 Literal에 없음).
- Related Concept Node는 동일 Concept이 여러 Trait와 연결돼도 중복 생성하지 않아야
  한다(Registry의 `concept_id`를 Node id로 그대로 쓰면 자연히 dedup된다).
- Matching Edge(`RELATED_TO` 등)는 계속 Core Trait 기준이어야 하고, Concept 관련
  Edge(`EXPRESSED_AS`)는 순수 설명용으로만 써야 한다.

실제 구현은 v2가 정식 전환된 뒤, A/B 역할 분담(A=API, B=시각화)이 재확인된 별도
라운드에서 진행하는 것을 권장한다.

## 10. 1.5단계 요약 (2026-08-23, 구조적 문제 수정)

1단계에서 발견된 7개 문제를 고쳤다 — 상세 내용은 1.5단계 완료 보고를 참고:

1. Registry를 role_id 단독 조회에서 `(question_family_id, blueprint_id, role_id)`
   복합 Key 조회로 교체(`src/schemas/trait_signal.py::TraitSignalRegistryKey`,
   `src/services/trait_signal_registry.py`).
2. `resolve_trait_signals()`를 새로 도입 — Registry에 없는 정상 질문은
   LEGACY_PRIMARY_ADAPTER로 최소 PRIMARY Signal 1개를 항상 보장(더 이상 signals=[]로
   조용히 끝나지 않음). Backup Question 6개(30개 Role)를 Registry에 새로 등록.
3. Active Trait 산정을 `TraitProbeCapability` 기반으로 재설계(§6).
4. `compute_trait_vector_snapshot_all()`을 `/profile` Handler에 실제로 연결
   (`src/services/trait_vector_shadow_repository.py`, Fail-Open).
5. 미래 날짜(2026-08-31) 오기를 오늘 날짜(2026-08-23)로 전부 수정.
6. `TraitSignal`을 `frozen=True`로 고정하고 모든 v2 mutable 기본값을
   `Field(default_factory=list)`로 교체, Registry 반환값은 `model_copy(deep=True)`로
   방어 복사.
7. 신규 RELATED-only Trait 7개가 "Active"로 오분류되지 않도록 `RELATED_ONLY_TRAIT_IDS`
   로 명시적으로 분리.

Major/Subject Mapping·신규 Trait 직접 질문 서빙·Planner 24개 Trait 전환은 이번
1.5단계에서도 하지 않았다(범위 밖 — 1단계와 동일한 보류 사유).
