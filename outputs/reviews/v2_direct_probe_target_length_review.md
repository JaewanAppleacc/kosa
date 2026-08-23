# V2 Direct Probe Target Option 길이 이상치 검토

2026-08-23 Trait Ontology v2(2.3단계) §3. 2.2단계 LLM 품질 평가 보고서가 발견한
"Target 길이 이상치 4건"(실제 LLM 생성 문구 기준, Sample마다 문구가 달라 매번 다를 수
있음)을 계기로, **정적 base_question 기준**으로 다시 전수 확인했다. 그 결과 2.2단계에서
사회적 바람직성 완화를 위해 Trade-off 문구를 추가한 6개 Target Option 중 5개, 그리고
Trade-off와 무관하게 원래부터 길었던 2개(systems_thinking 2개, creative_ideation_game_v1
1개 — 일부 중복)를 포함해 총 7개 Blueprint가 `src/engines/v2_direct_probe_quality_checks.py`의
"Target Option이 다른 선택지보다 지나치게 김(margin=10자)" 기준에 걸렸다.

## 재검토 관점

- 목표 Trait 선택지만 지나치게 구체적이거나 길지 않은가
- 목표 선택지가 가장 성숙하거나 바람직한 답처럼 보이지 않는가
- 다른 선택지보다 이유·결과·정당화가 더 많이 포함되지 않았는가
- 선택지 길이 자체가 목표 선택지를 추측하게 만들지 않는가
- 수정 후 기존 PRIMARY 의미가 유지되는가

## 수정 내역

모두 "의미를 유지하면서 자연스럽게 균형을 맞출 수 있는" 경우로 판단해 문구를
수정했다(임의로 잘라내지 않고, 핵심 행동 표현은 그대로 두고 부수적인 수식어·중복
표현만 정리했다). 2.2단계에서 추가한 Trade-off 문구(사회적 바람직성 완화 목적)는
완전히 제거하지 않고 더 간결한 형태로 남겼다 — Trade-off를 아예 없애면 2.2단계에서
고친 문제(무조건 좋아 보이는 답)가 되돌아온다.

| blueprint_id | role_id | 연결 Trait | 수정 전 (길이) | 수정 후 (길이) | 다른 선택지 최대 길이 | 수정 이유 |
|---|---|---|---|---|---|---|
| systems_thinking_game_v1 | st_ripple_check | systems_thinking | 이게 다른 아이템이나 전략에 어떤 영향을 주는지 같이 살펴본다 (34) | 다른 아이템이나 전략에 어떤 영향을 주는지 살펴본다 (28) | 21 | "이게"/"같이"는 의미에 기여하지 않는 군더더기 — 삭제해도 "요소 간 영향 관계를 살펴본다"는 핵심 행동은 그대로다. |
| systems_thinking_school_life_v1 | st_map_impact | systems_thinking | 이 변화가 다른 사람의 역할과 어떻게 서로 얽혀 영향을 주는지 짚어본다 (39) | 이 변화가 다른 역할과 얽혀 영향을 주는지 짚어본다 (28) | 21 | "사람의"/"서로"/"어떻게"를 정리했다. "얽혀"는 그대로 남겨 causal_analysis·planning과 구분되는 관계망(systems_thinking) 의미를 지켰다. |
| detail_orientation_school_life_v1 | do_check_conditions | detail_orientation | 시간이 촉박해도 제출 조건을 하나하나 놓치지 않았는지 세세히 확인한다 (38, 2.2단계 Trade-off 추가분) | 촉박해도 조건을 하나하나 놓치지 않는지 확인한다 (26) | 19 | "시간이"/"제출"/"세세히"는 문맥상 이미 전달되는 중복 표현이었다. "하나하나 놓치지 않는지"(세부 정확성의 핵심)와 "촉박해도"(Trade-off)는 유지했다. |
| persistence_completion_game_v1 | pc_keep_going | persistence_completion | 결과가 잘 안 나오고 다른 목표를 시작할 시간이 늦어져도, 지금 목표는 그대로 두고 끝까지 시도를 이어간다 (59, 2.2단계 Trade-off 추가분) | 잘 안 나와도 다른 목표로 넘어가지 않고 끝까지 이어간다 (31) | 28 | 2.2단계에 추가한 Trade-off 절("다른 목표를 시작할 시간이 늦어져도")이 너무 장황했다 — "다른 목표로 넘어가지 않고"로 같은 기회비용을 더 짧게 표현했다. "같은 목표를 유지한 채 계속한다"(방법 변경이 아님, 2.1단계에서 확정한 핵심 구분)는 그대로다. |
| persistence_completion_school_life_v1 | pc_finish_through | persistence_completion | 다른 일에 쓸 시간이 줄어들어도, 지루한 과제를 끝까지 마무리하는 데 가장 오래 매달린다 (49, 2.2단계 Trade-off 추가분) | 시간이 걸려도 과제를 끝까지 마무리하는 데 가장 오래 매달린다 (34) | 27 | Trade-off 절을 "시간이 걸려도"로 압축했다. "끝까지 마무리하는 데 가장 오래 매달린다"(핵심 행동)는 그대로다. |
| opinion_expression_media_v1 | oe_state_view | opinion_expression | 분위기가 어색해질 수 있어도 내 생각을 먼저 분명하게 말한다 (33, 2.2단계 Trade-off 추가분) | 분위기가 어색해져도 내 생각을 먼저 분명하게 말한다 (28) | 22 | "질 수 있어도"→"져도"로 축약. 의미·Trade-off 동일. |
| creative_ideation_game_v1 | ci_invent_rule | creative_ideation | 여러 요소를 새롭게 엮어서 지금까지와 다른 방식을 스스로 만들어본다 (37) | 여러 요소를 새롭게 엮어서 다른 방식을 스스로 만들어본다 (31) | 24 | "지금까지와"를 삭제해도 "다른 방식"이 이미 차별성을 전달한다. "새롭게 엮어서... 만들어본다"(조합·생성 행동, novelty_seeking과 분리한 2.1단계 표현)는 그대로다. |

## 수정하지 않은 항목

`opinion_expression_school_life_v1`(oe_speak_role, 2.2단계 Trade-off 추가분, 35자 vs
최대 26자)은 자동 검사의 "지나치게 김" 기준(margin 10자)에는 걸리지 않았지만
"선택지 길이 편차 큼" 경고는 여전히 남아 있다 — 임의로 더 줄이면 Trade-off 문구
("다른 사람들 반응이 걱정되더라도")가 사라질 위험이 있어 이번 라운드에서는 손대지
않았다. 2인 검토에서 필요하다고 판단하면 후속 라운드에서 다룬다.

## 검증

`src/engines/v2_direct_probe_quality_checks.py::question_level_flags()`를 14개
Blueprint 전체에 다시 실행한 결과, "Target Option이 다른 선택지보다 지나치게 김" 경고가
7개 모두에서 사라졌다(수정 전 7건 → 수정 후 0건). 자동 검사기 자체가 "편향 없음"을
확정하는 게 아니라는 원칙은 그대로 유지한다 — 이 결과는 "정량적 길이 이상치가
사라졌다"는 사실만 보장하고, 문장이 실제로 자연스러운지·여전히 Target을 짐작하게
만드는지는 사람이 읽고 판단해야 한다.

## 상태

`REVIEW_REQUIRED` — 7개 Blueprint 모두. 자동 검사(길이·PRIMARY 매핑 정합성)는 통과했지만,
LLM Quality Gate 통과나 이 문서의 자체 판단을 "내용 타당성 검토 완료"로 간주하지 않는다.
2인 Human Review Worksheet(`v2_direct_probe_human_review_guide.md`)에서 실제 사람이
자연스러움·PRIMARY 근거를 확인해야 `TEAM_REVIEWED`로 승격할 수 있다.
