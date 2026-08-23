# ContextPack Context별 질문 Runtime Report

2026-08-23 Trait Ontology v2(2.9단계) §12 — `PYTHONPATH=. python scripts/career_generate_context_pack_question_runtime_report.py`로 재생성한다. `저장된 질문 은행 수`는 Context 제작 에이전트가 채운 전체 후보 수이고, `실제 최소·최대 응답 질문 수`는 학생 한 명이 Anchor 하나를 고른 뒤 실제로 답하는 개수다(Routing 1개는 어느 쪽에도 포함하지 않는다 — Trait Evidence를 만들지 않기 때문이다).

| Context | Routing 은행 | Seed 은행 | Adaptive Blueprint 은행(자체+공용) | Backup 은행 | 최소 응답(설계상) | 최대 응답(설계상) | 현재 실제 최소·최대(검수 상태 반영) | PRIMARY Trait 수 | RELATED-only 수 | NO_SIGNAL 수 |
|---|---|---|---|---|---|---|---|---|---|---|
| 미술·디자인(art_design) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 14 | 0 | 14 |
| 창업·비즈니스(business) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 14 | 0 | 10 |
| 요리·음식(cooking) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 14 | 0 | 14 |
| 패션·뷰티(fashion_beauty) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 13 | 0 | 16 |
| 역사·인문학(history_humanities) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 11 | 0 | 10 |
| 법·정치·시사(law_politics) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 14 | 0 | 10 |
| 만들기·코딩(making) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 15 | 0 | 10 |
| 과학탐구(science) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 16 | 0 | 10 |
| 스포츠(sports) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 17 | 0 | 12 |
| 여행·문화탐방(travel) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 17 | 0 | 10 |
| 봉사·사회참여(volunteer) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 18 | 0 | 10 |
| 글쓰기·독서(writing) | 1 | 5 | 0+14 | 5 | 5 | 7 | 미승인(Fail-Closed) — 서빙 안 됨 | 19 | 0 | 10 |

## 공용 Adaptive Probe Blueprint 은행

- 전체 14개, 신규 12개 Context 전부에 `allowed_context_ids`로 노출됨(§5 — 12개 Context × 개별 Blueprint를 새로 만들지 않고 공유한다).
- 현재 reviewer_1 APPROVED: 0개(모든 신규 Context에 공통 적용되므로 어느 Context 기준으로 세도 같다).

## 참고: 저장된 질문 은행 수 ≠ 학생 응답 수

예를 들어 Seed 은행 5개는 Anchor 5개 각각 전용이라 학생 한 명은 그중 정확히 1개만 받는다. Adaptive Blueprint 은행도 마찬가지로 전체 후보 목록이고, 실제로는 그중 최소 4개·최대 6개만 그 학생에게 순차적으로 제시된다(§4 최소·최대 정책, `evidence_engine.decide_stop_or_continue` 재사용).
