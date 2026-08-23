# ContextPack Matrix Diagnostics — 12 Context × 5 Anchor

진단 전용 보고서다 — 이 실행에서 어떤 ContextPack·Shared Probe도 실제로 APPROVE되지 않았다(모든 승인은 `tempfile` 임시 경로에서만 이뤄졌다). 질문 원문·학생 답변 원문은 담지 않는다.

## 1. 감사 요약

- 활성화 배치 정본: {'1': ['business', 'science', 'sports'], '2': ['making', 'travel', 'volunteer', 'writing'], '3': ['art_design', 'cooking', 'fashion_beauty', 'history_humanities', 'law_politics']}
- 발견된 Context Pack: ['art_design', 'business', 'cooking', 'fashion_beauty', 'history_humanities', 'law_politics', 'making', 'science', 'sports', 'travel', 'volunteer', 'writing'] (12개)
- discovery_errors: (없음)
- ontology_errors: (없음)
- Flag OFF 지원 Context: ['game', 'media', 'school_life'] (기존 3개와 일치: True)
- Flag ON이지만 실제 검수 파일이 전부 TBD일 때 지원 Context: ['game', 'media', 'school_life'] (기존 3개와 일치: True)
- Shared Probe Blueprint 개수: 14

| context_id | 발견 | Routing | Anchor | Seed | Backup | 검수 Key | 실제 검수 전부 TBD |
|---|---|---|---|---|---|---|---|
| art_design | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| business | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| cooking | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| fashion_beauty | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| history_humanities | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| law_politics | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| making | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| science | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| sports | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| travel | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| volunteer | 예 | 1 | 5 | 5 | 5 | 11 | 예 |
| writing | 예 | 1 | 5 | 5 | 5 | 11 | 예 |

## 2. Fail-Closed 직접 검증 (임시 Fixture)

- 대상 Context: `business`
- 미승인 Pack이 assessment_supported에서 제외됨: True
- 미승인 Pack Context 선택이 422로 거부됨: True (error_code=VALIDATION_ERROR)
- 미승인 Signal이 Review Gate에서 제외됨: True
- 미승인 Anchor의 Shared Probe가 후보에서 제외됨: True
- 승인된 Anchor의 Shared Probe는 후보에 포함됨: True
- 완전 승인 후 assessment_supported에 포함됨(대조군): True

## 3. 60개 조합 요약

**4개 항목은 서로 배타적인 결과 분류다** — "정상 종료"는 Runtime 흐름(Routing→Anchor→Seed→Backup Fallback→Context 종료)뿐 아니라 후속 Major Matching까지 최소 기준을 채운 경우만 센다. "Evidence 부족"은 Runtime 흐름 자체는 끝까지 정상이었지만(routing_ok/seed_ok 등 전부 정상) 단일 Context 답변 몇 개만으로는 `/majors`의 최소 사용 가능 Trait/Vector Group 기준을 못 채운 경우다 — 이는 결함이 아니라 설계상 예상된 결과다(지시서 §4 "모든 Context–Anchor 조합이 충분한 Evidence를 만들 필요는 없다").

- 총 조합: 60
- 정상 종료: 0
- Evidence 부족(정상 결과로 취급): 60
- Fail-Closed로 분류: 0
- 실제 오류: 0
- Legacy/타 Context 질문 누출: 0
- Anchor 불일치: 0
- 승인되지 않은 Signal 반영: 0
- 무한 루프·상한 초과 발생: False

## 4. 조합별 상세

| context_id | anchor_id | routing | seed | adaptive | shared | backup | no_signal | evidence_traits | profile | major | dept | subject | subgraph | 상태 | failure |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| business | idea_shaping | True | True | 0 | 0 | True | 0 | collaboration_preference,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| business | feedback_reading | True | True | 0 | 0 | True | 0 | audience_response_prediction,opinion_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| business | resource_budgeting | True | True | 0 | 0 | True | 0 | independent_judgment,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| business | plan_decision | True | True | 0 | 0 | True | 0 | change_adaptation,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| business | team_role_share | True | True | 0 | 0 | True | 0 | change_adaptation,opinion_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| science | cause_exploring | True | True | 0 | 0 | True | 0 | causal_analysis,detail_orientation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| science | data_comparing | True | True | 0 | 0 | True | 1 | information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| science | hypothesis_testing | True | True | 0 | 0 | True | 0 | change_adaptation,independent_judgment | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| science | observing | True | True | 0 | 0 | True | 0 | causal_analysis,detail_orientation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| science | uncertain_result | True | True | 0 | 0 | True | 0 | detail_orientation,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| sports | spectating_analysis | True | True | 0 | 0 | True | 0 | causal_analysis,pattern_finding | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| sports | record_improvement | True | True | 0 | 0 | True | 0 | persistence_completion,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| sports | strategy_tactics | True | True | 0 | 0 | True | 0 | change_adaptation,systems_thinking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| sports | individual_training | True | True | 0 | 0 | True | 0 | independent_judgment,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| sports | team_situation | True | True | 0 | 0 | True | 0 | opinion_expression,opinion_mediation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| making | assembling | True | True | 0 | 0 | True | 0 | causal_analysis,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| making | tool_using | True | True | 0 | 0 | True | 0 | immediate_execution,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| making | error_fixing | True | True | 0 | 0 | True | 1 | causal_analysis | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| making | improving | True | True | 0 | 0 | True | 0 | immediate_execution,persistence_completion | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| making | user_perspective | True | True | 0 | 0 | True | 0 | audience_response_prediction,pattern_finding | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| travel | unfamiliar_place | True | True | 0 | 0 | True | 0 | immediate_execution,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| travel | culture_info | True | True | 0 | 0 | True | 0 | causal_analysis,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| travel | plan_change | True | True | 0 | 0 | True | 0 | change_adaptation,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| travel | companion_opinion | True | True | 0 | 0 | True | 0 | emotional_interpretation,opinion_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| travel | route_decision | True | True | 0 | 0 | True | 0 | information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| volunteer | help_method | True | True | 0 | 0 | True | 0 | causal_analysis,persistence_completion | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| volunteer | resource_allocation | True | True | 0 | 0 | True | 0 | planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| volunteer | field_change | True | True | 0 | 0 | True | 0 | causal_analysis,change_adaptation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| volunteer | opinion_difference | True | True | 0 | 0 | True | 0 | creative_ideation,opinion_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| volunteer | cause_selection | True | True | 0 | 0 | True | 0 | information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| writing | story_interpretation | True | True | 0 | 0 | True | 0 | causal_analysis,creative_ideation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| writing | information_organizing | True | True | 0 | 0 | True | 0 | persistence_completion,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| writing | expression_style | True | True | 0 | 0 | True | 1 | novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| writing | reader_reaction | True | True | 0 | 0 | True | 0 | audience_response_prediction,change_adaptation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| writing | source_comparison | True | True | 0 | 0 | True | 0 | information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| art_design | visual_appreciation | True | True | 0 | 0 | True | 0 | aesthetic_sensitivity,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| art_design | direct_creation | True | True | 0 | 0 | True | 0 | persistence_completion,visual_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| art_design | revision_feedback | True | True | 0 | 0 | True | 0 | change_adaptation,opinion_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| art_design | planning_composition | True | True | 0 | 0 | True | 0 | planning,systems_thinking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| art_design | tool_material_choice | True | True | 0 | 0 | True | 0 | information_comparison,tool_utilization | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| cooking | food_choice | True | True | 0 | 0 | True | 0 | information_comparison,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| cooking | recipe_understanding | True | True | 0 | 0 | True | 0 | causal_analysis,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| cooking | ingredient_substitution | True | True | 0 | 0 | True | 0 | creative_ideation,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| cooking | process_planning | True | True | 0 | 0 | True | 0 | persistence_completion,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| cooking | taste_adjustment | True | True | 0 | 0 | True | 0 | detail_orientation,independent_judgment | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| fashion_beauty | style_combination | True | True | 0 | 0 | True | 0 | creative_ideation,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| fashion_beauty | info_comparison | True | True | 0 | 0 | True | 0 | information_comparison,novelty_seeking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| fashion_beauty | situational_fit | True | True | 0 | 0 | True | 0 | change_adaptation,planning | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| fashion_beauty | expression_choice | True | True | 0 | 0 | True | 0 | opinion_expression,visual_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| fashion_beauty | trend_adaptation | True | True | 0 | 0 | True | 0 | novelty_seeking,personal_goal_priority | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| history_humanities | conflicting_records | True | True | 0 | 0 | True | 0 | causal_analysis,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| history_humanities | figure_choice | True | True | 0 | 0 | True | 0 | emotional_interpretation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| history_humanities | historical_context | True | True | 0 | 0 | True | 0 | information_comparison,systems_thinking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| history_humanities | value_conflict | True | True | 0 | 0 | True | 0 | causal_analysis,opinion_mediation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| history_humanities | cause_effect_chain | True | True | 0 | 0 | True | 0 | causal_analysis,systems_thinking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| law_politics | rule_conflict | True | True | 0 | 0 | True | 0 | causal_analysis,opinion_expression | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| law_politics | source_reading | True | True | 0 | 0 | True | 0 | causal_analysis,information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| law_politics | differing_claims | True | True | 0 | 0 | True | 0 | information_comparison | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| law_politics | public_decision | True | True | 0 | 0 | True | 0 | opinion_expression,systems_thinking | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |
| law_politics | rule_making | True | True | 0 | 0 | True | 0 | causal_analysis,change_adaptation | OK | INSUFFICIENT_EVIDENCE | SKIPPED_NO_MAJOR | SKIPPED_NO_MAJOR | OK | EVIDENCE_INSUFFICIENT | - |

## 5. 격리·안전성 위반이 있는 조합

없음 — 60개 조합 전부 Context/Anchor 격리, Routing Evidence 미반영, Review Gate 적용, 멱등 재현, Context 전환이 정상이었다.

## 6. 보조 검증 — 결정론적 로컬 Stub LLM (실제 LLM·네트워크 호출 아님)

위 §3의 60개 조합은 실제 `_llm_client=None`(LLM OFF)으로 실행했다 — `generate_v2_direct_probe_question()`이 Pack Context에서는 `allow_base_question_fallback=False`로 호출되므로, LLM이 없으면 Adaptive Tail 첫 시도에서 곧바로 그 Anchor의 (유일한) Backup으로 넘어가고, Backup까지 소진되면 `STOP_GENERATION_EXHAUSTED`로 Context가 끝난다 — 이게 버그가 아니라 "LLM OFF에서도 결정론적으로 종료한다"는 설계 그대로다. 그 결과 §3에서는 `adaptive_question_count`/`shared_probe_count`/`native_probe_count`가 항상 0이다.
그래서 이 §6은 순수 로컬 객체 `DeterministicStubLLMClient`(네트워크 호출 없음, Blueprint의 Role 순서만 그대로 유지하는 placeholder 문장 반환)로 12개 Context 각각의 Anchor 1개씩(총 12개 조합)만 추가로 실행해, Adaptive Tail이 실제로 여러 번 진행될 때도 격리·Review Gate가 유지되는지 보조로 확인한다.

| context_id | anchor_id | adaptive_candidate_pool | adaptive_served | shared | native | backup | no_signal | evidence_traits | 격리 위반 |
|---|---|---|---|---|---|---|---|---|---|
| business | idea_shaping | 14 | 6 | 6 | 0 | False | 2 | independent_judgment,information_comparison,novelty_seeking,opinion_mediation,pattern_finding | 없음 |
| science | cause_exploring | 14 | 6 | 6 | 0 | False | 2 | causal_analysis,independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| sports | spectating_analysis | 14 | 6 | 6 | 0 | False | 2 | independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| making | assembling | 14 | 6 | 6 | 0 | False | 2 | independent_judgment,information_comparison,opinion_mediation,pattern_finding,planning | 없음 |
| travel | unfamiliar_place | 14 | 6 | 6 | 0 | False | 2 | immediate_execution,independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| volunteer | help_method | 14 | 6 | 6 | 0 | False | 2 | causal_analysis,independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| writing | story_interpretation | 14 | 6 | 6 | 0 | False | 2 | causal_analysis,independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| art_design | visual_appreciation | 14 | 6 | 6 | 0 | False | 2 | aesthetic_sensitivity,independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| cooking | food_choice | 14 | 6 | 6 | 0 | False | 2 | independent_judgment,information_comparison,novelty_seeking,opinion_mediation,pattern_finding | 없음 |
| fashion_beauty | style_combination | 14 | 6 | 6 | 0 | False | 2 | independent_judgment,information_comparison,novelty_seeking,opinion_mediation,pattern_finding | 없음 |
| history_humanities | conflicting_records | 14 | 6 | 6 | 0 | False | 2 | independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
| law_politics | rule_conflict | 14 | 6 | 6 | 0 | False | 2 | causal_analysis,independent_judgment,information_comparison,opinion_mediation,pattern_finding | 없음 |
