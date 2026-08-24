# 질문 → Trait → 소수 전공 매칭 추적

이 평가는 A의 질문 생성·종료 로직과 Matching Engine을 수정하지 않는다. C가 만든 고정 질문에서 답변을 먼저 선택하고, 그 선택이 만든 Trait만 현재 엔진에 넣었다. 관광·호텔 Profile은 공개 Master가 아닌 `REVIEW_REQUIRED` 평가 가설이다.

## 1. 질문과 답변이 어떤 Trait 근거가 되는가

| Context | 질문 | 선택 답변 | 연결 Trait |
|---|---|---|---|
| travel | 여행이나 답사를 준비할 때, 어떤 부분에 가장 공을 들이나요? | 동선과 일정을 미리 촘촘히 짜 두는 것 | `planning` |
| cooking | 요리를 할 때, 어떤 과정이 가장 재미있나요? | 재료 손질 순서와 시간을 미리 배분하는 것 | `planning` |
| fashion_beauty | 옷차림이나 스타일을 정할 때, 어떤 쪽에 더 신경이 쓰이나요? | 다른 사람 눈에 어떻게 비칠지 가늠하는 것 | `audience_response_prediction` |
| writing | 글을 읽거나 쓸 때, 어떤 작업에 가장 오래 머무르게 되나요? | 읽는 사람이 어떻게 받아들일지 떠올려 보는 것 | `audience_response_prediction` |
| science | 과학 실험이나 관찰 활동에서 가장 재미있는 부분은 무엇인가요? | 자료를 여러 곳에서 찾아 비교해 보는 것 | `information_comparison` |
| law_politics | 사회 이슈나 시사 문제를 볼 때, 무엇을 먼저 하게 되나요? | 여러 매체의 보도를 찾아 견줘 본다 | `information_comparison` |
| history_humanities | 역사나 인문학 주제를 볼 때, 어떤 질문이 먼저 떠오르나요? | 그때 사람들은 어떤 심정이었는지 | `emotional_interpretation` |
| volunteer | 봉사나 사회참여 활동을 할 때, 어떤 순간이 가장 기억에 남나요? | 도움받는 사람이 실제로 뭘 필요로 하는지 알아챌 때 | `emotional_interpretation` |

같은 Trait가 서로 다른 Context에서 두 번 이상 관찰된 경우만 매칭 입력으로 사용했다.

- `audience_response_prediction`: support 2회 / context 2개
- `emotional_interpretation`: support 2회 / context 2개
- `information_comparison`: support 2회 / context 2개
- `planning`: support 2회 / context 2개

## 2. 현재 Matching Engine 결과

| 전공 | 상태 | 내부 진단 점수 | 사용 Trait 수 | 사용 Vector 그룹 수 |
|---|---|---:|---:|---:|
| 미디어·커뮤니케이션 | computed | 0.6700 | 3 | 2 |
| HCI·UX | insufficient | — | 1 | 1 |
| 산업공학 | insufficient | — | 2 | 2 |
| 관광·호텔(평가용 draft) | computed | 0.6700 | 4 | 3 |

## 3. 이 결과가 증명하는 것과 남은 Gate

- 질문 선택에서 전공 점수까지 어떤 Trait가 사용됐는지 행 단위로 추적할 수 있다.
- 대표 전공 목록에 관광·호텔 Profile이 없으면 해당 학생은 구조적으로 그 결과를 받을 수 없다.
- 평가용 Profile을 넣으면 기존 엔진이 소수 전공도 계산할 수 있어 기술적 확장 경로는 확인된다.
- 이 시나리오에서는 관광·호텔과 미디어·커뮤니케이션이 0.6700으로 동점이다. 후보 추가만으로 분야 간 변별력이 생기지는 않으며 경계 Persona 평가가 필요하다.
- 점수는 후보 정렬 진단값이지 학생 적합 확률이 아니다.
- 관광·호텔 Vector는 공식 교육과정으로 검수되지 않았으므로 공개·Master 승격은 금지한다.

**승격 Gate:** 서로 다른 대학 5개 이상의 공식 교육과정으로 Trait 근거를 대조하고, 호텔/관광·경영·무역 물류 경계 Persona를 블라인드 평가한 뒤 reviewer 승인을 받아야 한다.
