# Trait Vector v2 Shadow Mode 비교 보고서

2026-08-31 Trait Ontology v2(1단계) §11. 기존 Profile·Matching·Subgraph 결과는
이 보고서 생성 과정에서 전혀 바뀌지 않는다 — Legacy Trait Summary와 v2 Trait
Vector Snapshot을 같은 세션에 대해 병행 계산만 했다.

## 실행 조건

- LLM/LangSmith 비활성(재실행해도 항상 같은 결과가 나오도록 결정론적으로 고정).
- Persona 1~6/8/10은 실제 `/assessment` API(FastAPI TestClient)로 세션을 끝까지
  진행했다 — Seed 3개(Context당 1개)에서만 의도한 선택지를 고르고, 그 뒤
  꼬리질문은 전부 옵션[0]을 고른다.
- Persona 7은 같은 방식으로 Seed 3개만 답하고 중단했다.
- Persona 9는 실제 API로 재현할 수 없어(아래 '핵심 한계' 참고) 실제 엔진 함수
  (`detect_explicit_conflicts` 등)에 직접 넣을 Evidence Ledger를 구성했다.

## 핵심 한계 — LLM 미연동 시 v2 Signal 관찰 범위

로컬 `.env`가 `ENABLE_LLM_QUESTION_GENERATION=true`로 설정돼 있어도, 이
스크립트는 재현성을 위해 LLM을 강제로 끈다. LLM이 꺼지면 꼬리질문은
`mock_data.tail_question_from_planner_decision()`이 만드는 자리표시자
role_id(`role_{trait}`)를 쓰는데, 이 값은 `trait_signal_registry.py`
Registry에 전혀 등록돼 있지 않다 — 그래서 **실제 v2 Signal은 세션당 최대
3개(Context별 Seed 답변 1개)에서만 붙는다.** 검토된 15개 Tail Blueprint Role
(`tail_option_blueprints.py`)은 LLM이 실제로 그 Blueprint를 선택해 질문을
생성해야만 서빙된다. 이 보고서의 모든 수치는 이 하한(lower bound) 조건에서
나온 값이다 — LLM을 켜면 세션당 최대 15개까지 v2 Signal 관찰 기회가 늘어날
수 있다(실제 수치는 별도 검증 필요, 이번 1단계 범위 밖).

## Persona별 비교

### Persona 1 — 분석·시스템 사고형

game/media Seed에서 원인 분석 선택지를 골라 causal_analysis를 강화하고, systems_thinking RELATED Signal이 서로 다른 Context 2곳(game/media)에서 겹쳐 관찰되는지 확인한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): causal_analysis(STRONG), collaboration_preference(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(STRONG, primary_evidence), collaboration_preference(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), change_adaptation(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), planning(LIMITED, primary_evidence), systems_thinking(LIMITED, promoted_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: systems_thinking(LIMITED, promoted_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: persistence_completion
- RELATED 승격(promoted_related_signal)된 신규 Trait: systems_thinking
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:0, causal_analysis:2, change_adaptation:0, collaboration_preference:0, emotional_interpretation:0, immediate_execution:0, information_comparison:0, persistence_completion:1, planning:1, systems_thinking:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:0, collaboration_preference:0, emotional_interpretation:0, immediate_execution:0, information_comparison:0, persistence_completion:1, planning:1, systems_thinking:1

### Persona 2 — 시각·창의 표현형

media Seed에서 시각적 표현 선택지를 골라 visual_expression + aesthetic_sensitivity RELATED Signal을 관찰한다. Seed 경로만으로는 이 Concept의 원천이 media 하나뿐이라 승격 조건(서로 다른 질문 2개)을 채우지 못하는 걸 그대로 보여주는 사례다(§13 한계 참고).

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): change_adaptation(MODERATE), emotional_interpretation(MODERATE), immediate_execution(MODERATE), pattern_finding(MODERATE), visual_expression(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): change_adaptation(MODERATE, primary_evidence), emotional_interpretation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), pattern_finding(MODERATE, primary_evidence), visual_expression(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), causal_analysis(LIMITED, primary_evidence), collaboration_preference(LIMITED, primary_evidence), planning(LIMITED, primary_evidence), aesthetic_sensitivity(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: aesthetic_sensitivity(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: aesthetic_sensitivity, persistence_completion, systems_thinking
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): aesthetic_sensitivity:1, audience_response_prediction:0, causal_analysis:0, change_adaptation:0, collaboration_preference:0, emotional_interpretation:0, immediate_execution:0, pattern_finding:1, persistence_completion:1, planning:1, systems_thinking:1, visual_expression:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): aesthetic_sensitivity:1, audience_response_prediction:0, causal_analysis:0, change_adaptation:0, collaboration_preference:0, emotional_interpretation:0, immediate_execution:0, pattern_finding:1, persistence_completion:1, planning:1, systems_thinking:1, visual_expression:1

### Persona 3 — 계획·완수형

school_life Seed에서 계획 수립 선택지를 골라 planning + persistence_completion RELATED Signal을 관찰한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): collaboration_preference(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), opinion_mediation(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): collaboration_preference(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), opinion_mediation(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), causal_analysis(LIMITED, primary_evidence), change_adaptation(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), planning(LIMITED, primary_evidence), detail_orientation(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: detail_orientation(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: detail_orientation, persistence_completion, systems_thinking
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:0, collaboration_preference:0, detail_orientation:1, emotional_interpretation:0, immediate_execution:0, information_comparison:1, opinion_mediation:0, persistence_completion:1, planning:1, systems_thinking:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:0, collaboration_preference:0, detail_orientation:1, emotional_interpretation:0, immediate_execution:0, information_comparison:1, opinion_mediation:0, persistence_completion:1, planning:1, systems_thinking:1

### Persona 4 — 즉시 실행·변화 적응형

game Seed에서 즉시 실행, school_life Seed에서 변화 대응 선택지를 골라 uncertainty_tolerance/novelty_seeking RELATED Signal을 각각 관찰한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): causal_analysis(STRONG), change_adaptation(MODERATE), collaboration_preference(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), opinion_mediation(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), collaboration_preference(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), opinion_mediation(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), pattern_finding(LIMITED, primary_evidence), novelty_seeking(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: novelty_seeking(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: novelty_seeking, systems_thinking, uncertainty_tolerance
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:1, collaboration_preference:0, emotional_interpretation:0, immediate_execution:1, information_comparison:0, novelty_seeking:1, opinion_mediation:0, pattern_finding:0, systems_thinking:1, uncertainty_tolerance:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:1, collaboration_preference:0, emotional_interpretation:0, immediate_execution:1, information_comparison:0, novelty_seeking:1, opinion_mediation:0, pattern_finding:0, systems_thinking:1, uncertainty_tolerance:1

### Persona 5 — 협업·조정형

game Seed에서 협업, school_life Seed에서 의견 조정 선택지를 골라 opinion_expression RELATED Signal을 관찰한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): emotional_interpretation(STRONG), change_adaptation(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): emotional_interpretation(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), causal_analysis(LIMITED, primary_evidence), collaboration_preference(LIMITED, primary_evidence), opinion_mediation(LIMITED, primary_evidence), opinion_expression(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: opinion_expression(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: opinion_expression
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:0, causal_analysis:0, change_adaptation:0, collaboration_preference:1, emotional_interpretation:1, immediate_execution:0, information_comparison:0, opinion_expression:1, opinion_mediation:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:0, causal_analysis:0, change_adaptation:0, collaboration_preference:1, emotional_interpretation:1, immediate_execution:0, information_comparison:0, opinion_expression:1, opinion_mediation:1

### Persona 6 — 독립 판단·자기 기준형

independent_judgment/personal_goal_priority는 이번 1단계에서 RELATED Signal을 아예 등록하지 않았다(현재 질문에서 실제 근거를 찾지 못해 억지로 만들지 않았다, §2 원칙) — 이 Persona는 그 두 Trait가 항상 NOT_PROBED로 남는다는 걸 그대로 보여주는 정직한 사례다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): audience_response_prediction(STRONG), change_adaptation(MODERATE), collaboration_preference(MODERATE), emotional_interpretation(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), planning(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): audience_response_prediction(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), collaboration_preference(MODERATE, primary_evidence), emotional_interpretation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), planning(MODERATE, primary_evidence), causal_analysis(LIMITED, primary_evidence), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: persistence_completion(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: persistence_completion, uncertainty_tolerance
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:0, change_adaptation:0, collaboration_preference:0, emotional_interpretation:0, immediate_execution:1, information_comparison:0, persistence_completion:1, planning:1, uncertainty_tolerance:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:1, causal_analysis:0, change_adaptation:0, collaboration_preference:0, emotional_interpretation:0, immediate_execution:1, information_comparison:0, persistence_completion:1, planning:1, uncertainty_tolerance:1

### Persona 7 — Sparse Evidence Persona

Seed 3개(Context당 1개)만 답하고 중단한 경우 — 대부분의 Trait가 opportunity는 있지만 support_count 부족으로 INSUFFICIENT/HYPOTHESIS에 머무는지 확인한다.

- 답변 수: 3
- Legacy 상위 Trait(STRONG/MODERATE): (STRONG/MODERATE 없음)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(LIMITED, primary_evidence), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: systems_thinking
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): causal_analysis:1, systems_thinking:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): causal_analysis:1, systems_thinking:1

### Persona 8 — Related Signal만 반복된 Persona

systems_thinking은 어떤 Role에서도 PRIMARY로 배정된 적이 없다(신규 12개 Trait는 이번 1단계에서 전부 PRIMARY Role이 없다, §7 한계) — RELATED만 반복 관찰돼 LIMITED로 승격되더라도 STRONG/MODERATE로는 절대 못 올라가는지 확인한다(§9 '한 번의 답변으로 강한 Trait가 되면 안 된다'의 구조적 보장).

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): causal_analysis(STRONG), change_adaptation(STRONG), collaboration_preference(MODERATE), information_comparison(MODERATE), opinion_mediation(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(STRONG, primary_evidence), change_adaptation(STRONG, primary_evidence), collaboration_preference(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), opinion_mediation(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), immediate_execution(LIMITED, primary_evidence), systems_thinking(LIMITED, promoted_related_signal), novelty_seeking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: systems_thinking(LIMITED, promoted_related_signal), novelty_seeking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: novelty_seeking
- RELATED 승격(promoted_related_signal)된 신규 Trait: systems_thinking
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:0, causal_analysis:2, change_adaptation:1, collaboration_preference:0, emotional_interpretation:0, immediate_execution:0, information_comparison:0, novelty_seeking:1, opinion_mediation:0, systems_thinking:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:1, collaboration_preference:0, emotional_interpretation:0, immediate_execution:0, information_comparison:0, novelty_seeking:1, opinion_mediation:0, systems_thinking:1

### Persona 9 — Explicit Conflict Persona

planning_vs_execution Contrast Pair(§12-1)를 frame_id='new_tool'에서 양쪽 다 minimum_evidence_each_side=2로 채운 Evidence Ledger를 직접 구성했다(실제 API로는 재현 불가 — 아래 '남은 한계' 참고). planning/immediate_execution이 CONFLICTING으로 Mask되는지 확인한다.

- 답변 수: 0
- Legacy 상위 Trait(STRONG/MODERATE): (STRONG/MODERATE 없음)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): persistence_completion(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal), immediate_execution(CONFLICTING, explicit_conflict), planning(CONFLICTING, explicit_conflict)
- v2 신규 Trait 후보만: persistence_completion(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: persistence_completion, uncertainty_tolerance
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): immediate_execution:1, persistence_completion:1, planning:1, uncertainty_tolerance:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): immediate_execution:1, persistence_completion:1, planning:1, uncertainty_tolerance:1

### Persona 10 — 동일 Trait가 여러 Related Concept에서 연결되는 Persona

game Seed에서 패턴 인식(pattern_in_structure Concept), media Seed에서 원인 분석(whole_system_view Concept)을 골라 systems_thinking이 서로 다른 2개 Concept을 통해 관찰되는지 확인한다 — 같은 답변에서 중복 합산되지 않는지도 함께 확인한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): causal_analysis(STRONG), collaboration_preference(STRONG), change_adaptation(MODERATE), emotional_interpretation(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), pattern_finding(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(STRONG, primary_evidence), collaboration_preference(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), emotional_interpretation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), pattern_finding(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), systems_thinking(LIMITED, promoted_related_signal)
- v2 신규 Trait 후보만: systems_thinking(LIMITED, promoted_related_signal)
- v2 HYPOTHESIS: (없음)
- RELATED 승격(promoted_related_signal)된 신규 Trait: systems_thinking
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: systems_thinking(['pattern_in_structure', 'whole_system_view'])
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:0, collaboration_preference:1, emotional_interpretation:0, immediate_execution:0, information_comparison:0, pattern_finding:1, systems_thinking:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:0, causal_analysis:1, change_adaptation:0, collaboration_preference:1, emotional_interpretation:0, immediate_execution:0, information_comparison:0, pattern_finding:1, systems_thinking:1

## 종합 판단

- Core Trait 24개 중 Vertical Slice Active로 분류된 것: 19개
  (기존 12개 + 신규 7개: aesthetic_sensitivity, detail_orientation, novelty_seeking, opinion_expression, persistence_completion, systems_thinking, uncertainty_tolerance)
- 신규 12개 Trait 중 이번 1단계에서 전혀 관찰되지 않는 것(PRIMARY Role 자체가 없음): challenge_seeking, creative_ideation, independent_judgment, personal_goal_priority, verbal_expression
- 신규 Trait는 전부 PRIMARY Role이 없다 — RELATED Signal로만 관찰되고, 위
  '핵심 한계' 때문에 LLM 없이는 Seed 3개에서 나온 조합만으로 승격 여부가
  갈린다. Persona 1/10처럼 game+media Seed 조합이 causal_analysis 계열을
  고르면 systems_thinking만 승격되고, 나머지 신규 Trait(aesthetic_sensitivity/
  opinion_expression/persistence_completion/uncertainty_tolerance/
  detail_orientation/novelty_seeking)는 Seed 원천이 Context 1곳뿐이라 이번
  1단계의 Seed-only 관찰로는 HYPOTHESIS를 넘지 못한다.
- RELATED Signal 승격(LIMITED)이 STRONG/MODERATE로 잘못 해석된 사례는 없다
  (`compute_trait_vector_snapshot_all`이 legacy PRIMARY 판정을 항상 우선한다).
- 동일 Concept·Trait가 같은 답변에서 중복 합산되는 사례는 없었다(Persona 10 —
  서로 다른 답변에서 서로 다른 Concept으로만 연결됨을 확인).
- 지나치게 넓은 Trait Mapping이나 동점 현상은 관찰되지 않았다 — 신규 Trait는
  전부 최대 1개 RELATED Signal만 가진 Role에서 나왔고, 한 Role이 3개 이상의
  RELATED Signal을 가진 경우는 없다(Registry 자체가 이미 그렇게 설계됨).
