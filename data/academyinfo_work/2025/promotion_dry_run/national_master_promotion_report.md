# 전국 학과 Master 승격 후보 v2 — 2025년

**이 문서는 후보 목록·통계 보고서다. `data/master/departments.jsonl`은 이 산출물로
바뀌지 않았다 — 기존 35건은 Migration 완료 전까지 그대로 유지한다.**

## 요약

- 기존 Master 행 수: 35건
- 신규 승격 후보 행 수: 1072건
- 후보 중 offering_id 중복: 0건
- 신규 후보가 걸치는 대학 수: 158개
- 신규 후보 중 기존 Master 35건과 old_department_id(표시명 그룹)를 공유하는 건수: 0건(감사 참고용)

## Major별 신규 후보 수

| Canonical Major | 후보 수 |
|---|---|
| business_administration | 271 |
| computer_science | 209 |
| life_science | 134 |
| media_communication | 133 |
| mechanical_engineering | 114 |
| psychology | 80 |
| education | 78 |
| industrial_engineering | 53 |

## Dry Run 차단 사유별 수(참고, §5 결과 그대로 인용)

| 사유 | 개수 |
|---|---|
| BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR | 0 |
| BLOCKED_ARTS_RECOMMENDATION | 3637 |
| BLOCKED_BRIDGE_EXCLUDED_RECOMMENDATION | 0 |
| BLOCKED_BRIDGE_MAPPING_REVIEW | 0 |
| BLOCKED_BRIDGE_SCOPE_REVIEW | 0 |
| BLOCKED_CLASSIFICATION_REVIEW | 0 |
| BLOCKED_CONTRACT_DEPARTMENT | 325 |
| BLOCKED_DUPLICATE_ID | 0 |
| BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION | 6711 |
| BLOCKED_GROUP_DRAFT | 0 |
| BLOCKED_INACTIVE_STATUS | 14582 |
| BLOCKED_MISSING_CLASSIFICATION | 0 |
| BLOCKED_MISSING_LINEAGE | 0 |
| BLOCKED_NCE_UNRESOLVED | 0 |
| BLOCKED_NIGHT_OR_REMOTE | 388 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 11856 |
| BLOCKED_OUTSIDE_SMALL_SERIES_SCOPE | 1866 |
| BLOCKED_OUT_OF_RECOMMENDATION_SCOPE | 0 |
| BLOCKED_P1_REVIEW_UNRESOLVED | 0 |
| BLOCKED_URL_POLICY | 0 |

## 재생성 명령

```
PYTHONPATH=. ./.venv/bin/python scripts/career_build_national_master_promotion_candidates.py --survey-year 2025 --data-dir /Users/jaewan/Documents/Codex/2026-08-17/final-integration-master-promotion/data
```

