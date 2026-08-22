# 데이터 품질 검사 결과 (작업자 C)

생성 2026-08-22 · ERROR 0 / WARN 1 / INFO 12

| 등급 | 검사 | 대상 | 내용 |
|---|---|---|---|
| WARN | admission_draft_only | data/admissions/admission_references.jsonl | 39행이 draft다 — 화면 비교에 쓰려면 verified 승격이 필요하다 |
| INFO | admission_cut_pending | data/admissions/admission_references.jsonl | 39행의 컷 점수가 비어 있다 — 출처 미확정 상태에서 숫자를 채우지 않는다 |
| INFO | major_profile_draft | computer_science | A 검토 전 초안이다 |
| INFO | major_profile_draft | media_communication | A 검토 전 초안이다 |
| INFO | major_profile_draft | design | A 검토 전 초안이다 |
| INFO | major_profile_draft | business_administration | A 검토 전 초안이다 |
| INFO | major_profile_draft | psychology | A 검토 전 초안이다 |
| INFO | major_profile_draft | mechanical_engineering | A 검토 전 초안이다 |
| INFO | major_profile_draft | education | A 검토 전 초안이다 |
| INFO | major_profile_draft | life_science | A 검토 전 초안이다 |
| INFO | rag_sample_documents | data/rag/sources.jsonl | 5건이 공식 자료가 아니라 파이프라인 검증용 샘플이다 (source_url이 sample://로 시작해 공식 출처와 섞이지 않는다) |
| INFO | review_required_present | data/master/canonical_mapping_review_required.jsonl | 1건이 REVIEW_REQUIRED로 남아 있다 — A 검토 대상 |
| INFO | schl_id_placeholder | data/raw/departments.raw.jsonl | 30개 학과의 schl_id가 임시값이다 — 대학알리미 API Key 발급 시 전부 재생성되며 department_id도 바뀐다 |
