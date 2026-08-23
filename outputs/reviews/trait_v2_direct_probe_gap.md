# Trait v2 Direct Probe Gap — 2026-08-23 Trait Ontology v2(1.5단계) §12

이 문서는 신규 12개 Trait 중 우선 검토 대상 7개(systems_thinking, creative_ideation,
detail_orientation, persistence_completion, independent_judgment, uncertainty_tolerance,
opinion_expression)에 대해 "PRIMARY 질문을 실제로 만든다면 어떻게 만들 것인가"를
설계 초안 수준으로 정리한다.

**이번 단계에서 하지 않는 것**: 아래 질문 문장·선택지 초안은 Runtime Question Bank나
LLM Tail Option Blueprint에 등록하지 않는다. 신규 Trait용 실제 질문은 사용자 승인 후
별도 단계에서 적용한다(1.5단계 지시서 §12). 이 문서는 그 결정을 위한 자료다.

각 Trait 표의 "현재 Signal 상태/Context/Frame"은
`src/data/trait_ontology/trait_probe_capabilities_v2.py::TRAIT_PROBE_CAPABILITIES`에서
실제로 계산한 값을 그대로 옮긴 것이다(손으로 다시 세지 않았다).

---

## systems_thinking (구조적 사고)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 12개(Registry 전체 60개 등록 중 12개가
  이 Trait를 RELATED로 가리킨다 — 신규 12개 중 가장 넓게 관찰되는 Trait).
- **현재 연결 Context**: game, media, school_life 전부(단, 전부 RELATED 경유이며 Tail
  Blueprint 3개 모두에 등장한다).
- **현재 연결 Frame**: seed_frame, backup, problem_check, longest_focus,
  unexpected_result, new_tool, others_reaction, conflicting_opinions, team_role,
  limited_time_priority, first_action(사실상 전체) — Tail Blueprint 소속 Role에 RELATED가
  많이 걸려 있어 Frame 다양성 자체는 이미 넓다.
- **PRIMARY 질문 필요 여부**: 필요. RELATED만으로는 §9 승격 규칙을 만족해도 LIMITED
  상한(0.33)을 넘지 못한다 — "구조적 사고가 이 학생의 뚜렷한 성향"이라고 말하려면
  causal_analysis/pattern_finding과 구별되는 PRIMARY 근거가 있어야 한다.
- **가능한 질문 Context 2개**: game(시스템 하나를 바꾸면 다른 요소가 어떻게 같이
  움직이는지 다루는 공략·밸런스 상황), school_life(동아리·프로젝트에서 한 역할이 바뀌면
  다른 역할에 어떤 영향이 가는지 다루는 상황).
- **서로 다른 질문 Frame 2개**: `problem_check`(문제가 생기면 무엇부터 확인하는가 —
  "이 부분만 보나, 연결된 다른 부분까지 같이 보나"), `new_tool`(새 도구가 주어지면 —
  "이 도구 하나만 보나, 기존 요소들과 어떻게 맞물리는지 같이 보나").
- **기존 Trait와 구별해야 할 핵심**: causal_analysis(원인 하나를 깊게 판다) ·
  pattern_finding(반복 규칙을 찾는다)과 달리, systems_thinking은 "요소 간 상호작용·
  관계망 전체"에 초점이 있다 — 질문 상황에 반드시 "요소가 2개 이상이고 서로 영향을
  주고받는다"는 구조가 들어가야 한다.
- **질문 설계 시 오판 가능성**: 상황에 요소가 하나뿐이면(예: "왜 실패했는지 분석한다")
  causal_analysis와 구별이 안 된다 — 선택지 문구가 "그 이유를 찾는다"에 머물지 않고
  "그게 바뀌면 다른 것도 같이 바뀌는지 본다"까지 명시해야 오판을 줄일 수 있다.

## creative_ideation (아이디어 발상)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 0개 — Registry 어디에도 등록돼 있지 않다
  (NOT_PROBED).
- **현재 연결 Context / Frame**: 없음.
- **PRIMARY 질문 필요 여부**: 필요(RELATED조차 없어 현재 완전히 관찰 불가).
- **가능한 질문 Context 2개**: game(새 규칙·전략을 스스로 떠올리는 상황), media(기존에
  없던 콘텐츠 소재·구성을 떠올리는 상황).
- **서로 다른 질문 Frame 2개**: `first_action`(가장 먼저 무엇을 하고 싶은가 — "본 적
  없는 새로운 방식을 떠올려본다"), `new_tool`(새로운 도구가 주어지면 — "이 도구로 아직
  아무도 안 해본 걸 시도해본다").
- **기존 Trait와 구별해야 할 핵심**: visual_expression/verbal_expression은 표현 "형태"
  (시각/언어)에 대한 관심이고, creative_ideation은 형태와 무관하게 "새로운 발상 자체"다
  — 리뷰 문서(`trait_ontology_v2_review.md`)에 기록된 대로 visual_expression과의 O*NET
  근거 중첩 긴장이 있으므로, 질문 상황에서 "무엇을 그리는가/어떻게 표현하는가"가 아니라
  "무엇을 떠올렸는가"에 초점을 맞춰야 한다.
- **질문 설계 시 오판 가능성**: 선택지가 "새로운 디자인을 그려본다"처럼 시각적 표현으로
  귀결되면 visual_expression과 겹친다 — "떠올린 아이디어를 실제로 어떻게 구현했는가"가
  아니라 "무엇을 떠올렸는가" 자체에서 응답이 갈리도록 설계해야 한다. novelty_seeking
  (새로움을 찾아 나서는 것)과도 겹칠 수 있다 — novelty_seeking은 "익숙한 것 대신 새 걸
  고른다"는 선택 행동이고, creative_ideation은 "없던 것을 스스로 만들어낸다"는 생성
  행동이라는 차이를 선택지 문구로 분명히 해야 한다.

## detail_orientation (세부 주의)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 5개.
- **현재 연결 Context**: game, media, school_life.
- **현재 연결 Frame**: seed_frame, backup, problem_check을 포함해 problem_response_v1·
  media Seed·3개 Backup에 걸쳐 있음.
- **PRIMARY 질문 필요 여부**: 필요.
- **가능한 질문 Context 2개**: media(정보·자료를 비교할 때 사소한 차이까지 짚어보는
  상황), school_life(과제·자료를 제출하기 전 세부 오류를 확인하는 상황).
- **서로 다른 질문 Frame 2개**: `problem_check`(문제가 생기면 무엇부터 확인하는가 —
  "전체 흐름만 보나, 각 부분의 작은 오차까지 짚어보나"), `limited_time_priority`(제한된
  시간에는 무엇을 우선하는가 — "시간이 없어도 세부까지 챙기는가, 큰 흐름만 보는가").
- **기존 Trait와 구별해야 할 핵심**: information_comparison(여러 대상을 비교해 정보를
  찾는다)과 persistence_completion(끝까지 지속한다)과 다르다 — detail_orientation은
  "정확성"(세부까지 꼼꼼히 보는가) 축이라, 비교 대상이 있는지·끝까지 갔는지와 무관하게
  "본 것 안에서 얼마나 세밀하게 보는가"에 집중해야 한다.
- **질문 설계 시 오판 가능성**: "여러 자료를 찾아본다"류 선택지는 information_comparison
  으로 읽히기 쉽다 — "찾아본다"가 아니라 "이미 본 것에서 작은 차이·오류까지 짚어낸다"는
  문구가 필요하다.

## persistence_completion (지속·완수)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 5개.
- **현재 연결 Context**: game, media, school_life.
- **현재 연결 Frame**: seed_frame, backup, planning_and_execution_v1 소속 Frame 전체.
- **PRIMARY 질문 필요 여부**: 필요.
- **가능한 질문 Context 2개**: school_life(장기 프로젝트·과제를 진행하다 지루하거나
  막힐 때의 행동), game(어려운 스테이지·목표를 반복 실패해도 계속 도전하는 상황).
- **서로 다른 질문 Frame 2개**: `unexpected_result`(결과가 예상과 다르면 어떻게
  수정하는가 — "포기하지 않고 방법을 바꿔서라도 끝까지 간다"), `limited_time_priority`
  (제한된 시간에는 무엇을 우선하는가 — "시간이 부족해도 시작한 걸 끝까지 마무리한다").
- **기존 Trait와 구별해야 할 핵심**: planning(시작 전 순서를 미리 구상)과는 시점이
  다르다 — persistence_completion은 "시작한 뒤 어려워져도 끝까지 가는가"이므로, 질문
  상황에 반드시 "이미 시작한 일이 어려워지거나 지루해졌다"는 전제가 들어가야 한다.
- **질문 설계 시 오판 가능성**: "미리 계획을 세운다"류 선택지는 planning과 겹친다 —
  계획 여부가 아니라 "어려움이 생긴 뒤에도 그만두지 않는가"로 응답이 갈리게 해야 한다.

## independent_judgment (독립적 판단)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 0개 — Registry 어디에도 등록돼 있지 않다
  (NOT_PROBED).
- **현재 연결 Context / Frame**: 없음.
- **PRIMARY 질문 필요 여부**: 필요(RELATED조차 없어 완전히 관찰 불가).
- **가능한 질문 Context 2개**: school_life(팀 활동에서 남의 의견을 따르기보다 스스로
  판단해 결정하는 상황), game(공략을 참고하지 않고 스스로 판단해 플레이 방식을 정하는
  상황).
- **서로 다른 질문 Frame 2개**: `team_role`(팀 활동에서는 어떤 역할을 맡고 싶은가 —
  "함께 하더라도 판단은 스스로 내린다"), `conflicting_opinions`(여러 의견이 충돌하면
  무엇을 기준으로 결정하는가 — "다른 사람 의견보다 스스로 판단한 기준을 따른다").
- **기존 Trait와 구별해야 할 핵심**: collaboration_preference의 반대말이 아니다 —
  협업하면서도 판단은 스스로 내릴 수 있다는 게 핵심이라, 질문 상황이 "혼자 vs 함께"를
  묻지 않고 "함께 하는 상황에서도 판단의 주체가 누구인가"를 물어야 한다. opinion_
  expression(판단을 표현·주장하는 것)과도 다르다 — independent_judgment는 "판단을
  내리는 과정" 자체이고, 표현 여부와는 별개다(판단은 스스로 내리지만 말은 안 할 수도
  있다).
- **질문 설계 시 오판 가능성**: "내 의견을 적극적으로 말한다"류 선택지는 opinion_
  expression과 겹친다 — "말했는가"가 아니라 "누구의 판단을 따랐는가"로 응답이 갈려야
  한다. "혼자 하고 싶다"류 선택지는 collaboration_preference와 겹친다 — 협업 여부가
  아니라 판단 주체를 물어야 한다.

## uncertainty_tolerance (불확실성 감내)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 2개(game Seed, problem_response_v1
  Blueprint) — 신규 12개 중 RELATED 관찰이 가장 적은 편에 속한다.
- **현재 연결 Context**: game, media, school_life(Tail Blueprint 경유로 구조적 도달은
  가능하나, 실제 RELATED 등록은 game Seed 1곳뿐이다).
- **현재 연결 Frame**: seed_frame + problem_response_v1 소속 Frame 전체.
- **PRIMARY 질문 필요 여부**: 필요.
- **가능한 질문 Context 2개**: game(결과를 알 수 없는 새 시도를 확신 없이도 진행하는
  상황), media(반응을 예측할 수 없는 콘텐츠를 일단 만들어 올리는 상황).
- **서로 다른 질문 Frame 2개**: `new_tool`(새로운 도구가 주어지면 — "써본 적 없어 결과를
  모르는 상태에서도 일단 진행한다"), `first_action`(가장 먼저 무엇을 하고 싶은가 —
  "확실하지 않아도 불안해하지 않고 시작한다").
- **기존 Trait와 구별해야 할 핵심**: change_adaptation은 "예상과 다른 결과가 나온 뒤"의
  대응이고, uncertainty_tolerance는 결과가 나오기 "전" 불확실한 상태 자체를 견디는
  것이다 — 질문 상황은 반드시 "아직 결과를 모르는 시점"이어야 하고, "결과를 본 뒤
  바꾼다"는 change_adaptation 쪽으로 넘어간다.
- **질문 설계 시 오판 가능성**: "일단 시도해본다"류 선택지는 immediate_execution과
  겹치기 쉽다 — 행동의 신속함이 아니라 "불확실함에도 불안해하지 않는 심리적 태도"가
  드러나는 문구가 필요하다(예: "결과를 몰라도 크게 신경 쓰지 않는다" 같은 태도 표현).

## opinion_expression (의견 표명)

- **현재 Signal 상태**: PRIMARY 0개, RELATED 4개.
- **현재 연결 Context**: game, media, school_life.
- **현재 연결 Frame**: seed_frame, backup, expression_and_audience_v1 소속 Frame 전체.
- **PRIMARY 질문 필요 여부**: 필요.
- **가능한 질문 Context 2개**: school_life(조별 활동에서 의견이 갈릴 때 자기 생각을
  먼저 말하는 상황), media(콘텐츠에 대한 자기 의견을 사람들 앞에서 밝히는 상황).
- **서로 다른 질문 Frame 2개**: `conflicting_opinions`(여러 의견이 충돌하면 무엇을
  기준으로 결정하는가 — "내 생각을 먼저 분명히 말한다"), `team_role`(팀 활동에서는
  어떤 역할을 맡고 싶은가 — "생각이 있으면 먼저 나서서 제안하는 역할을 맡는다").
- **기존 Trait와 구별해야 할 핵심**: opinion_mediation은 "여러 의견이 충돌할 때 조율
  기준을 세우는 것"이고, opinion_expression은 조율 여부와 무관하게 "자기 의견 자체를
  드러내는가"다 — 질문 상황에 "조율/절충"이 아니라 "내 생각을 드러내는가"에 초점을
  맞춰야 한다.
- **질문 설계 시 오판 가능성**: "다른 의견들을 절충한다"류 선택지는 opinion_mediation과
  겹친다 — "절충안을 만드는가"가 아니라 "내 의견을 먼저 밝히는가"로 응답이 갈려야 한다.
  independent_judgment(판단의 주체)와도 겹칠 수 있다 — opinion_expression은 "표현
  여부"이므로, "판단을 스스로 내렸는가"가 아니라 "그 판단을 남 앞에서 말했는가"가
  선택지에 분명히 드러나야 한다.

---

## 종합

7개 Trait 중 5개(systems_thinking, detail_orientation, persistence_completion,
uncertainty_tolerance, opinion_expression)는 이미 RELATED Signal이 있어 PRIMARY 질문을
추가하면 비교적 빠르게 DIRECTLY_MEASURABLE로 승격될 수 있는 후보다. 나머지 2개
(creative_ideation, independent_judgment)는 현재 Registry에 전혀 등록돼 있지 않아
(NOT_PROBED) PRIMARY 질문 없이는 아예 관찰이 불가능하다 — 2단계에서 우선순위를 정할 때
"이미 RELATED가 있는 Trait부터 PRIMARY로 승격"과 "전혀 없는 Trait를 새로 여는 것" 중
어느 쪽을 먼저 할지는 사용자 판단이 필요하다(완료 보고 §29 참고).
