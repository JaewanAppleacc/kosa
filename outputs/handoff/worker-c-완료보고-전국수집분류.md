# 작업자 C 완료 보고 ② — 대학알리미 전국 수집·정규화·분류

작성 2026-08-24 · 브랜치 `worker-c` · A 지시서 §12 형식
설계 근거 전문: `rationale_c/07-academyinfo-collection.md` (26항목)
이전 보고: `worker-c-완료보고-대학알리미수집.md`

---

# A가 판단해야 할 것 — 4건

## ① §4 연도 비교는 수행 불가 — 대안 선택 필요

**A 지시 §4를 실행할 수 없다.** 2024년치를 전국 수집했더니 학과가 0건이었다.

```
완료 — 대학 376개 · 학과 0건 · 실패 0개 대학 · API 호출 398회
```

오류가 아니라 정상 빈 응답(`NODATA_ERROR`)이다. 표본 확인 결과:

```
svyYr=2025  schlId=0000149 → 135건
svyYr=2024  schlId=0000149 →   0건
svyYr=2023  schlId=0000149 →   0건
```

**원인: 두 오퍼레이션이 서로 다른 서비스이고 연도 범위가 다르다.**

```
getComparisonPubYear     BasicInformationService_2 (대학 비교통계) → [2025, 2024, 2023]
getUniversityMajorCode   BasicInformationService_1 (학과)          → 2025만
```

C가 앞 서비스의 연도 목록을 학과 서비스에도 적용한 것이 잘못이었다. §7-16에서
"실제 API 응답만 정본"이라고 써 놓고 **한 API의 응답을 다른 API의 정본으로 쓴** 같은
종류의 실패다.

**따라서 다음이 전부 보류된다.**

- `schlMjrId` 유지율 — 계산 불가
- 학과명 변경·신설·폐지·통합·분리 추적 — 불가
- `department_id` 원본 키 검증(§7-8·§7-17에서 "두 해 비교 후 확정"으로 열어 둔 것)

`department_lineage.jsonl`은 **생성되지 않았다.** 구현과 테스트는 그대로 있어 데이터가
생기면 즉시 돌아간다.

**대안 3안 — A 선택 필요.**

| | 방법 | 비용 | 비고 |
|---|---|---|---|
| 1 | **파일 데이터셋 사용**(권고) | 스키마 매핑 1회 | `교육부_대학알리미_학교별 학부·학과(전공) 리스트`는 2014년부터 연도별 제공. Key 불필요 |
| 2 | 다음 공시까지 대기 | 시간 | 2026 공시가 열리면 2025 vs 2026 |
| 3 | 비교 없이 승격 | 위험 이월 | 중복 588건을 검토 대기로 둔 채 진행, 안정성은 다음 공시에 검증 |

**재발 방지는 이미 넣었다.** 수집 전에 표본 3건으로 학과 데이터 존재를 확인하고, 없으면
`MajorDataUnavailableError`로 즉시 중단한다. 이번엔 398콜을 쓰고 알았지만 3콜이면 됐다.
테스트가 "표본 호출 3회 이하"를 고정한다.

## ② 대표 전공군 40개 초안 — 검토 필요

`data/canonical_major_groups.draft.jsonl`. 전부 `review_status: draft`다.

**설계 기준.** 대학알리미 **중계열 28개를 뼈대**로 삼았다(공식 분류라 근거가 붙고, 이미
20~40 범위 안이다). 다만 이름이 학생 기준이 아니라 아래처럼 쪼갰다.

```
중계열 15 "전기·전자·컴퓨터"   → 컴퓨터·소프트웨어·AI / 전기·전자·정보통신 / 반도체·신소재
중계열 24 "의료"               → 의학 / 치의학 / 한의학 / 수의학
중계열 07 "화학·생명과학·환경" → 화학 / 생명과학 / 지구·지리·환경
```

진로가 거의 안 갈리는 것은 합쳤다(금융·회계 → 경영학, 국제·지역학 → 정치외교학).
합친 이유는 전부 `boundary_cases`에 문장으로 남겼다.

**교양 소계열 5개는 전공군에서 뺐다** — `교양인문학`·`교양공학` 등은 학부대학 교양과정
단위지 학생이 지원하는 학과가 아니다. 넣으면 "교양학과"를 추천하게 된다.

**소계열 다중 배정 0건.** 한 소계열이 두 전공군에 걸리지 않게 설계했다. 겹치게 뒀다면
그 소계열의 학과 전부가 매번 `REVIEW_REQUIRED`로 갔을 것이다.

**A가 볼 지점:** 40개는 상한에 붙어 있다. 더 쪼개야 할 군이 나오면 합칠 것을 함께 찾아야
한다. 지금 합쳐 둔 것 중 `무역·유통·관광`과 `생활과학(식품·의류·주거)`이 가장 이질적이라
1순위 분리 후보다.

## ③ 검토 대기 물량이 실측으로 확정됐다

착수 전 "수천 건"이라고만 알던 숫자가 나왔다.

| 검토 대상 | 건수 | 성격 |
|---|---|---|
| 융합·디자인·미디어 명칭 (Fail-Closed) | 4,454 | 이름만으로 예체능 여부 확정 금지 → 공식 교육과정 확인 필요 |
| N.C.E 미분류 | 3,657 | 대학이 공식 분류를 넣지 않음 |
| `department_id` 중복 | 588 | 같은 학과가 여러 원본 행 |

**자동 후보 비율 85.0%** — 21,590 / 25,389. 나머지가 위 물량이다.

## ④ 이전 보고의 미결 1건 — 단과대학 URL 3건

`worker-c-완료보고-대학알리미수집.md` ①의 경계 사례가 아직 미결이다. A의 "학과 URL로
인정하지 않는 것" 목록에 "단과대학"이 없어서, 중앙대 디자인학부(`arts.cau.ac.kr`)·
고려대 경영학과(`biz.korea.ac.kr`)·성균관대 소프트웨어학과(`sw.skku.edu`)를 허용할지
판단이 필요하다.

**A 지시 §8에 따라 공개 Schema 변경은 전부 되돌렸다.** `src/schemas/major.py`와 계약
테스트 3개를 원본으로 복귀시켰고, `source_dataset`은 공개 API에 넣지 않았다.
`department_url` 값 37건은 `data/raw/departments.raw.jsonl`에 보존돼 있어, A가 Schema에
필드를 추가하면 빌더 한 줄로 흘러간다.

---

# 지시서 §12 보고 항목

## 1. 공공데이터포털 수정일과 조사연도 구분

```
포털 수정일   2026-05-04   API 상품·명세가 언제 고쳐졌나
웹 화면 연도  2026 있음    대학알리미 웹이 무엇을 보여주나
API 지원연도  2025/2024/2023  API가 실제로 무엇을 주나  ← 수집기가 쓰는 것
```

앞의 둘은 근거로 쓰지 않았다. Manifest에 셋을 함께 기록해 판단 과정을 되짚을 수 있게 했다.

## 2. 실제 API 지원연도

`getComparisonPubYear` → `[2025, 2024, 2023]`. **2026은 지원하지 않는다.**

단, ①에서 밝혔듯 이 목록은 **대학 비교통계 서비스의 것**이고 학과 서비스는 2025만 있다.

## 3. 선택한 최신 조사연도

**2025.**

## 4. 2025를 선택한 이유

A 정책의 "2026 미지원, 2025까지 지원 → 2025 전국 학과 수집" 분기.
연도를 코드에 박지 않고 `getComparisonPubYear`에 매번 물어 최신값을 고른다.
지원연도를 하나도 못 받으면 기본값으로 넘어가지 않고 구조화 오류로 멈춘다.

## 5. 수집 대학·캠퍼스·학과 수

```
대학(캠퍼스 별도 schlId)  377개
학과                      36,866건
실패 대학                 0개
API 호출                  615회 (한도 10,000/일)
원본 용량                 136MB
```

정규화 후 대학 217개 — 4년제 학사 학과가 하나도 없는 학교(전문대 등)가 빠진 결과다.

## 6. 실패·Quota·Resume 결과

실패 0. Quota 도달 없음. Resume 미사용(중단 없이 완료).
`collection_errors.jsonl` 비어 있음.

## 7. 4~7년 학사과정 포함·제외 수

**포함 25,389 / 제외 11,477.**

```
전문대학        10,851   학교종류 코드로 판정 (학교명 추측 안 함)
교육대학           194
수업연한 2년       250
수업연한 3년       113
학석사통합          36
수업연한 3.5년      13
수업연한 1년        15
기타                 5
```

제외 행은 삭제하지 않고 `excluded_records.jsonl`에 **판정에 쓴 공식 필드와 사유**를 함께
남겼다. 기준이 바뀌면 재수집이 아니라 이 파일만 다시 읽어 재판정한다.

## 8. 최신·직전연도 schlMjrId 유지율

**계산 불가.** → ①

## 9. source_record_id / department_id 결과

```
source_record_id  schlId + schlMjrId + 조사연도   (연도 포함)
department_id     학교 + 정규화 학과명 + 단과대학 (연도 제외, 기존 규칙 유지)
```

`src/ids.py`는 A 소유라 수정하지 않았다. `schlMjrId`를 `department_id`로 채택하지 않았다 —
학과 재등록 시 값이 바뀌면 매핑·검토 이력이 끊긴다.

## 10. 중복·변경·Lineage 수

```
department_id 중복        588건 → department_resolution_review_queue.jsonl
lineage                   생성 안 됨 (①)
```

중복은 **자동으로 한 행을 고르지 않았다.** 재학생 수 최대값으로 대표 행을 뽑으면 신설
학과(재학생 0명)가 탈락한다.

## 11. 공식 소계열 수와 N.C.E 수

```
대계열   6      중계열  28 (N.C.E 포함)   소계열  158 (N.C.E 포함)
계열체계 198행 — 복수 소속은 999 N.C.E. 하나뿐. 실제 소계열 157개는 중계열과 1:1
N.C.E 미분류 학과  3,657건
```

`99`/`999`는 분류명이 아니라 미분류 Sentinel로 처리했다.

## 12. 대표 전공군 20~40개 초안

**40개.** → ②

## 13. AUTO 후보 / REVIEW_REQUIRED / UNMAPPED 비율

```
AUTO_CANDIDATE   21,590   85.0%
UNMAPPED          3,799   15.0%   (N.C.E 3,657 + 교양·미배정 142)
REVIEW_REQUIRED       0            소계열 다중 배정 충돌 없음
```

`AUTO_CANDIDATE`는 **확정이 아니라 후보**다. `review_status`는 전부 `draft`다.

## 14. 예체능·융합학과 처리

```
APPROVED                17,268
EXCLUDED_ARTS_SPORTS     3,667   공식 대계열 C(예체능)
REVIEW_REQUIRED          4,454   융합·디자인·콘텐츠·미디어 명칭 → Fail-Closed
```

예체능 학과는 **원본과 분류 결과에 그대로 보존**하고 추천 노출만 제외했다.
상태명은 기존 `department_recommendation_scope`를 그대로 썼고 새 이름을 만들지 않았다.

## 15. 서울대·연세대 컴퓨터 계열 Mapping 예시

```
서울대학교 컴퓨터공학부      → computer_science
고려대학교 컴퓨터학과        → computer_science
고려대학교 인공지능학과      → computer_science
고려대학교 컴퓨터교육과      → education              ← 사범대
서울대학교 전기정보공학부    → electrical_electronic  ← "정보"가 있어도 전자군
```

이름에 "컴퓨터"가 들어가도 공식 소계열 근거로 갈린다. 학과명 문자열 매칭이었으면 전부
컴퓨터군으로 뭉쳤을 것이다.

## 16. source_dataset 미사용 확인

공개 API에 추가하지 않았다. `data/academyinfo_raw/*/collection_manifest.json`의
`official_source_url`로만 관리한다.

## 17. department_url 채움·미채움 수

**전국 수집분은 전부 `None`이다** — API에 학과 홈페이지 필드가 없고, A 지시대로 억지로
채우지 않았다.

시연 데이터 35건은 이전 보고에서 채운 값이 `data/raw/departments.raw.jsonl`에 그대로
있다(공개 Schema 복귀로 Master에는 나가지 않는다).

## 18. 수정 파일

**신규**
```
src/data_sources/academyinfo_year.py          조사연도 동적 선택 + 학과 데이터 표본 검증
src/data_sources/academyinfo_identity.py      source_record_id · lineage · review queue
scripts/career_classify_academyinfo.py        소계열 → 전공군 후보 + Dry Run
data/canonical_major_groups.draft.jsonl       대표 전공군 40개 초안
tests/worker_c/test_academyinfo_year.py           16
tests/worker_c/test_academyinfo_identity.py       13
tests/worker_c/test_academyinfo_classification.py 19
```

**수정**
```
scripts/career_collect_academyinfo_departments.py  연도 자동 선택 · Manifest 확장 ·
                                                   표본 검증 · 원자적 쓰기
scripts/career_normalize_academyinfo.py            source_record_id · lineage · review queue
.gitignore                                         보고서만 커밋되도록 예외
rationale_c/07-academyinfo-collection.md           26항목
```

**수집 중 발견한 버그 (수정 완료).** 대학마다 원본 JSONL을 통째로 다시 쓰면서 대상 파일에
직접 썼다. 그 순간 죽으면 잘린 gz가 남고 Checkpoint는 "완료"라고 말해 `--resume`이
`EOFError`로 죽는다. 실제 수집 중 관측했다. 임시 파일 + 원자적 교체로 고쳤다.
**시연 규모에서는 안 나타나고 전국 규모에서야 드러난 실패 모드**다.

## 19. 테스트 결과

```
python -m unittest discover -s tests -t .
Ran 908 tests — OK      (이번 작업 신규 48개)
```

## 20. 데이터 품질 검사

```
department_id 중복        588 → 검토 대기열 (자동 선택 안 함)
대학 없는 고아 학과         0
학과명·대학명 결측          0
수집 실패 대학              0
소계열 다중 배정 충돌       0
빈 전공군                   0   (40개 전부 실제 학과가 붙음)
```

학과 상태: `ABOLISHED` 14,985 · `EXISTING` 9,275 · `NEW` 1,038 · `MERGED` 57 · `SPLIT` 34.
폐지 학과가 많은 것은 대학알리미가 이력을 함께 주기 때문이고, 지시서대로 **삭제하지 않고
상태와 함께 보존**했다.

## 21. Git에 포함·제외한 파일

```
포함  수집기 · 정규화기 · 분류기 · 전공군 초안 · 코드표 16종 · Manifest ·
      normalization_report.json · classification_dry_run.json · 테스트 · 근거 문서
제외  departments.raw.jsonl.gz (136MB) · universities.raw.jsonl.gz ·
      curricula/ · checkpoint · collection_errors.jsonl · .env
```

Key 문자열 스테이지 diff 검색 0건.

## 22. 남은 사람 검수 항목

1. **§4 연도 비교 대안 선택** (①)
2. **대표 전공군 40개 검토** (②) — 특히 `무역·유통·관광`·`생활과학` 분리 여부
3. **융합학과 4,454건** — 공식 교육과정 근거로 예체능 여부 판정
4. **N.C.E 3,657건** — 공식 분류가 없어 다른 근거 필요
5. **department_id 중복 588건** — 어느 `schlMjrId`가 현행인지
6. **단과대학 URL 3건** (④)
7. **Master 승격 여부** — 승격 시 기존 35건의 `department_id`가 전부 재생성되고
   canonical 매핑 34건이 재검수 대상이 된다. ①이 정해진 뒤에 판단할 일이다

## 23. Commit·Push Hash

```
1cebef7  worker-c: collect latest AcademyInfo departments and build classification draft
b462883  docs(worker-c): record A review outcome and the two reversed judgements
16ed9e5  worker-c: replace root-domain source_url with verifiable dataset URL
10302c6  worker-c: add AcademyInfo collection and normalization pipeline
```

(이 보고서 작성 시점 이후 커밋은 push 결과에 추가 기록)

---

## 실행 방법

```bash
# .env에 DATA_GO_KR_SERVICE_KEY (Decoding 키)
python scripts/career_collect_academyinfo_departments.py          # 연도 자동 선택
python scripts/career_normalize_academyinfo.py --survey-year 2025
python scripts/career_classify_academyinfo.py --survey-year 2025
```

연도를 지정하지 않으면 API에 물어 최신값을 쓴다. 학과 데이터가 없는 연도를 지정하면
표본 3건 확인 후 즉시 중단한다.
