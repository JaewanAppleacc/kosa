# 작업자 C 완료 보고 — 대학알리미 학과 수집·정규화

작성 2026-08-23 · 브랜치 `worker-c` · 지시서 §12 형식
설계 근거 전문: `rationale_c/07-academyinfo-collection.md` (항목 16개)

---

# A가 판단해야 할 것 — 5건

바쁘면 이 절만 읽으면 된다. 나머지는 근거·실측치다.

## ① 공개 API 응답에 필드 2개가 늘었다 — 승인 필요

`Department`(= `GET /departments/{major_id}` 응답)에 **선택 필드 두 개**를 추가했다.

```python
source_dataset: str | None = None   # 데이터셋 이름 (표기용)
department_url: str | None = None   # 확인된 학과 홈페이지. 없으면 None
```

- 기존 필드는 하나도 안 바뀜. 둘 다 `None` 기본값이라 **기존 소비자는 안 깨진다.**
- 응답 필드 집합을 고정하던 **테스트 3개를 함께 갱신**했다. 이 테스트들은 C가 A 경계를
  넘지 않게 심어 둔 방어장치라, 한 번 되돌리고 보고한 뒤 사용자 지시를 받아 반영했다.

```
tests/test_api.py::test_response_schema_matches_existing_departments_response_contract
tests/test_recommendation_scope_policy.py::test_departments_response_contract_is_unchanged
tests/test_vertical_slice_major_department_alignment.py::test_departments_response_contract_unchanged
```

**A가 할 일:** 이 계약 변경을 승인할지 판단. 승인하면 `outputs/mock_api/departments_normal.json`을
재생성해야 Mock과 실제 응답이 갈리지 않는다.

**현재 채워진 상태: 시연 35개 학과 전부에 학과 홈페이지가 들어갔다 (35/35).**
화면에서 모든 학과 카드에 `학과 홈페이지 →` 링크가 뜬다.

URL은 전부 **후보를 만들고 실제로 접속해 본문에 대학명·학과명이 있는지 확인한 것만** 넣었다.
이 검증이 실제로 오연결을 막았다.

| 후보 URL | 실제 도착지 |
|---|---|
| `design.yonsei.ac.kr` | Yonsei School of **Computing** (디자인 아님) |
| `media.korea.ac.kr` | media **lab** (연구실, 미디어학부 아님) |
| `media.khu.ac.kr` | 경희대 **미디어센터** (학과 아님) |

그대로 넣었으면 학생이 엉뚱한 사이트로 이동했을 것이다 — **링크가 없는 것보다 나쁘다.**

**A가 알아야 할 예외 3건:**

1. **중앙대 디자인학부 → 예술대학 홈페이지**(`arts.cau.ac.kr`). 디자인학부는 5개 전공이
   각각 별도 사이트를 쓰고 학부 단독 홈페이지가 없다. "학부 페이지가 없으면 상위 단과대학"이
   허용 가능한 대체인지 확인 필요.
2. **서울대 컴퓨터공학부·중앙대 예술대학**은 자동 검증을 못 했다(이 PC에서 ConnectError /
   HTTP 999 봇 차단). 사람이 브라우저로 열어 확인한 것을 근거로 넣었다.
3. **충남대 자유전공학부는 2025학년도부터 '지식융합학부'로 개칭**됐다. 공시 명칭과 현행
   명칭이 다르므로 `name_note`에 기록만 하고 `department_name`은 안 바꿨다 — 어느 쪽을
   화면에 쓸지는 판정이라 검토 대상이다. 손으로 넣은 데이터라 생긴 지연으로, 전국 수집분
   승격(②) 시 자동 해소된다.

**왜 필요했나:** 기존 `source_url`이 전부 `https://www.academyinfo.go.kr/` 루트 도메인인데
프론트가 이걸 **"공식 출처"라는 링크 텍스트**로 노출하고 있었다. 학생이 눌러도 포털 첫 화면만
뜨고 자기 학과 근거는 못 본다. 근거를 뒷받침하는 것처럼 보이지만 아무것도 증명하지 않는 링크다.
대학알리미는 조회 폼 기반이라 **학과별 고정 링크가 아예 존재하지 않는다** — API 응답 필드를
전부 확인했지만 학과 홈페이지는커녕 대학 홈페이지 필드도 없다. 그래서 한 필드가 겸하던
두 역할을 분리했다.

| 필드 | 뜻 | 화면 |
|---|---|---|
| `source_url` | 이 **데이터**의 출처 | 링크 아님. `대학알리미 2025년 공시 기준` 표기 |
| `department_url` | 학생이 **더 알아볼** 곳 | 링크. 있을 때만 `학과 홈페이지 →` |

## ② `department_id` 생성 키를 아직 정하지 못했다 — 결정 필요

정규화에서 **`department_id` 중복 8건**이 나왔다. 대학알리미가 같은 학과를 여러
`schlMjrId`로 나눠 보내기 때문이다.

```
경희대 간호학과 | 간호과학대학 | EXISTING  | schlMjrId 0218135 | 재학  0
경희대 간호학과 | 간호과학대학 | EXISTING  | schlMjrId 0009465 | 재학 85
경희대 간호학과 | 간호과학대학 | ABOLISHED | schlMjrId 0208603 | 재학  0
```

`generate_department_id(schl_id, 학과명, 단과대학)`은 이 셋을 구분할 수단이 없다.

"재학생 많은 쪽을 남긴다"가 바로 떠오르지만 **신설 학과는 재학생이 0명**이라 반례가 즉시 나온다.
§9("사람이 검토하지 않은 것을 확정하지 않는다")에 따라 자동으로 고르지 않고 전부 남긴 채
`review_status: REVIEW_REQUIRED`로 표시했다 (해당 17행).

`schlMjrId`를 해시에 넣으면 중복은 사라지지만, 대신 **같은 학과가 연도마다 다른 id를 받을
위험**이 생긴다. 2024·2025 두 해를 비교해 유지율을 확인한 뒤 정해야 한다. **아직 안 했다.**

## ③ 4년제 범위를 6년제까지 넓혔다 — 확인 필요

지시서 §7은 "4년제"라고만 했는데, 그대로 잡으면 **의·치·한의·수의예과가 통째로 빠진다**.
사용자 판단으로 포함하기로 했다.

```
schlKndCd = 03 (대학교)  AND  pbnfDgriCrseDivCd = 3 (학사)
                         AND  lsnTrmCd ∈ {07, 08, 09, 10, 11, 12, 13}   # 4년~7년
```

수업연한 코드는 연한 순으로 커지다 끝에서 끊긴다 — `14`=1년(교육특성화), `15`=2년(교육특성화)로
**코드값은 13보다 큰데 실제 연한은 1~2년**이다. `>= "07"` 같은 부등호로 짰으면 조용히 딸려
들어왔을 함정이라 명시적 집합으로 잡고 테스트로 고정했다.

실측(시연 13개 대학 2,380건): 포함 2,324 / 제외 56. 6년제로 포함된 21건은
의예과·치의예과·약학부·수의과·한의예과 등.

## ④ 수집 원본을 Git에 넣지 않기로 했다 — 정책 확인 필요

전국 환산 시 **약 155MB, 파일 34,000개**다. gzip은 git 델타 압축이 안 먹어서 재수집할 때마다
전량이 새 blob으로 히스토리에 영구히 쌓인다(3개 연도면 465MB, 되돌리려면 히스토리 재작성).

`.gitignore`로 제외하고, **재현에 필요한 최소 집합만** 커밋하는 것으로 정했다.

```
커밋 O   codes/ (72KB) · collection_manifest.json · 수집·정규화 스크립트 · 테스트
커밋 X   departments.raw.jsonl.gz · curricula/ · checkpoint · errors
```

지시서 §13이 허용한 경로("Manifest와 재현 가능한 수집 스크립트를 우선 인계")를 따랐다.
Git LFS는 쓰지 않았다 — LFS 없이 clone하면 파일이 포인터로만 받아져 "있는데 못 읽는" 상태가 된다.

## ⑤ 분류(§8) 착수 전에 합의가 필요하다

`canonical_majors.jsonl`이 현재 **10개**다. `canonical_mapper.py`는 Exact/Alias만 자동 확정하고
Embedding·LLM 결과는 무조건 `REVIEW_REQUIRED`로 남긴다(설계안 §3·§8).

시연 13개 대학만으로도 학과가 2,324건이다. 이걸 10개 canonical에 붙이면 대부분 `UNMAPPED`거나
검토 대기열로 간다. **전국이면 검토 대기가 수천 건이 된다.**

완화 경로가 §8-1 1순위 근거에 이미 있다 — **대학알리미 공식 표준 대·중·소계열**. 코드표를
전부 받아뒀다(대계열 6 · 중계열 28 · 소계열 158 · 계열체계 198). 이걸 canonical 뼈대로 쓸지가
자동 확정률을 좌우한다.

**착수 전 드라이런으로 `AUTO / REVIEW_REQUIRED / UNMAPPED` 비율부터 재야 한다.** 이 숫자 없이
시작하면 몇 주짜리인지 몇 달짜리인지 모른 채 뛰어드는 것이다.

---

# 지시서 §12 보고 항목

## 1. 사용한 공식 Endpoint·Operation·조사연도

```
Base       https://apis.data.go.kr/B340014
대학 목록   BasicInformationService_2/getComparisonUniversitySearchList
학과       BasicInformationService_1/getUniversityMajorCode
코드표 16종  BasicInformationService_1 12종 + _2 4종
조사연도    2025 (유효값 2025 / 2024 / 2023 — getComparisonPubYear로 확인)
응답 형식   XML 전용 (JSON 옵션 없음)
일일 트래픽  _2 = 1,000 · _1 = 10,000 (오퍼레이션당)
```

지시서 §3이 "또는 실제 서비스 문서상 동일 역할 Operation"이라고 열어둔 부분은, 실제 호출로
지시서에 적힌 이름이 그대로 맞음을 확인했다.

## 2. Key 노출 방지 방식

- `.env`의 `DATA_GO_KR_SERVICE_KEY`로만 주입. `.gitignore:12`에 `.env` 포함 확인.
- `.env.example`에는 변수명만 기록.
- Key는 항상 `params`로만 전달 — URL 문자열에 박지 않는다.
- 모든 예외 메시지·응답 본문에서 `_mask()`로 `***SERVICE_KEY***` 치환.
- Encoding 키가 들어와도 `unquote()`로 정규화(사람이 가장 자주 틀리는 지점).
- 테스트 3건이 Key 미노출을 고정: 오류 메시지 / 네트워크 오류 메시지 / URL.
- 산출물·Git diff 전체 검색 결과 Key 문자열 0건.

## 3. Smoke Test 결과

```
getComparisonPubYear   resultCode 00 · 2025/2024/2023
getCodeByType          resultCode 00 · 16종
getUniversityMajorCode resultCode 00 · 필드 구조 확인
getCodeByKind          ConnectTimeout 1회 → 재시도 필요성의 실측 근거
```

## 4. 수집 대학 수·학과 수·실패 수

```
전국 대학 목록   377개
수집 범위       시연 13개 대학 → schlId 17개 (본교·분교 별도)
학과            2,380건
실패 대학        0개
API 호출         54회
원본 용량        8.3MB
```

## 5. 4년제 범위 판정 기준과 제외 수

→ 위 ③. 포함 2,324 / 제외 56.

| 제외 사유 | 건수 |
|---|---|
| 수업연한 2년 | 46 |
| 수업연한 3년 | 6 |
| 학위과정이 학사 아님(학석사통합) | 3 |
| 수업연한 3.5년 | 1 |

제외 행은 삭제하지 않고 `excluded_records.jsonl`에 **제외 근거 + 판정에 쓴 공식 필드**와 함께
남겼다. 기준이 바뀌면 재수집이 아니라 재정규화로 끝난다.

## 6. 파일 경로

```
data/academyinfo_raw/2025/
  codes/*.jsonl.gz              코드표 16종        ← 커밋 대상
  collection_manifest.json      수집 이력          ← 커밋 대상
  departments.raw.jsonl.gz      원본 2,380건       ← gitignore
  universities.raw.jsonl.gz     대학 377건         ← gitignore
  curricula/*.txt.gz            교과목 전문 분리분  ← gitignore
  collection_checkpoint.json    Resume 상태        ← gitignore

data/academyinfo_work/2025/
  departments.normalized.jsonl  정규화 2,324건
  excluded_records.jsonl        제외 56건 + 근거
  normalization_report.json     품질 숫자
```

## 7. Canonical Major 분류 규칙

**아직 구현하지 않았다.** 이번 작업은 분류 **재료 정리**까지다. 정규화 결과에 §8-1 근거를
`official_classification`으로 담아 뒀다.

```jsonc
{
  "large_series_code": "B",  "large_series_name": "자연과학계열",
  "middle_series_code": "23","middle_series_name": "의료",
  "small_series_code": "110","small_series_name": "의학",
  "self_series_name": "자연과학계열",   // 대학자체계열 — 표준분류와 충돌하면 REVIEW 신호
  "is_unclassified": false
}
```

교육목표(`education_goal`)·목표 키워드(`education_goal_keywords`)·교과목 해시도 함께 담았다 —
§8-1 3순위 근거인 "학과 교육목표·교육과정 공식 자료"가 API로 직접 온다.

## 8. 예체능 추천 제외 규칙

**아직 구현하지 않았다.** 대계열 분포는 확보했다.

```
인문사회계열 874 · 공학계열 598 · 자연과학계열 492
예체능계열   315 · 교육계열  25 · 의학계열  20
```

지시서 §8-2가 제안한 `academic_field`/`eligibility_status` 필드명이 기존
`data/master/department_recommendation_scope.jsonl` 및 커밋 `3b0c8ac`의 스키마와 다르다.
**착수 전 이름 통일이 필요하다** — 안 그러면 같은 개념이 두 이름으로 갈라진다.

## 9. 확정·REVIEW_REQUIRED·미매핑 개수

분류 미착수라 매핑 수치는 없다. 정규화 단계 수치:

```
포함            2,324
REVIEW_REQUIRED    17   (department_id 중복 8그룹)
계열 미분류(N.C.E) 347   ← Canonical 매핑 대상 아님
department_url 없음 2,324 (수집분 전부. API가 주지 않는다)
학과 상태: EXISTING 1,330 · ABOLISHED 916 · NEW 76 · MERGED 2
```

`N.C.E`(중계열 `99` / 소계열 `999`)는 분류명이 아니라 **"분류 없음" 센티널**이다. 유효 계열로
취급하면 미분류 학과 수백 건이 존재하지 않는 "N.C.E 전공"으로 뭉친다.

## 10. 기존 시연 데이터와의 Diff

기존 35건은 **아직 교체하지 않았다.** `data/master/`는 §1대로 건드리지 않고 별도 디렉터리에만
쌓았다. 다만 출처 문제 수정을 위해 `data/raw/departments.raw.jsonl`의 `source_url` 31건을
루트 도메인 → 데이터셋 URL로 교체하고 Master를 재생성했다(학과 내용은 불변).

전면 교체 시 `schl_id`가 `ACADEMYINFO_PENDING_*` → 실제 코드로 바뀌므로 **`department_id`가
전부 재생성되고 기존 canonical 매핑 34건이 재검수 대상**이 된다. ②가 정해진 뒤에 해야 한다.

## 11. 중복·결측·고아 레코드

```
department_id 중복      8그룹 / 17행  → REVIEW_REQUIRED 표시 (②)
단과대학명 결측          0건
대학 없는 고아 학과      0건
학과명·대학명 결측       0건
수집 실패 대학          0건
```

## 12. 추가·수정한 코드와 테스트

**신규**
```
src/data_sources/academyinfo_client.py               API 클라이언트
src/data_sources/academyinfo_codes.py                공식 코드 기반 판정
scripts/career_collect_academyinfo_departments.py    수집 CLI (옵션 10개)
scripts/career_normalize_academyinfo.py              정규화
tests/worker_c/test_academyinfo_client.py            24 tests
tests/worker_c/test_academyinfo_codes.py             16 tests
tests/worker_c/test_academyinfo_department_collector.py  10 tests
rationale_c/07-academyinfo-collection.md             설계 근거 16항목
outputs/handoff/worker-b-department-source-url.md    B 인계
```

**수정**
```
src/schemas/major.py                       Department 선택 필드 2개 (①)
scripts/career_build_department_master.py  두 필드 통과
data/raw/departments.raw.jsonl             source_url 31건 교체
.env.example / .gitignore
tests/test_api.py 외 2건                    계약 테스트 갱신 (①)
```

**테스트가 잡아준 실제 버그 2개** (설계가 아니라 테스트가 발견)

1. `resultCode`가 일시 오류(05 등)일 때 재시도 루프를 우회해 즉시 죽었다. 네트워크 예외만
   재시도되고 서버측 일시 오류는 안 됐다.
2. gzip 헤더에 파일명이 박혀, 같은 내용을 다른 경로에 쓰면 바이트가 달라졌다. §10의
   "동일 입력 재빌드 Byte-identical" 검사가 내용이 아니라 경로를 검사하게 될 뻔했다.

## 13. 테스트 결과

```
python -m unittest discover -s tests -t .
Ran 860 tests — OK          (신규 50개 포함)
```

## 14. A/B API 계약 영향

**있다.** → ①

- **A**: `Department` 선택 필드 2개 추가 + `outputs/mock_api/departments_normal.json` 재생성 필요
- **B**: 프론트 변경 필요. worker-c에 `frontend/`가 없어 별도 문서로 분리했다 —
  `outputs/handoff/worker-b-department-source-url.md` (수정 코드 포함)

## 15. 아직 사람이 검토해야 할 항목과 남은 한계

1. **`department_id` 원본 키** (②) — 2024·2025 비교 후 확정. 이걸 먼저 정해야 전국 승격 가능
2. **`canonical_majors` 확장 여부** (⑤) — 분류 착수 전 합의 필요
3. **분류 검토 처리량** (⑤) — 드라이런으로 비율 측정 후 인력 판단
4. **예체능 필드명 통일** (§8) — 기존 `department_recommendation_scope.jsonl`과 대조
5. **7년(13) 학과 실제 내용** — 시연 표본에 없었다. 전국 수집 후 학사과정 맞는지 확인
6. **비학과 행 필터** — "교양과" 같은 행이 섞인다. 규칙을 데이터보다 먼저 쓰지 않기 위해
   전국 분포를 본 뒤 정한다
7. **데이터셋 대조 스크립트 없음** — 기존 35건은 사람이 손으로 옮겨 적은 것이라, 데이터셋
   출처 표기도 엄밀히는 미검증 주장이다. 전국 수집 후 Diff가 이 대조를 겸한다
8. **`admission_unit`** — API에 대응 필드가 없어 `None`으로 둔다. 단과대학으로 대체하지 않았다

---

## 실행 방법

```bash
# .env에 DATA_GO_KR_SERVICE_KEY (Decoding 키) 필요
python scripts/career_collect_academyinfo_departments.py --survey-year 2025 --only-demo-universities
python scripts/career_normalize_academyinfo.py --survey-year 2025

# 전국 (약 30분, API 호출 400여 회)
python scripts/career_collect_academyinfo_departments.py --survey-year 2025
```

한도 초과 시 여기까지 저장하고 정상 종료한다 — 다음 날 `--resume`으로 이어받으면 된다.
