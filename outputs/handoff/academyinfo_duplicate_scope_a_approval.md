# 대학알리미 일반과정·계약학과 관계 검수 — A 승인 결과

검수일: 2026-08-24
검수 정본: `data/reviews/academyinfo_duplicate_scope_review_status.jsonl`

## 결론

대학알리미 공식 `major_character_name`, `schlMjrId`, 수업연한을 근거로 중복 후보
6그룹을 모두 서로 다른 과정으로 확인했다.

- 일반과정 6건: `IN_RECOMMENDATION_SCOPE`
- 계약학과 6건: `OUT_OF_RECOMMENDATION_SCOPE / CONTRACT_DEPARTMENT`
- 관계 판정: `DISTINCT_DEPARTMENTS_KEEP_SEPARATE`
- 사람 검수 상태: 6건 모두 `APPROVE / CONFIRMED`

계약학과는 폐지학과로 바꾸거나 원본에서 삭제하지 않는다. Raw·Lineage·Audit에는
`EXISTING` 상태와 원래 식별자를 보존하고, 학생 대상 추천 후보에서만 제외한다.

## 확인한 6그룹

| 학교 | 학과 | 일반과정 schlMjrId | 계약학과 schlMjrId | 판정 |
|---|---|---:|---:|---|
| 서경대학교 | 코스메틱뷰티매니지먼트학과 | 0246788 | 0246874 | 일반 유지·계약 제외 |
| 서경대학교 | 헤어디자인학과 | 0232771 | 0232745 | 일반 유지·계약 제외 |
| 충남대학교 | 약학과 | 0010025 | 0220559 | 6년 일반 유지·4년 계약 제외 |
| 한일장신대학교 | 사회복지학과 | 0224303 | 0019547 | 일반 유지·계약 제외 |
| 원광대학교 | 약학과(2+4학제) | 0009123 | 0009574 | 일반 유지·계약 제외 |
| 동신대학교 | 사회복지학과 | 0016970 | 0011969 | 일반 유지·계약 제외 |

## 정본 분리 원칙

`data/academyinfo_work/2025/packets/duplicate_decision_draft.jsonl`은 생성기로 다시
만들 수 있는 검수 입력 패킷이므로 `TBD / PENDING` 상태를 유지한다. 사람의 최종 결정은
별도 검수 정본인 `data/reviews/academyinfo_duplicate_scope_review_status.jsonl`에만
기록한다. Loader는 두 파일의 candidate ID, department ID, source record ID,
`schlMjrId`, 과정 유형과 추천 범위가 정확히 일치하는지 Fail-Fast로 검증한다.

## 승인 시점 통계

- 주간 학사과정 정규화 전체: 24,422
- 현재 상태 후보: 10,063
- 계약학과 제외 후 추천 후보: 10,057
- 승인 가능 후보: 5,449
- 추천 후보 중복 `department_id`: 0
- 추천 승격 검토 Queue: 3,837

기존 35건 시연 Master와 공개 API·Mock은 이번 승인으로 변경하지 않는다.
