# Trait Ontology v2 검토 문서 (1단계, DRAFT — 2인 교차검토 전)

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

## 6. Vertical Slice Active Trait 선정 근거 (§7)

`src/data/trait_ontology/vertical_slice_active_traits.py`가 실제 Registry
(`ROLE_ID_TO_TRAIT_SIGNALS`)를 세어 계산한다(손으로 다시 세지 않음). 신규 12개 중
서로 다른 Role(≈서로 다른 질문) 2개 이상에서 RELATED Signal이 관찰되는 것만 Active로
분류한다:

| trait_id | RELATED을 부여하는 서로 다른 Role 수 | Active |
|---|---|---|
| systems_thinking | 6 | ✅ |
| aesthetic_sensitivity | 2 | ✅ |
| detail_orientation | 2 | ✅ |
| novelty_seeking | 2 | ✅ |
| opinion_expression | 2 | ✅ |
| persistence_completion | 2 | ✅ |
| uncertainty_tolerance | 2 | ✅ |
| challenge_seeking | 0 | ❌ |
| creative_ideation | 0 | ❌ |
| independent_judgment | 0 | ❌ |
| personal_goal_priority | 0 | ❌ |
| verbal_expression | 0 | ❌ |

**Vertical Slice Active Trait = 19개**(기존 12개 + 신규 7개). 나머지 신규 5개
(`challenge_seeking`/`creative_ideation`/`independent_judgment`/
`personal_goal_priority`/`verbal_expression`)는 이번 1단계의 기존 질문(Seed 15개 +
Tail Blueprint 15개 Role)만으로는 실제 근거를 찾지 못해 억지로 Mapping하지 않았다
(지시서 §7 "실제로는 관련 Trait가 1~2개뿐인 선택지라면 억지로 3개 이상 만들지
말 것"과 같은 원칙 — 신호 자체가 없으면 만들지 않는다).

## 7. §14 진단 — 질문 수 대비 실제 Trait 관찰 Coverage(LLM 미연동 기준)

`outputs/evaluation/trait_vector_v2_shadow_report.md`의 Persona 1~6/8/10(완주 세션)
실측:

- 세션당 평균 답변 수: 21개(전부 동일 — Vertical Slice 3개 Context의 Adaptive Stop
  Condition이 답변 내용과 무관하게 이 근처에서 항상 멈추기 때문)
- PRIMARY Evidence가 2회 이상인 Trait: 기존 12개 Trait 대부분(Legacy STRONG/MODERATE
  판정을 받은 Trait 기준)
- Context 2개 이상에서 관찰된 신규 Trait: `systems_thinking`뿐(game_seed_01 +
  media_seed_01 조합을 고른 Persona 한정) — 나머지 신규 Trait는 Seed 원천이 Context
  1곳뿐이라 이번 1단계 Seed-only 관찰로는 Context 다양성 1을 넘지 못한다.
- HYPOTHESIS로만 남는 신규 Trait 수: Persona마다 1~3개(어떤 Seed를 골랐는지에 따라
  다름)
- **핵심 한계(중요)**: 이 모든 수치는 LLM을 끈 상태(Mock 꼬리질문, 자리표시자
  role_id)에서 나온 하한값이다 — 실제 검토된 15개 Tail Blueprint Role은 LLM이 실제로
  그 Blueprint를 선택해 질문을 생성해야만 서빙되고, 그래야 세션당 최대 15개까지
  v2 Signal 관찰 기회가 늘어난다. 이번 1단계는 이 조건에서의 결과를 그대로
  보고한다(가짜로 부풀리지 않는다).
- 상위 5개 Trait(causal_analysis/collaboration_preference/immediate_execution/
  information_comparison/emotional_interpretation 등 기존 12개 중심)는 Persona마다
  안정적으로 STRONG/MODERATE로 유지됐다 — 신규 Trait가 끼어들어 기존 순위를
  흔드는 사례는 없었다(Shadow Mode이므로 애초에 Matching에 반영되지 않기도 한다).

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
