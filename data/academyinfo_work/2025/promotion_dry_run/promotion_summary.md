# 전국 학과 Master 승격 Dry Run — 2025년

**이 문서는 계산 결과 보고서다. `data/master/departments.jsonl`·공개 API는
바뀌지 않았다.**

## 요약

- 평가 대상: 24794건
- READY_FOR_PROMOTION: 5595건
- BLOCKED: 19199건
- 현재 검수 상태(TBD/미존재)만으로 막힌 건: 0건

## 차단 사유별 개수

| 사유 | 개수 |
|---|---|
| BLOCKED_AMBIGUOUS_SERVICE_CANONICAL_MAJOR | 0 |
| BLOCKED_ARTS_RECOMMENDATION | 3637 |
| BLOCKED_CLASSIFICATION_REVIEW | 0 |
| BLOCKED_CONTRACT_DEPARTMENT | 325 |
| BLOCKED_DUPLICATE_ID | 0 |
| BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION | 6640 |
| BLOCKED_GROUP_DRAFT | 0 |
| BLOCKED_INACTIVE_STATUS | 14582 |
| BLOCKED_MISSING_CLASSIFICATION | 0 |
| BLOCKED_MISSING_LINEAGE | 0 |
| BLOCKED_NCE_UNRESOLVED | 0 |
| BLOCKED_NIGHT_OR_REMOTE | 388 |
| BLOCKED_NO_SERVICE_CANONICAL_MAJOR | 135 |
| BLOCKED_OUT_OF_RECOMMENDATION_SCOPE | 0 |
| BLOCKED_P1_REVIEW_UNRESOLVED | 0 |
| BLOCKED_URL_POLICY | 0 |

## 상태별 표본(최대 10건)

### READY_FOR_PROMOTION 표본

- off_000629788ed55204cf4b7fd9 — 국립금오공과대학교 기계공학부 스마트모빌리티전공 → mechanical_engineering
- off_000e915a593f0581e011e464 — 국립강릉원주대학교 다문화학과 → social_welfare
- off_000f78e43bf7c0f5b3d68127 — 우송대학교 물류시스템학과 → industrial_engineering
- off_0025f7aadf66e31dcf4ac4e8 — 경희대학교 미래정보디스플레이학부 → physics_astronomy
- off_002b01f310e95b34b977aeef — 전주대학교 보건관리학과 → health_science
- off_002c2dd8853bc5355abbc459 — 서원대학교 범죄수사전공 → public_administration
- off_002dd17a7f7f20a21c7df2d7 — 영남대학교 [외국인유학생]새마을국제개발학전공 → political_science
- off_003d8f86a56f9ba4bb68b428 — 계명대학교 유아교육과 → education
- off_0044a0a38ab9466ec7638850 — 남부대학교 유아교육과 → education
- off_004e6ecfb8d482221781da99 — 이화여자대학교 영어영문학부 → foreign_language

### BLOCKED 표본

- off_00024115b1e683c2d8cdc111 — 극동대학교 초등특수교육전공: BLOCKED_INACTIVE_STATUS
- off_00054fac0452a5ab078912f2 — 경기대학교 응용통계학과: BLOCKED_INACTIVE_STATUS
- off_0005f8e765f3e3773887a9a9 — 서울한영대학교 음악예술학부: BLOCKED_ARTS_RECOMMENDATION, BLOCKED_INACTIVE_STATUS
- off_000787f6f3921a2b89a6e3ca — 제주대학교 관광경영관광개발학학과군: BLOCKED_INACTIVE_STATUS
- off_0007bfeb08c58d439c460e88 — 국립한국교통대학교 IT응용융합학과(4년제): BLOCKED_CONTRACT_DEPARTMENT, BLOCKED_INACTIVE_STATUS, BLOCKED_NIGHT_OR_REMOTE
- off_000b7883aa0071c8a869ac54 — 협성대학교 산업디자인학과: BLOCKED_ARTS_RECOMMENDATION
- off_000d9a10a13311ba180518de — 서울여자대학교 식품영양학전공: BLOCKED_INACTIVE_STATUS
- off_0010359e1c921154d2b48cc4 — 동양대학교 실내디자인학과: BLOCKED_ARTS_RECOMMENDATION, BLOCKED_INACTIVE_STATUS
- off_00119c59d14f33a5f7f9cddf — 강원대학교 메카트로닉스전공: BLOCKED_INACTIVE_STATUS
- off_00137048194969a22a4fc484 — 한신대학교 국제관계전공: BLOCKED_EXCLUDED_FROM_INITIAL_PROMOTION, BLOCKED_INACTIVE_STATUS

## 재생성 명령

```
PYTHONPATH=. ./.venv/bin/python scripts/career_build_national_department_promotion_dry_run.py --survey-year 2025 --data-dir /Users/jaewan/Documents/Codex/2026-08-17/national-departments-38-majors/data
```

