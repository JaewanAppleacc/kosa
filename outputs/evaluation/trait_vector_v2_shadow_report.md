# Trait Vector v2 Shadow Mode 비교 보고서

2026-08-23 Trait Ontology v2(1단계 §11, 1.5단계 §11/§14). 기존 Profile·Matching·Subgraph 결과는
이 보고서 생성 과정에서 전혀 바뀌지 않는다 — Legacy Trait Summary와 v2 Trait
Vector Snapshot을 같은 세션에 대해 병행 계산만 했다.

## 실행 조건

- LLM/LangSmith 비활성(재실행해도 항상 같은 결과가 나오도록 결정론적으로 고정).
- Persona 1~6/8/10은 실제 `/assessment` API(FastAPI TestClient)로 세션을 끝까지
  진행했다 — Seed 3개(Context당 1개)에서만 의도한 선택지를 고르고, 그 뒤
  꼬리질문은 전부 옵션[0]을 고른다.
- Persona 7은 같은 방식으로 Seed 3개만 답하고 중단했다.
- Persona 9는 실제 API로 재현할 수 없어(아래 '1.5단계 수정 사항' 참고) 실제 엔진 함수
  (`detect_explicit_conflicts` 등)에 직접 넣을 Evidence Ledger를 구성했다.

## 1.5단계 수정 사항 — role_id 단독 조회 → 복합 Key + LEGACY_PRIMARY_ADAPTER

1단계는 LLM이 꺼지면 꼬리질문이 `mock_data.tail_question_from_planner_decision()`이
만드는 자리표시자 role_id(`role_{trait}`)를 썼고, 이 값은 Registry에 전혀 등록될
수 없어 **v2 Signal이 세션당 최대 3개(Context별 Seed 답변 1개)에서만 붙었다.**
1.5단계는 `resolve_trait_signals()`가 Registry에 없는 조합이면 legacy
`primary_trait_delta`를 그대로 PRIMARY Signal로 옮기는 LEGACY_PRIMARY_ADAPTER로
넘어가도록 바꿨다 — 그래서 이제 **일반 질문(Conflict Resolution 제외)은 전부 최소
PRIMARY Signal 1개를 얻는다**(아래 '§14 LLM-off Coverage 측정' 참고). 다만
RELATED Signal은 여전히 EXACT_BLUEPRINT(Seed·Backup·Tail Blueprint에 사람이
직접 등록한 Role)에서만 나온다 — LEGACY_PRIMARY_ADAPTER는 근거 없는 RELATED를
추측해서 만들지 않는다(1단계 §16 금지 조항 유지).

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
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:2, change_adaptation:1, collaboration_preference:2, emotional_interpretation:1, immediate_execution:2, information_comparison:2, persistence_completion:1, planning:1, systems_thinking:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:2, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:2, immediate_execution:2, information_comparison:2, persistence_completion:1, planning:2, systems_thinking:1

### Persona 2 — 시각·창의 표현형

media Seed에서 시각적 표현 선택지를 골라 visual_expression + aesthetic_sensitivity RELATED Signal을 관찰한다. Seed 경로만으로는 이 Concept의 원천이 media 하나뿐이라 승격 조건(서로 다른 질문 2개)을 채우지 못하는 걸 그대로 보여주는 사례다(§13 한계 참고).

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): change_adaptation(MODERATE), emotional_interpretation(MODERATE), immediate_execution(MODERATE), pattern_finding(MODERATE), visual_expression(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): change_adaptation(MODERATE, primary_evidence), emotional_interpretation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), pattern_finding(MODERATE, primary_evidence), visual_expression(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), causal_analysis(LIMITED, primary_evidence), collaboration_preference(LIMITED, primary_evidence), planning(LIMITED, primary_evidence), aesthetic_sensitivity(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: aesthetic_sensitivity(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: aesthetic_sensitivity, persistence_completion, systems_thinking
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): aesthetic_sensitivity:1, audience_response_prediction:1, causal_analysis:1, change_adaptation:2, collaboration_preference:1, emotional_interpretation:2, immediate_execution:2, pattern_finding:2, persistence_completion:1, planning:1, systems_thinking:1, visual_expression:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): aesthetic_sensitivity:1, audience_response_prediction:2, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:2, immediate_execution:2, pattern_finding:2, persistence_completion:1, planning:2, systems_thinking:1, visual_expression:2

### Persona 3 — 계획·완수형

school_life Seed에서 계획 수립 선택지를 골라 planning + persistence_completion RELATED Signal을 관찰한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): collaboration_preference(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), opinion_mediation(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): collaboration_preference(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), opinion_mediation(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), causal_analysis(LIMITED, primary_evidence), change_adaptation(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), planning(LIMITED, primary_evidence), detail_orientation(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: detail_orientation(HYPOTHESIS, unconfirmed_related_signal), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: detail_orientation, persistence_completion, systems_thinking
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:1, change_adaptation:1, collaboration_preference:2, detail_orientation:1, emotional_interpretation:1, immediate_execution:2, information_comparison:1, opinion_mediation:2, persistence_completion:1, planning:1, systems_thinking:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:2, causal_analysis:2, change_adaptation:2, collaboration_preference:2, detail_orientation:1, emotional_interpretation:2, immediate_execution:2, information_comparison:2, opinion_mediation:2, persistence_completion:1, planning:2, systems_thinking:1

### Persona 4 — 즉시 실행·변화 적응형

game Seed에서 즉시 실행, school_life Seed에서 변화 대응 선택지를 골라 uncertainty_tolerance/novelty_seeking RELATED Signal을 각각 관찰한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): causal_analysis(STRONG), change_adaptation(MODERATE), collaboration_preference(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), opinion_mediation(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), collaboration_preference(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), opinion_mediation(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), pattern_finding(LIMITED, primary_evidence), novelty_seeking(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: novelty_seeking(HYPOTHESIS, unconfirmed_related_signal), systems_thinking(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: novelty_seeking, systems_thinking, uncertainty_tolerance
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:1, immediate_execution:2, information_comparison:2, novelty_seeking:1, opinion_mediation:2, pattern_finding:1, systems_thinking:1, uncertainty_tolerance:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:2, causal_analysis:3, change_adaptation:2, collaboration_preference:2, emotional_interpretation:2, immediate_execution:2, information_comparison:2, novelty_seeking:1, opinion_mediation:2, pattern_finding:2, systems_thinking:1, uncertainty_tolerance:1

### Persona 5 — 협업·조정형

game Seed에서 협업, school_life Seed에서 의견 조정 선택지를 골라 opinion_expression RELATED Signal을 관찰한다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): emotional_interpretation(STRONG), change_adaptation(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): emotional_interpretation(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), causal_analysis(LIMITED, primary_evidence), collaboration_preference(LIMITED, primary_evidence), opinion_mediation(LIMITED, primary_evidence), opinion_expression(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: opinion_expression(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: opinion_expression
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:1, change_adaptation:2, collaboration_preference:1, emotional_interpretation:2, immediate_execution:2, information_comparison:2, opinion_expression:1, opinion_mediation:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:2, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:3, immediate_execution:2, information_comparison:2, opinion_expression:1, opinion_mediation:2

### Persona 6 — 독립 판단·자기 기준형

independent_judgment/personal_goal_priority는 이번 1단계에서 RELATED Signal을 아예 등록하지 않았다(현재 질문에서 실제 근거를 찾지 못해 억지로 만들지 않았다, §2 원칙) — 이 Persona는 그 두 Trait가 항상 NOT_PROBED로 남는다는 걸 그대로 보여주는 정직한 사례다.

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): audience_response_prediction(STRONG), change_adaptation(MODERATE), collaboration_preference(MODERATE), emotional_interpretation(MODERATE), immediate_execution(MODERATE), information_comparison(MODERATE), planning(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): audience_response_prediction(STRONG, primary_evidence), change_adaptation(MODERATE, primary_evidence), collaboration_preference(MODERATE, primary_evidence), emotional_interpretation(MODERATE, primary_evidence), immediate_execution(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), planning(MODERATE, primary_evidence), causal_analysis(LIMITED, primary_evidence), persistence_completion(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: persistence_completion(HYPOTHESIS, unconfirmed_related_signal), uncertainty_tolerance(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: persistence_completion, uncertainty_tolerance
- RELATED 승격(promoted_related_signal)된 신규 Trait: (없음)
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:2, causal_analysis:1, change_adaptation:2, collaboration_preference:2, emotional_interpretation:2, immediate_execution:2, information_comparison:2, persistence_completion:1, planning:2, uncertainty_tolerance:1
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:3, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:2, immediate_execution:2, information_comparison:2, persistence_completion:1, planning:2, uncertainty_tolerance:1

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
- Frame 다양성(관찰된 것만, trait_id: frame_count): causal_analysis:2, systems_thinking:1

### Persona 8 — Related Signal만 반복된 Persona

systems_thinking은 어떤 Role에서도 PRIMARY로 배정된 적이 없다(신규 12개 Trait는 이번 1단계에서 전부 PRIMARY Role이 없다, §7 한계) — RELATED만 반복 관찰돼 LIMITED로 승격되더라도 STRONG/MODERATE로는 절대 못 올라가는지 확인한다(§9 '한 번의 답변으로 강한 Trait가 되면 안 된다'의 구조적 보장).

- 답변 수: 21
- Legacy 상위 Trait(STRONG/MODERATE): causal_analysis(STRONG), change_adaptation(STRONG), collaboration_preference(MODERATE), information_comparison(MODERATE), opinion_mediation(MODERATE)
- v2 상위 Trait 후보(전체, NOT_PROBED 제외): causal_analysis(STRONG, primary_evidence), change_adaptation(STRONG, primary_evidence), collaboration_preference(MODERATE, primary_evidence), information_comparison(MODERATE, primary_evidence), opinion_mediation(MODERATE, primary_evidence), audience_response_prediction(LIMITED, primary_evidence), emotional_interpretation(LIMITED, primary_evidence), immediate_execution(LIMITED, primary_evidence), systems_thinking(LIMITED, promoted_related_signal), novelty_seeking(HYPOTHESIS, unconfirmed_related_signal)
- v2 신규 Trait 후보만: systems_thinking(LIMITED, promoted_related_signal), novelty_seeking(HYPOTHESIS, unconfirmed_related_signal)
- v2 HYPOTHESIS: novelty_seeking
- RELATED 승격(promoted_related_signal)된 신규 Trait: systems_thinking
- 같은 Trait가 2개 이상 Related Concept로 연결된 사례: (없음)
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:1, immediate_execution:2, information_comparison:2, novelty_seeking:1, opinion_mediation:2, systems_thinking:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:2, causal_analysis:2, change_adaptation:3, collaboration_preference:2, emotional_interpretation:2, immediate_execution:1, information_comparison:2, novelty_seeking:1, opinion_mediation:2, systems_thinking:1

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
- Context 다양성(관찰된 것만, trait_id: context_count): audience_response_prediction:1, causal_analysis:2, change_adaptation:2, collaboration_preference:2, emotional_interpretation:2, immediate_execution:2, information_comparison:2, pattern_finding:2, systems_thinking:2
- Frame 다양성(관찰된 것만, trait_id: frame_count): audience_response_prediction:2, causal_analysis:3, change_adaptation:2, collaboration_preference:3, emotional_interpretation:2, immediate_execution:2, information_comparison:2, pattern_finding:2, systems_thinking:1

## §14 LLM-off Coverage 측정 (실제 완주 세션 1개, 재현 가능)

- 전체 답변 수: 21
- 일반 질문(Conflict Resolution 제외) 수: 21
- EXACT_BLUEPRINT 수: 3
- LEGACY_PRIMARY_ADAPTER 수: 18
- v2 Signal이 비어 있는(signals=[]) 일반 질문 수: 0 (0이어야 완료 조건을 만족한다)
- 관찰된 Trait 수(NOT_PROBED 제외): 10
- Directly Measurable Trait 중 이번 세션에서 실제 관찰된 수: 8
- Related-Only Trait 중 이번 세션에서 실제 관찰된 수: 2
- HYPOTHESIS 수: 1
- 승격된 RELATED(promoted_related_signal) 수: 1
- NOT_PROBED로 남은 Trait 수: 5
- Context 2개 이상에서 관찰된 Trait 수: 5
- Frame 2개 이상에서 관찰된 Trait 수: 8

## §11 LLM-on 실검증 (opt-in, 실제 API Key 존재 시 1회 수동 실행 결과)

`.env`에 `OPENAI_API_KEY`와 `ENABLE_LLM_QUESTION_GENERATION=true`가 설정돼 있어
실제 네트워크 호출로 1회 검증했다(재현성이 필요 없는 opt-in 검증이라 이 스크립트의
기본 실행에는 포함하지 않는다 — 실행할 때마다 실제 비용이 발생한다).

- `generate_tail_question(option_blueprint_id="problem_response_v1", trait_definition=causal_analysis, context=game, frame_id="problem_check")`를
  실제 OpenAI Client로 1회 호출했다.
- `outcome.source == "llm"`(성공), 생성된 질문: "게임을 하다가 예상과 다른 일이 일어났을 때 먼저 무엇을 하나요?"
- 반환된 5개 Role(cause_analysis/strategy_change/direct_trial/external_research/ask_others) 전부 `resolve_trait_signals(question_family_id="tail_blueprint", blueprint_id="problem_response_v1", ...)`에서 `EXACT_BLUEPRINT`로 조회됐다 —
  LLM이 생성한 질문의 Role이 실제로 Signal Registry에 연결되는지 확인됐다.
- 5개 선택지 문장을 사람이 직접 읽고 확인한 결과, 각 선택지가 가리키는 Signal
  Mapping(causal_analysis/change_adaptation/immediate_execution/information_comparison/collaboration_preference)과 의미상 모순이 없었다.
- Quality Gate 재생성 시 내부 Blueprint id 보존 여부와 외부 호출 실패 시 Backup
  전환은 실제 네트워크 호출로 강제 재현하기 어려워(LLM이 의도적으로 형식을 어기게
  만들 수 없고, 네트워크 장애도 임의로 일으킬 수 없다) 결정론적 FakeLLM 테스트로
  검증했다(`tests/test_evidence_ledger_v2_signal.py::LLMOnSignalMappingTest`).

## 종합 판단

- Core Trait 24개 중 Directly Measurable: 12개(기존 12개와 정확히 동일 — 신규 Trait는 이번 단계에서 하나도 승격되지 않았다)
- Related-Only Trait: 7개 aesthetic_sensitivity, detail_orientation, novelty_seeking, opinion_expression, persistence_completion, systems_thinking, uncertainty_tolerance
- Not Probed Trait: 5개 challenge_seeking, creative_ideation, independent_judgment, personal_goal_priority, verbal_expression
- RELATED Signal 승격(LIMITED)이 STRONG/MODERATE로 잘못 해석된 사례는 없다
  (`compute_trait_vector_snapshot_all`이 legacy PRIMARY 판정을 항상 우선한다).
- 동일 Concept·Trait가 같은 답변에서 중복 합산되는 사례는 없었다(Persona 10 —
  서로 다른 답변에서 서로 다른 Concept으로만 연결됨을 확인).
- 지나치게 넓은 Trait Mapping이나 동점 현상은 관찰되지 않았다 — 신규 Trait는
  전부 최대 1개 RELATED Signal만 가진 Role에서 나왔고, 한 Role이 3개 이상의
  RELATED Signal을 가진 경우는 없다(Registry 자체가 이미 그렇게 설계됨).
- 1.5단계 핵심 성과: 일반 질문의 v2 Signal 누락(signals=[])이 0건으로 확인됐다 —
  1단계의 '세션당 최대 3개' 한계가 PRIMARY Signal 관점에서 해소됐다.
