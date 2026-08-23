# LLM 자동 검수 vs 사람의 독립 검토 — 경계 문서

2026-08-23 Trait Ontology v2(2.3단계) §5. 이 문서는 "무엇을 이미 확인했고 무엇은 아직
아무도 확인하지 않았는지"를 명확히 하기 위한 것이다. 특히 다음 문장을 정정한다:

> **"실제 LLM 경로로 생성됨: 28/28"은 "질문 타당성 검증 완료"를 의미하지 않는다.**

`outputs/evaluation/v2_direct_probe_llm_quality_report.md`의 28/28은 "LLM이 실패하거나
Fallback으로 넘어가지 않고 실제로 Structured Output을 생성했다"는 뜻일 뿐이다. 그
Sample들이 실제로 좋은 질문인지, Trait를 제대로 구분하는지, 자연스러운지는 그
보고서의 '문장 자연스러움 검토'/'인접 Trait 혼동 가능성'/'사람 검토 상태' 열이 항상
`TBD`로 남아 있는 것에서 이미 드러나듯 **아직 아무도 확인하지 않았다.**

## LLM 자동 검수가 실제로 확인하는 것

`src/engines/question_quality_gate.py::run_quality_gate()`(하드 실패 — LLM 출력을 그
자리에서 거부) + `src/engines/v2_direct_probe_quality_checks.py`(Advisory — 검토 후보
표시만, 아무것도 자동 승격하지 않음)가 기계적으로 확인하는 항목:

- JSON/Schema 준수 (`GeneratedQuestion`/`QuestionGenerationResult` Pydantic 검증)
- 선택지 개수(정확히 5개), Role ID 집합이 Blueprint와 일치
- 금지 표현(Trait Label 노출, "편인가요"/"어떤 사람인가요" 같은 자기평가 문구,
  "역할을 맡고 싶"은 역할선호형 문구)
- 질문 문장이 물음표로 끝나는 선택지가 없는지 같은 형태적 자연스러움의 **1차** 검사
  (진짜 자연스러움 판단이 아니라 "명백히 이상한 형태"만 걸러낸다)
- Role 및 Trait ID가 실제 Ontology/Blueprint에 존재하는지
- 극단 표현("항상"/"무조건"/"절대"/"아무도 안 해본"), 선택지 길이 편차, Target
  Option 길이 이상치 탐지(2.3단계 §3에서 실제로 이 신호를 근거로 7개 문구를 수정했다
  — 하지만 "길이가 정상 범위"라는 사실이 "내용이 타당하다"를 보장하지 않는다)

## 사람의 독립 검토만 확인할 수 있는 것

다음은 LLM Quality Gate나 이 라운드의 어떤 자동 스크립트도 판정하지 않는다 — 지금
`outputs/reviews/v2_direct_probe_question_review.md`(70행)와
`outputs/reviews/v2_direct_probe_human_review_guide.md`(14문항)의 모든 검토 상태
열이 `TBD`/`DRAFT`로 남아 있는 이유가 바로 이것이다.

- 질문이 실제로 해당 Trait를 다른 Trait와 구분해서 관찰하는가(같은 상황에서 인접
  Trait로도 자연스럽게 읽히지는 않는가)
- 사회적으로 바람직한 답을 유도하는가(Target Option이 "더 성숙한 답"처럼 보이는가)
- PRIMARY·RELATED·NO_SIGNAL Mapping이 실제 문장의 행동과 타당하게 연결되는가(특히
  NO_SIGNAL로 표시한 14개가 정말 "근거 불명확"이 맞는지)
- Trait 간 개념적으로 과도하게 겹치지 않는가(예: independent_judgment vs
  opinion_expression처럼 같은 상황에서 둘 다 나올 수 있는 조합)
- 고등학생이 자연스럽게 이해할 수 있는 문장인가(또래 언어로서의 자연스러움 — LLM이
  생성한 표현이 형식적으로는 정상이어도 실제로 자연스럽게 읽히는지는 다른 문제다)

## 이번 라운드(2.3단계)에서 이 경계를 지킨 방식

- `outputs/reviews/v2_direct_probe_target_length_review.md`(§3 길이 이상치 수정)는
  "정량적 길이 이상치가 사라졌다"는 사실만 검증했다고 명시하고, 문서 자체의 최종
  `상태`를 `REVIEW_REQUIRED`로 남겼다 — 스스로 "타당성 검증 완료"라고 쓰지 않았다.
  Trade-off 압축이 실제로 자연스러운 한국어인지, 원래 사회적 바람직성 완화 의도를
  훼손하지 않았는지는 사람이 읽어야 한다.
- `data/reviews/v2_direct_probe_question_review_status.json`/
  `v2_direct_probe_option_review_status.json`(§4 Validator)은 `reviewer_1_status`/
  `reviewer_2_status`가 둘 다 `APPROVE`일 때만 `final_status`가 `TEAM_REVIEWED`로
  계산되게 강제한다 — LLM 통과나 자동 검사 결과는 이 계산에 전혀 들어가지 않는다.
- `scripts/validate_v2_direct_probe_review_status.py`는 이미 `team_reviewed`로
  승격된 Blueprint가 있다면 그 승격이 실제 두 검토자 상태와 일치하는지만 확인한다 —
  검토 자체를 대신하지 않는다.

## 남는 위험

이 문서 자체도 "경계를 문서화했다"는 사실만 보장한다 — 실제로 팀원 두 명이
Worksheet/Human Review Guide를 읽고 각 항목에 `APPROVE`/`REVISE`/`HOLD`를 채워
넣기 전까지는, 이 코드베이스의 어떤 자동화도 "이 14개 질문이 실제로 타당하다"고
주장하지 않는다.
