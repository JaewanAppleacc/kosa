# Trait Ontology — Vertical Slice 초안 (DRAFT, 2인 교차검토 전)

기준 문서: `outputs/AI_진로_학업설계_Agent_수정_최종설계안.md` §6-1·§6-3·§6-4·§6-6
전제: Context Definition Table v2 확정(게임·미디어·학교생활·창업비즈니스·만들기, Vertical Slice=게임·미디어·학교생활)

총 12개(설계안 §2 "Trait 10~12개" 상한). §6-4 권장 비율(Shared 70~80% / Domain-specific 20~30%)에 맞춰 Shared 9개(75%) + Domain-specific 3개(25%)로 구성했습니다.

**2026-08-20 결정 반영**: O*NET/Holland 그라운딩 조사 이후 두 가지를 확정했습니다.
1. 대응 항목이 없던 `immediate_execution`, `opinion_mediation`, `audience_response_prediction`은 O*NET 대응을 더 찾지 않고 **"팀 정의" 상태로 확정**합니다.
2. `prioritization`과 `planning`은 O*NET에서 같은 항목("Organizing, Planning, and Prioritizing Work")을 공유하는 게 확인돼 **`planning` 하나로 통합**하고, 빈 자리에 O*NET Work Style "Adaptability"에 대응되는 **`change_adaptation`(변화 대응)**을 새로 추가했습니다. 총 개수는 12개로 동일합니다.

## 1. Trait 목록 — 분류·정의

| trait_id | 이름 | 상위 Dimension | primary_vector_group | scope | minimum_context_count |
|---|---|---|---|---|---|
| causal_analysis | 원인 분석 | 분석과 구조화 | cognitive | shared | 2 |
| pattern_finding | 패턴 탐색 | 분석과 구조화 | cognitive | shared | 2 |
| planning | 계획·우선순위 수립 | 계획과 실행 | work_style | shared | 2 |
| immediate_execution | 즉시 실행 | 계획과 실행 | work_style | shared | 2 |
| change_adaptation | 변화 대응 | 계획과 실행 | work_style | shared | 2 |
| collaboration_preference | 협업 선호 | 협업과 조정 | work_style | shared | 2 |
| opinion_mediation | 의견 조정 | 협업과 조정 | work_style | shared | 2 |
| emotional_interpretation | 타인의 감정 해석 | 인간과 관계 탐구 | cognitive | shared | 2 |
| audience_response_prediction | 사용자 반응 예측 | 사용자·타인 관점 | cognitive | shared | 2 |
| visual_expression | 시각적 표현 | 창의적 표현 | interest | domain_specific | 1 |
| information_comparison | 정보 비교·탐색 | 정보 탐색과 비교 | cognitive | domain_specific | 1 |
| tool_utilization | 도구 활용 | 도구 활용과 제작 | environment | domain_specific | 1 |

## 1-1. 근거 자료 그라운딩 (2026-08-20, O*NET/Holland 실제 조회)

앞선 버전에서는 `source_references`를 전부 "O*NET/Holland 참고"로 뭉뚱그렸는데, 실제로 O*NET Online(onetonline.org)·O*NET Resource Center(onetcenter.org)를 조회해서 12개 각각에 대응하는 공식 항목이 있는지 확인했습니다. **결과: 12개 중 깔끔하게 맞는 건 절반 정도고, 나머지는 억지 대응이거나 아예 대응되는 공식 항목이 없습니다.** 없는 걸 있는 것처럼 적지 않았습니다.

참고로 O*NET Work Styles는 2024년에 구조가 개편돼(21개 하위 항목 → 4개 상위 그룹: Conscientious and Rule Oriented / Emotionally Resilient / Interpersonally Oriented / Proactive and Growth Oriented), 예전에 흔히 인용되던 16개 항목 목록(제 기억 속 지식)은 이제 낡은 버전입니다. 아래는 2024 개편판 기준입니다.

| trait_id | 대응 시도 | 원문 정의 | 적합도 | 확인 방식 |
|---|---|---|---|---|
| causal_analysis | O*NET GWA "Analyzing Data or Information" (코드 4.A.2.a.4) | "Identifying the underlying principles, reasons, or facts of information by breaking down information or data into separate parts." | **강함** | 해당 페이지 직접 조회 |
| pattern_finding | Holland "Investigative" 유형 | "Investigative types typically like to work with ideas... logical, curious, exact, intellectual, cautious, independent" | 보통 (유형 설명 수준, 항목 단위 대응 아님) | 검색 결과 인용 |
| planning | O*NET GWA "Organizing, Planning, and Prioritizing Work" (코드 4.A.2.b.6) | "Developing specific goals and plans to prioritize, organize, and accomplish your work." | 보통 — 2026-08-20 결정으로 prioritization을 이 항목에 통합 | 검색 결과 인용 |
| immediate_execution | **팀 정의로 확정(2026-08-20)** — O*NET 대응 항목 없음 (Work Style "Initiative"가 제일 가깝지만 "책임을 자발적으로 더 맡는 것"이지 "계획 없이 바로 하는 것"과는 다른 개념이라 채택 안 함) | - | 팀 정의 | 항목명만 확인, 정의문 미조회 |
| change_adaptation | O*NET Work Style "Adaptability" (Proactive and Growth Oriented, 2024 개편판) | 정의문 미조회, 항목명만 확인 | 보통 — 항목명 확인, 정의문 미확인 | 항목명만 확인 |
| collaboration_preference | O*NET Work Style "Cooperation" (Interpersonally Oriented) | 2024 개편판 정의문 미조회 (구버전 정의: "being pleasant with others... cooperative attitude") | 보통 — 항목명은 2024판에도 살아있음, 정의문은 구버전 인용 | 항목명 직접 조회, 정의문은 구버전 기억 |
| opinion_mediation | **팀 정의로 확정(2026-08-20)** — O*NET 대응 항목 없음 (GWA "Coordinating, Developing, Managing, and Advising" 카테고리명만 존재, 세부 정의 미조회) | - | 팀 정의 | 카테고리명만 확인 |
| emotional_interpretation | O*NET Work Style "Empathy" (2024 신설 항목) | 정의문 미조회 | 보통 — 항목명은 확인, 정의문 미확인 | 항목명만 확인 |
| audience_response_prediction | **팀 정의로 확정(2026-08-20)** — O*NET 대응 항목 불확실 (GWA "Interpreting the Meaning of Information for Others" 추정, 항목명도 정확히 재확인 못함) | - | 팀 정의 | 미확인 |
| visual_expression | GWA "Thinking Creatively" + Holland "Artistic" | "Developing, designing, or creating new applications, ideas, relationships, systems, or products, including artistic contributions." | **강함** | 검색 결과 인용 |
| information_comparison | GWA "Getting Information" | "Observing, receiving, and otherwise obtaining information from all relevant sources." | 보통 — "비교"라는 뉘앙스는 원문에 없고 제가 붙인 것 | 검색 결과 인용 |
| tool_utilization | Holland "Realistic" 유형 | "Realistic types generally like to work with things more than with people... practical, natural, persistent" | 보통 | 검색 결과 인용 |

**정리(2026-08-20 결정 반영):**
- **강하게 대응됨(2개)**: causal_analysis, visual_expression — 공식 정의문까지 직접 확인.
- **항목명은 확인, 정의문은 미확인(4개)**: planning, change_adaptation, collaboration_preference, emotional_interpretation — O*NET이 2024년에 구조를 바꾸면서 새 정의문이 온라인 페이지 텍스트로 잘 안 열려서, 항목이 "존재한다"까지만 확인했습니다.
- **팀 정의로 확정(3개)**: immediate_execution, opinion_mediation, audience_response_prediction — O*NET/Holland 대응 항목을 찾지 못해 억지로 갖다 붙이지 않고, "이 프로젝트를 위해 팀이 정의한 개념"으로 명시적으로 확정했습니다. 발표 시 이 3개는 O*NET 근거를 주장하지 않습니다.
- **prioritization은 planning에 통합**: O*NET이 이 둘을 애초에 하나의 활동("Organizing, Planning, and Prioritizing Work")으로 보는 게 확인돼, 별도 유지의 실익이 없다고 판단해 `planning`(계획·우선순위 수립) 하나로 합쳤습니다. 빈 자리에는 O*NET Work Style "Adaptability"에 대응되는 `change_adaptation`(변화 대응)을 추가했습니다.

**출처:**
- [Work Activities — Analyzing Data or Information](https://www.onetonline.org/find/descriptor/result/4.A.2.a.4)
- [Work Activities — Organizing, Planning, and Prioritizing Work](https://www.onetonline.org/find/descriptor/result/4.A.2.b.6)
- [Browse by Work Styles (2024 개편 구조)](https://www.onetonline.org/find/descriptor/browse/1.D)
- [Browse by Work Activities](https://www.onetonline.org/find/descriptor/browse/4.A)
- [Revisiting the Work Styles Domain of the O*NET Content Model (2024)](https://www.onetcenter.org/reports/Work_Styles_New.html)
- [RIASEC Theory — Self-Directed Search](https://self-directed-search.com/riasec-theory/)

이 결과를 각 Trait의 `source_references` 필드에 그대로 반영했고(강함/보통/약함 표시 포함), "대응 항목 없음"으로 나온 3개는 `source_references: ["팀 정의 — O*NET/Holland 대응 항목 없음, 2026-08-20 조사"]`로 명시했습니다.

## 2. Trait 목록 — 정의·행동·구분 기준

| trait_id | 정의 | 관찰 행동 | 상충 행동 | 유사 Trait와의 차이 |
|---|---|---|---|---|
| causal_analysis | 결과나 현상이 발생한 이유를 파고들어 확인하려는 경향 | 예상과 다른 결과가 나왔을 때 원인을 먼저 짚어보는 선택 | 원인 파악 없이 바로 다른 방법을 시도하거나 넘어감 | pattern_finding은 "반복되는 규칙"에, causal_analysis는 "이번 결과의 이유"에 초점 |
| pattern_finding | 여러 사례·정보에서 공통된 규칙이나 흐름을 찾아내려는 경향 | 여러 선택지·사례를 비교해 공통점을 정리하는 선택 | 사례를 개별적으로만 보고 규칙화하지 않음 | information_comparison은 "정보를 늘어놓고 비교"하는 것 자체, pattern_finding은 그 안에서 "규칙을 뽑아내는 것" |
| planning | 행동하기 전에 전체 절차나 방법을 미리 구상하고, 제한된 시간·자원에서 무엇을 먼저 할지 기준을 세워 정하는 경향 | 새로운 과제·도구가 주어졌을 때 먼저 방법을 구상하거나, "제한된 시간에는 무엇을 우선하는가" 질문에 명확한 기준으로 답함 | 구상·순서 없이 닥치는 대로 바로 시도 | immediate_execution과 반대 성향 쌍 (§3 Contrast Pair 참고). 2026-08-20부로 옛 prioritization의 "우선순위 판단" 의미를 흡수함 |
| immediate_execution | 계획을 오래 세우기보다 일단 시도하며 방법을 찾는 경향 | 새로운 도구·상황에서 바로 시도해보는 선택 | 시도 전에 충분히 계획부터 세움 | planning과 반대 성향 쌍 |
| change_adaptation | 예상과 다른 상황이 생겼을 때 유연하게 대응 방식을 바꾸는 경향 | "결과가 예상과 다르면 어떻게 수정하는가" 질문에서 새 방법을 시도하는 선택 | 원래 방식을 고수하며 바꾸지 않음 | causal_analysis는 "왜 그런지 원인을 파고드는 것"에, change_adaptation은 "원인 분석 여부와 무관하게 일단 방식을 바꾸는 것"에 초점 — 보완적이지만 다른 축 |
| collaboration_preference | 혼자보다 다른 사람과 함께 일하는 것을 선호하는 경향 | 팀 활동에서 역할을 나누거나 함께 결정하는 선택 | 혼자 처리하는 방식을 선호 | opinion_mediation은 "의견이 갈릴 때의 행동", collaboration_preference는 "함께 하는 것 자체에 대한 선호" |
| opinion_mediation | 여러 의견이 충돌할 때 기준을 세워 조율하려는 경향 | "여러 의견이 충돌하면 무엇을 기준으로 결정하는가" 질문에 조정 기준을 제시 | 충돌을 피하거나 한쪽 의견을 그대로 따름 | 위 참고 |
| emotional_interpretation | 다른 사람의 감정이나 반응을 관찰해 이해하려는 경향 | 친구·캐릭터·시청자의 감정 변화를 언급하며 선택 | 감정보다 사실·결과 자체에만 집중 | audience_response_prediction은 "앞으로의 반응 예측", emotional_interpretation은 "지금 느끼는 감정 이해" |
| audience_response_prediction | 결과물·행동에 대해 다른 사람이 어떻게 받아들일지 미리 고려하는 경향 | 결과물을 만들 때 "보는 사람이 어떻게 느낄지"를 기준으로 선택 | 자신의 기준만 고려하고 상대 반응은 고려하지 않음 | 위 참고 |
| visual_expression | 생각·느낌을 이미지·영상 등 시각적 형태로 표현하는 것에 대한 관심 | 편집·구성·이미지 관련 선택지를 선호 | 시각적 요소보다 글이나 말로 표현하는 것을 선호 | tool_utilization은 "어떤 방식으로 다루는가"(수단), visual_expression은 "무엇을 표현하는가"(결과물 형태) |
| information_comparison | 결정 전에 여러 정보나 선택지를 찾아보고 비교하는 경향 | 결정 전에 여러 자료·사례를 찾아보는 선택 | 정보 탐색 없이 직관적으로 바로 결정 | pattern_finding 참고 |
| tool_utilization | 도구·장비를 다뤄 결과물을 직접 만들거나 조작하는 것을 선호하는 경향 | 아이템·장비·편집 도구 등을 직접 다루는 선택 | 도구를 다루기보다 아이디어·구상 단계에 머무름 | immediate_execution은 "언제 하는가"(타이밍), tool_utilization은 "무엇으로 하는가"(수단) |

## 2-1. Trait 중복·구분 집중 검토 (2026-08-22 12차 리뷰)

§2의 "유사 Trait와의 차이" 열이 구분 기준은 담고 있지만, "동시에 강하게 나타날 수 있는가"·
"Contrast Pair로 볼 수 있는가"·"질문에서 어떻게 구분하는가"는 따로 정리돼 있지 않았다.
아래 7개 쌍을 이 4개 축으로 다시 검토한다.

| 쌍 | 공통점 | 구분 기준 | 동시에 강하게 나타날 수 있는가 | Contrast Pair로 볼 수 있는가 | 질문에서 어떻게 구분하는가 |
|---|---|---|---|---|---|
| causal_analysis vs pattern_finding | 둘 다 "생각하고 분석한다"는 인지적 활동 | causal_analysis는 **이번 한 결과**의 원인(왜 이렇게 됐나), pattern_finding은 **여러 사례**에 걸친 공통 규칙(무엇이 반복되나) | **예.** 원인을 캐다가 "이게 매번 같은 이유로 생기네"라며 규칙을 뽑아내는 건 자연스러운 연속 활동이다 | **아니오.** 반대 방향이 아니라 같은 방향의 서로 다른 초점이라 §12-1 Contrast 요건("동시에 존재할 수 없는 반대 쌍")에 안 맞는다 | 단발성 사건 원인을 묻는 질문(causal_analysis)과, 여러 선택지·사례를 늘어놓고 공통점을 묻는 질문(pattern_finding)으로 Frame 자체를 다르게 설계한다 |
| planning vs immediate_execution | 둘 다 "새로운 과제·도구가 주어졌을 때" 접근 방식을 다룬다 | planning은 시작 **전에** 전체 절차를 구상, immediate_execution은 구상 없이 **바로** 시도 | **제한적.** 같은 Frame(예: "새로운 도구가 주어지면?") 안에서는 한쪽 선택만 가능하지만, Frame이 다르면(예: 익숙한 상황 vs 낯선 상황) 같은 학생이 둘 다 관찰될 수 있다 — 그래서 RESOLVED_CONTEXT_DEPENDENT 상태가 존재한다 | **예.** 이미 §3/§12-1에서 실제 ContrastDefinition(`planning_vs_execution`)으로 구현돼 있다 | 같은 "new_tool" Frame 안에서 두 선택지를 직접 대조시키는 한 문항으로 구분한다(이미 구현됨) |
| planning vs information_comparison | 둘 다 "행동하기 전에 무언가를 먼저 한다"는 준비 단계 활동 | planning은 **절차·순서**를 구상(무엇을 언제 할지), information_comparison은 **정보·선택지**를 모아 비교(무엇을 고를지) — 계획은 "어떻게"에, 정보 비교는 "무엇을 고를 근거"에 초점 | **예.** 오히려 실전에서는 정보를 비교해서 계획에 반영하는 게 자연스러운 흐름이라 상관관계가 있을 것으로 예상된다(상충이 아니라 보완 관계) | **아니오.** 반대 방향이 아니라 준비 단계 안에서 서로 다른 하위 활동이라 Contrast 요건에 안 맞는다 | planning은 "언제·어떤 순서로 할지" 질문으로, information_comparison은 "결정 전에 자료·사례를 찾아보는지" 질문으로 구분한다 — 옵션 문구에 "순서/우선순위" 단어가 있으면 planning, "비교/찾아본다" 단어가 있으면 information_comparison 쪽 role로 설계한다 |
| collaboration_preference vs opinion_mediation | 둘 다 "다른 사람과의 상호작용" 관련 Trait | collaboration_preference는 **함께 일하는 것 자체**에 대한 선호(협업 여부), opinion_mediation은 의견이 **충돌했을 때** 어떻게 조율하는가(협업 중 갈등 대응) | **예.** 협업을 선호하는 사람이 의견 조정도 잘할 수 있고, 반대로 협업은 선호해도 의견 충돌은 피하는 사람도 있어 독립적인 축이다 | **아니오.** 반대 성향이 아니라 "협업 여부"와 "협업 중 갈등 대응 방식"이라는 서로 다른 국면을 다룬다 | collaboration_preference는 "혼자 할지 함께 할지" 선택 질문으로, opinion_mediation은 "의견이 갈리면 무엇을 기준으로 결정하는가" 질문으로 Frame을 분리한다 |
| emotional_interpretation vs audience_response_prediction | 둘 다 "타인의 심리 상태"를 다루는 관계 지향 Trait | emotional_interpretation은 **지금 상대가 느끼는 감정**을 이해, audience_response_prediction은 **앞으로 결과물에 대해 상대가 보일 반응**을 미리 예측 — 시점(현재 관찰 vs 미래 예측)과 대상(구체적 개인 vs 불특정 수용자)이 다르다 | **예.** 콘텐츠 제작처럼 "지금 캐릭터/사용자의 감정을 이해"하면서 동시에 "이 결과물을 볼 사람들이 어떻게 반응할지" 예측하는 경우가 흔하다 | **아니오.** 결핍/과잉의 반대 쌍이 아니라 시점이 다른 관찰이라 Contrast 요건에 안 맞는다 | emotional_interpretation은 특정 인물의 감정 변화를 언급하는 선택지로, audience_response_prediction은 "보는 사람이 어떻게 느낄지"를 기준으로 결과물을 설계하는 선택지로 구분한다 |
| visual_expression vs tool_utilization | 둘 다 "창작·제작 활동"과 연결된 Trait | visual_expression은 **무엇을 표현하는가**(시각적 형태라는 결과물 성격), tool_utilization은 **무엇으로 하는가**(도구·장비라는 수단) — 결과물의 형태 vs 작업의 수단 | **예.** 시각적 결과물을 만들려면 대개 도구를 다뤄야 하므로 상관관계가 높을 것으로 예상되지만, 개념적으로는 "그림을 손으로 그리는 것"(도구 없이도 visual_expression은 강할 수 있음)처럼 분리도 가능하다 | **아니오.** 반대 방향이 아니라 "결과물 형태"와 "작업 수단"이라는 서로 다른 축이다 | visual_expression은 편집·구성·이미지 등 결과물 형태를 고르는 선택지로, tool_utilization은 도구·장비를 직접 다루는 행위 자체를 고르는 선택지로 구분한다 |
| change_adaptation vs immediate_execution | 둘 다 work_style 그룹이고, 계획을 고수하지 않는다는 인상을 줄 수 있다 | immediate_execution은 **시작 시점**의 태도(계획 없이 바로 시작하는가), change_adaptation은 **진행 중** 예상과 다른 결과가 나왔을 때의 태도(방식을 바꾸는가) — "언제 계획을 안 세우는가"(시작 전)와 "언제 바꾸는가"(도중)로 시점이 다르다 | **예.** 계획을 세워 시작했더라도(immediate_execution은 낮음) 중간에 예상과 다르면 유연하게 수정하는(change_adaptation은 높음) 학생이 흔하다 — 오히려 이 조합("계획적으로 시작하되 필요하면 유연하게 수정")이 실무에서 이상적인 경우도 많아, 서로 배타적이지 않다 | **아니오.** 시작 시점과 진행 중이라는 서로 다른 국면을 다루는 독립적인 축이라 Contrast 요건("같은 조건에서 상충하는 반대 쌍")에 안 맞는다 | immediate_execution은 "새로운 과제를 처음 받았을 때" 질문으로, change_adaptation은 "진행하다가 결과가 예상과 다르면 어떻게 하는가" 질문으로 시점 자체를 다르게 설계해서 구분한다 |

**결론**: 위 7개 쌍 중 실제 반대 방향 Contrast Pair 요건(§12-1 "동시에 존재할 수 없는
반대 성향")을 만족하는 건 `planning vs immediate_execution` 하나뿐이고, 이미
`ContrastDefinition`으로 구현돼 있다. 나머지 6개 쌍은 전부 "동시에 강하게 나타날 수
있는 독립적이거나 보완적인 축"으로 확인돼, 새로운 Contrast Pair를 추가할 근거가 없다
— CLAUDE.md "동시에 존재할 수 있는 특성은 Contrast Pair로 만들지 않는다"와 일치한다.

## 3. Explicit Conflict 후보 (§12-1 ContrastDefinition)

Vertical Slice 단계에서 Conflict 탐지 로직 자체가 동작하는지 검증하려면 최소 1개의 Contrast Pair가 필요합니다.

```python
ContrastDefinition(
    contrast_id="planning_vs_execution",
    construct_id="approach_timing",
    positive_role_ids=["<planning Trait로 연결된 role_id들>"],
    opposite_role_ids=["<immediate_execution Trait로 연결된 role_id들>"],
    comparable_frame_ids=["new_tool"],  # "새로운 도구가 주어지면 어떻게 접근하는가" 프레임에서 두 선택지가 직접 대조됨
    condition_scope="새로운 도구·과제가 주어진 상황",
    minimum_evidence_each_side=2,
    description="같은 '새로운 상황' 조건에서 미리 계획하는지 바로 시도하는지가 갈리는 경우",
)
```

`collaboration_preference` vs `독립 작업 선호`처럼 동시에 존재할 수 있는 성향은 설계안 §12-1이 명시적으로 금지하므로 이번 12개에는 그런 쌍을 넣지 않았습니다(독립 작업 선호 Trait 자체를 이번 12개에서 제외).

## 4. 3-Context 예비 관찰 가능성 체크 (§6-5 정식 Matrix 전 사전 점검용)

정식 Coverage Matrix(§6-5)는 15개 Context 전체를 대상으로 다음 단계에서 만듭니다. 아래는 "이 12개 Trait를 지금 3개 Context만으로 Vertical Slice가 실제로 돌아갈지" 확인하는 약식 점검입니다(0~3 등급).

| trait_id | 게임 | 미디어 | 학교생활 | min_context 충족? |
|---|---:|---:|---:|---|
| causal_analysis | 3 | 2 | 2 | ✔ (3/3 ≥2) |
| pattern_finding | 3 | 2 | 2 | ✔ (3/3 ≥2) |
| planning | 2 | 2 | 3 | ✔ (3/3 ≥2) |
| immediate_execution | 3 | 2 | 1 | ✔ (2/3 ≥2) |
| change_adaptation | 3 | 2 | 2 | ✔ (3/3 ≥2) |
| collaboration_preference | 2 | 1 | 3 | ✔ (2/3 ≥2) |
| opinion_mediation | 2 | 1 | 3 | ✔ (2/3 ≥2) |
| emotional_interpretation | 1 | 3 | 2 | ✔ (2/3 ≥2) |
| audience_response_prediction | 1 | 3 | 2 | ✔ (2/3 ≥2) |
| visual_expression (min=1) | 1 | 3 | 1 | ✔ |
| information_comparison (min=1) | 3 | 2 | 2 | ✔ (여유 있음) |
| tool_utilization (min=1) | 2 | 2 | 1 | ✔ (min은 충족하나 3개 다 약함) |

12개 전부 `minimum_context_count`를 충족해서 Vertical Slice 진행에는 문제가 없습니다. 다만 `tool_utilization`은 세 Context 전부에서 등급이 낮은 편이라(2/2/1), "도구 활용과 제작" Dimension 자체가 3단계에서 "만들기·코딩" Context가 들어와야 제대로 채워질 약점입니다 — Context Definition Table v2에서 이미 짚었던 문제와 같은 지점이라 새로운 리스크는 아닙니다.

## 5. 확인이 필요한 지점

~~0. immediate_execution/opinion_mediation/audience_response_prediction 팀 정의 여부~~ → 팀 정의로 확정(2026-08-20).
~~1. prioritization/planning 통합 여부~~ → planning으로 통합, change_adaptation 신규 추가로 확정(2026-08-20).

2. `collaboration_preference`, `emotional_interpretation`, `change_adaptation`은 O*NET 2024 개편판에 항목명("Cooperation", "Empathy", "Adaptability")은 확인했지만 새 정의문 원문은 못 찾았습니다(사이트 구조상 상세 정의 페이지가 텍스트로 잘 안 열림). 정확한 인용이 필요하면 O*NET Resource Center의 Excel 원본 파일(`Work Style Names and Descriptions.xlsx`)을 직접 받아서 확인해야 합니다.
3. `information_comparison`을 domain_specific으로 분류했는데, 위 표를 보면 3개 Context 전부에서 고르게 관찰돼(3/2/2) 사실상 shared에 가깝습니다. 비율(75/25%)을 맞추려고 domain_specific에 넣었는데, 이후 15개 Context로 확장했을 때도 실제로 도메인 편향이 있는지는 재검토가 필요합니다.
4. `tool_utilization`은 지금 3개 Context 안에서는 약하게만 관찰됩니다. Vertical Slice 통과 자체엔 지장 없지만("STRONG" 판정까지 안 가고 "LIMITED"에 머물 가능성이 높음), 이게 로직 버그가 아니라 데이터 부족 때문이라는 걸 팀이 미리 인지하고 있어야 나중에 "왜 이 Trait만 약하게 나오지?"라는 오해를 피할 수 있습니다.
5. Contrast Pair(§3)의 `positive_role_ids`/`opposite_role_ids`는 아직 실제 role_id가 없어 자리표시자입니다. 다음 단계(Question/Option Blueprint 스켈레톤)에서 `planning`·`immediate_execution` 각각에 연결되는 role을 최소 1개씩 만들 때 이 Contrast 정의도 같이 채워야 합니다.

## 6. 다음 단계와의 연결

- 이 12개가 곧 A 지시서 §3 "공통 Pydantic Schema" 중 `TraitDefinition` 12건의 실제 데이터가 됩니다.
- 다음 산출물(Question/Evidence 통합 Schema, AssessmentState 등 4종 스켈레톤)에서 `target_traits`, `primary_trait_delta`가 참조할 `trait_id` 목록이 바로 이 표의 `trait_id` 컬럼입니다.
- 대표 전공 3개(다음 단계)를 고를 때, 이 12개 Trait로 서로 다른 점수 프로필이 나올 수 있는 전공 3개를 고르는 게 좋습니다 — 예: 분석/계획 중심 전공, 창의/사용자관점 중심 전공, 협업/관계 중심 전공처럼 서로 다른 Trait 조합에서 강점이 갈리는 조합.
