# 작업자 C → A 인계 — 2026-08-21 (`worker-c` 브랜치)

`README_C.md`가 요구한 C 소유 모듈을 A 확정 계약(`src/schemas/`, `src/repositories/protocols.py`)에
맞춰 전부 구현했다. A 소유 파일은 하나도 건드리지 않았다.

**설계 근거는 [`rationale_c/`](rationale_c/README.md) 폴더에 따로 정리했다** — 왜 LLM에 판정을
맡기지 않았는지, 데이터 규모를 어떤 기준으로 정했는지, 코드에 박힌 숫자를 무엇을 재서
정했는지. 발표에서 "그건 왜 그렇게 정했나"가 나올 지점만 모았다.

```bash
python -m unittest discover -s tests           # 248개 통과 (C 신규 122개)
python scripts/career_build_all.py             # 모든 데이터 재생성
python scripts/career_measure_thresholds.py    # 임계값 근거 재측정
python scripts/career_audit_data_quality.py    # ERROR 0 / WARN 1 / INFO 12
```

---

## 1. 구현한 것

| 파일 | 만족한 계약 |
|---|---|
| `src/repositories/department_repository.py` | `DepartmentRepository` Protocol (`search`/`get` → `Department`) |
| `src/repositories/admission_repository.py` | `AdmissionRepository` Protocol (`find_comparable`) |
| `src/engines/admission_filter.py` | §18 비교 가능성 정책 — 그룹 파생·검증·분리·정렬 |
| `src/engines/canonical_mapper.py` | §17 `CanonicalMappingResult`, Exact/Alias → Embedding → LLM |
| `src/rag/normalize.py` · `chunk.py` · `embed.py` · `ingest.py` · `retrieve.py` | §19 `RetrievedDocument`, `DocumentManifestEntry`, `DocumentRetriever` Protocol |
| `src/mcp/education_server.py` | §21 8개 Tool 전부, `MCPToolResult`의 4가지 상태 |
| `src/agents/course/course_document_parser.py` | §20 `ParsedSubjectCandidate` (PDF·Excel 전용 입력) |

### 계약을 코드로 강제한 지점 3곳

1. **미확정 Mapping은 자동 확정되지 않는다.** `canonical_mapper`에서 `AUTO_MAPPED`는
   Exact·Alias 단계에서만 나온다. Embedding·LLM 결과는 항상 `REVIEW_REQUIRED`이고,
   `CONFIRMED`로 가는 길은 사람이 부르는 `confirm()`뿐이다. `Department.canonical_major_id`도
   `AUTO_MAPPED`일 때만 채운다.
2. **비교 불가능한 입결은 섞이지 않는다.** `find_comparable()`이 항상 한 그룹만 반환하고,
   MCP Tool이 내보내기 직전에 `assert_single_group()`을 한 번 더 부른다. 정렬 함수도
   그룹이 섞여 있으면 정렬하지 않고 예외를 던진다.
3. **근거 없는 검색 결과가 나가지 않는다.** 검색 결과에 출처·기준일이 없으면 MCP Tool이
   `source_missing`을 돌려주고, 질의어가 본문에 30% 미만으로만 나타나는 문서는 아예
   결과에서 뺀다. BM25도 벡터 검색도 "가장 덜 안 맞는 문서"를 늘 돌려주기 때문에,
   바닥선이 없으면 근거 없는 질의에도 그럴듯한 결과가 나간다.

---

## 2. 제출 데이터 (지시서 §5 대비)

| §5 항목 | 상태 | 위치 |
|---|---|---|
| 정규화된 대학·학과 Master | 대학 10 · 학과 30 | `data/master/{universities,departments}.jsonl` |
| Canonical Mapping + REVIEW_REQUIRED | AUTO_MAPPED 29 · REVIEW_REQUIRED 1 | `data/master/canonical_mapping_*.jsonl` |
| 비교 가능한 AdmissionReference | 학과 16 · 39행 · 그룹 3개 (**컷 점수 미기입**) | `data/admissions/` |
| MajorProfile | 대표 전공 8개 | `data/master/major_profiles.jsonl` |
| CourseProfile 입력 (고교 과목) | 과목 18 · Alias 58 | `data/master/subjects*.jsonl` |
| 출처 포함 `RetrievedDocument[]` | 문서 6 · Chunk 10 (**5건은 샘플**) | `data/rag/` |
| 계약 준수 MCP Tool | 8개 | `src/mcp/education_server.py` |
| Persona·Hand-Calculated Fixture | 4종 (A의 demo_user_01 포함 5종) | `data/eval_fixtures/personas/` |
| RAG·Mapping 기대값 | 질의 4 · Mapping 18 | `data/eval_fixtures/*.json` |
| 질문 Cache (LLM 장애 대비) | 비핵심 Context 10개 | `data/master/question_cache.jsonl` |
| 데이터 품질 검사 결과 | ERROR 0 | `data/audit/data_quality.md` |
| 비핵심 Context Seed Question·Blueprint 초안 | 10개 (§9-1 Lint 통과) | `data/drafts/question_blueprints/` |
| Context × Trait Coverage 검토표 | 15 × 12 | `data/drafts/context_trait_reviews/` |

**출처 상태는 `data/README.md`에 종류별로 정리해 뒀다.** 실제 공식 자료 / 검증 전 골격 /
파이프라인 검증용 샘플 셋이 섞여 있고, 파일만 보고 구분할 수 있게 표시를 붙였다.

### Persona 4종이 만드는 상태 분포

| Persona | 재현하는 상태 |
|---|---|
| 표현·창작 중심 | STRONG 1 · MODERATE 2 · INSUFFICIENT(두 사유 모두) |
| 관계·조정 중심 | STRONG 1 + 나머지 전부 INSUFFICIENT (한 축만 강한 경우) |
| 실행 중심 | **LIMITED** — 같은 Context·같은 Frame에서만 반복된 근거 |
| 관심 분산형 | STRONG 없음 — "추가 탐색 필요" 문구가 나오는 조건 |

기대값은 손으로 센 값이고, 빌드 스크립트가 Evidence Engine 결과와 대조해 어긋나면 파일을
쓰지 않고 멈춘다. 4종 전부 첫 계산에서 일치했다.

---

## 3. A의 결정이 필요한 것 — 5건

### D1. `AdmissionRepository.find_comparable()` 계약이 자기모순이다 — **답을 정해 주면 바로 맞춘다**

Protocol의 반환 타입은 `list[AdmissionReference]` 하나인데 docstring은
"비교 가능한 자료끼리만 묶어서 **여러 그룹을 반환**한다"이고, 바로 다음 문장은
"서로 다른 그룹을 하나의 리스트로 **섞어서 반환하지 않는다**"이다. 평평한 리스트 하나로
여러 그룹을 담으면 두 문장이 동시에 성립하지 않는다.

C는 **섞지 않는다** 쪽을 지켰다 — `find_comparable()`은 항상 한 그룹만 반환하고
(`criteria.data_comparability_group`이 있으면 그 그룹, 없으면 최신 학년도 그룹),
여러 그룹이 필요하면 Protocol 밖 메서드 `find_comparable_groups()`를 쓴다.
Protocol을 `dict[str, list[...]]`로 바꿀지, 지금 해석을 확정할지 A가 정해 주면 된다.
어느 쪽이든 C 쪽 수정은 작다.

### D2. 의존성 3개 — 추가할지 지금 방식을 유지할지

`requirements-lock.txt`에 없어서 표준 라이브러리로 대체 구현한 것들이다. 전부
"인터페이스는 그대로 두고 내부만 교체" 가능한 형태로 짰다.

| 없는 것 | 지금 방식 | 추가하면 |
|---|---|---|
| langchain | RecursiveCharacterTextSplitter와 같은 규칙을 직접 구현 | `chunk.split_text()` 내부만 교체 |
| pgvector·DB 드라이버 | 메모리 `VectorIndex` (완전 탐색) | 같은 `upsert`/`search` 시그니처로 교체 |
| pypdf | 사이드카 `.txt` → pypdf(있으면) → 내장 최소 추출기 | 추출 정확도만 올라감 |

전국 규모로 넘어가면 pgvector는 사실상 필요하다. 지금 코퍼스(Chunk 10개)에서는 차이가 없다.

### D3. `.xls`(97-2003 이진) 지원 범위

지시서는 `.xls`도 입력으로 받으라고 했는데 표준 라이브러리로는 읽을 수 없다. 지금은
**빈 결과가 아니라 명시적 오류**를 돌려준다("xlsx로 다시 저장해 달라"). 조용히 빈 결과를
주면 "개설과목이 없는 학교"로 오해되기 때문이다. B의 업로드 화면에서 `.xls`를 아예 막을지,
파서를 도입할지 결정이 필요하다.

### D4. `schl_id` 임시값 — `department_id`가 나중에 전부 바뀐다

대학알리미 API Key가 없어 `schl_id`를 `ACADEMYINFO_PENDING_*`로 두고 있다. Key가 나오면
`department_id` 해시가 전부 새로 생성되므로, 그 전에 만들어진 `department_id`를 다른 곳에
저장해 두면 끊긴다. **Key 발급 전까지 `department_id`를 세션 데이터에 영구 저장하지 말 것.**

### D5. RAG 샘플 문서를 언제 걷어낼지

지금 코퍼스 6건 중 5건이 `sample://` 샘플이다. 실제 수집이 승인되면 그 5건을 지우고
대학 홈페이지 문서로 대체한다. 발표 시연에 이 5건을 쓸지(= 샘플임을 화면에서 밝힐지)는
A·B 판단이 필요하다.

---

## 4. 아직 막혀 있는 것

| 항목 | 막힌 이유 | 풀리면 할 일 |
|---|---|---|
| 전국 학과 Master | `DATA_GO_KR_SERVICE_KEY` 미발급 | `data/raw/departments.raw.jsonl` 교체 후 재생성. 코드 변경 없음 |
| 입결 실수치 | 출처 미확정 (대학어디가 자동 수집 불가) | 골격 파일의 두 컷 필드만 채우고 `review_status`를 `verified`로 |
| 대학 홈페이지 RAG | 수집 미승인 | `data/rag/sources.jsonl`에 실제 URL 추가 + 원문 저장 |
| 고교 과목 성취기준 | NCIC가 HWP/PDF 첨부로만 제공 | 과목명·교과(군)은 이미 확보. 성취기준만 비어 있다 |
| 핵심 5개 Context 중 business·making Seed | A 소유 (A 지시서 §4) | 작성되면 Coverage 표 재생성 |

---

## 5. C가 의도적으로 하지 않은 것

- `src/schemas/`, `src/repositories/protocols.py`, LangGraph 관련 파일 수정
- Trait 상태 판정(§13)·Contrast 선택(§5-1)·Matching(§16) 로직 구현 — A 소유
- 핵심 5개 Context의 Seed Question 작성 — 검사로도 막아 뒀다
  (`career_build_question_blueprints.py`가 핵심 Context를 받으면 종료한다)
- 확인하지 못한 입결 수치 기입, 공식 URL을 단 가짜 학과 문서 생성
- Context·Trait를 `PUBLISHED`로 승격 — A 검토 전이라 전부 `DRAFT`

---

## 6. 브랜치 정리 — PR 전에 할 일

이 브랜치에는 브랜치 전용 `CLAUDE.md`가 있다(기존 `worker-c`를 머지하면서 딸려왔다).
`README_C.md`가 요구한 대로 **`main` PR에는 포함하면 안 된다.**

```bash
python scripts/check_no_worker_claude.py   # PR 직전 확인 — 지금은 실패한다
```

둘 중 하나로 처리한다.

1. PR 직전에 `worker-c`에서 루트 `CLAUDE.md`를 지우는 마무리 커밋을 추가한다.
2. A가 구현 커밋만 골라 Cherry-pick 한다 — 구현은 `feat(worker-c): C 담당 모듈 전체 구현`
   커밋 하나에 모여 있다.

---

## 7. A의 통합 결정 — 2026-08-22 (`main` 병합 이후 1단계)

C의 구현이 `main`에 병합된 뒤, A가 실제 서비스에 처음 연결한 범위와 그 과정에서 확정한
결정을 남긴다. C가 작성한 위 1~6번 내용은 그대로 두고 여기에만 덧붙인다.

- **연결한 범위**: `GET /departments/{major_id}` 하나만 실제 경로로 교체했다
  (`FastAPI → MajorExplorationService → DepartmentRepository Protocol →
  JsonlDepartmentRepository → data/master/departments.jsonl`). 입결(D4)·RAG(D5)·
  Subject–Trait Matching·MCP 호출 Workflow는 이번 단계에 포함하지 않았다 — 한 번에
  다 연결하지 않고 Vertical Slice 하나씩 늘려가는 방향을 유지한다.
- **D1(`find_comparable()`)**: 이번 단계에서는 입결 API 자체를 연결하지 않아 답을
  당장 확정할 필요가 없었다 — 결정 보류. 다음 통합 단계(입결 연결)에서 정한다.
- **D4(`schl_id`/`department_id` 임시값)**: 그대로 따른다. `MajorExplorationService`는
  Repository가 돌려준 `department_id`를 응답으로만 내보내고, `AssessmentState`(장기
  Profile Store 대상)에는 어디에도 저장하지 않는다.
- **새 통합 원칙 하나 추가**: Department 조회 결과(canonical_major_id 매칭 결과 포함)를
  다시 Assessment 질문이나 Career Profile 계산에 되먹임하지 않는다 — Matching(§16)이
  이미 확정한 대표 전공을 조회하는 조회 전용 단방향 흐름이다.
- **표시 정책**: `department_status`가 `MERGED`/`SPLIT`/`ABOLISHED`인 학과, 그리고
  `canonical_major_id`가 아직 `None`(REVIEW_REQUIRED)인 학과는 일반 탐색 결과에서
  제외한다 — Repository는 그대로 두고 새로 추가한 `src/services/
  major_exploration_service.py`(A 소유)에서 이 노출 정책만 담당한다.
- **다음 후보**: 입결 연결(D1 확정 필요), RAG를 학과 상세 화면에 연결, 전국 학과 Master로
  확장(`DATA_GO_KR_SERVICE_KEY` 발급 이후).

---

## 8. 사용자 승인에 따라 A가 수행한 Vertical Slice 정합화 — 2026-08-22 (`main` 병합 이후 2단계)

7번(1단계) 이후 발견된 문제: `/majors/{session_id}`가 실제로 추천하는 대표 전공은
`src/data/majors/vertical_slice_major_profiles.py`의 3개(`media_communication`/
`hci_ux`/`industrial_engineering`)인데, C가 구축한 `data/master/departments.jsonl`은
그중 `media_communication`만 연결돼 있었다 — `hci_ux`/`industrial_engineering`을
추천받으면 학과 탐색이 항상 빈 목록이었다. 사용자가 이 정합화를 A에게 명시적으로
승인해 진행했다.

- **C의 데이터 구조·빌드 파이프라인은 그대로 썼다.** `data/raw/*.raw.jsonl`에 실제 대학·
  학과 5건을 추가하고(고려대·경희대·숭실대의 산업공학 계열 학과 3건, 이화여대·서울여대의
  HCI/UX 학과 2건 — 전부 공식 홈페이지로 교육과정을 직접 확인), `career_build_department_
  master.py`를 다시 돌려 `departments.jsonl`을 재생성했다. `departments.jsonl`을 손으로
  고치지 않았다.
- **`canonical_majors.jsonl`에 `hci_ux`/`industrial_engineering`을 새 Canonical Major로
  추가했다** — 이 둘은 원래 여기에 아예 없어서, 자동 Mapping이 애초에 이 둘로 확정될
  방법이 없었다. `industrial_engineering`은 실제 학과명(산업경영공학·산업·정보시스템공학
  등)이 alias와 정확히 일치해 3건 전부 Exact-Alias로 AUTO_MAPPED됐다.
- **`hci_ux`는 더 엄격하게 다뤘다.** 이화여대 융합콘텐츠학과는 alias("융합콘텐츠")로
  자동 확정됐다. 서울여대 산업디자인학과는 학과명만 보면 기존 `design`의 alias("산업
  디자인")에 자동으로 걸린다 — 하지만 공식 페이지 확인 결과 2006년부터 학년별 전용 UX
  트랙(UX디자인방법론→UX디자인 I/II→UX디자인종합설계)과 15년 이상 운영 중인 UX Design
  Lab이 있어, `canonical_mapper.confirm()` 경로로 사람이 `hci_ux`로 재확정했다(design
  자동 매칭 결과는 secondary_candidate로 남겨 근거를 지우지 않았다).
- **재현성 확보**: `confirm()`은 원래 재빌드 때마다 결과가 사라지는 구조였다 —
  `data/master/canonical_mapping_manual_confirmations.jsonl`(새 파일, raw 데이터와 같은
  성격의 입력)에 확정 근거를 남기고, `career_build_department_master.py`가 매 빌드마다
  이 파일을 다시 적용하도록 고쳤다. `tests/worker_c/test_shipped_data.py`의 재현성·
  미확정-Mapping-비승격 테스트 2개도 CONFIRMED 상태를 인식하도록 함께 갱신했다(C의
  기존 검증 의도는 그대로 유지 — REVIEW_REQUIRED만 여전히 확정 데이터에서 제외된다).
- **기존 8개 전공·30개 학과는 그대로 보존했다** — 개수 감소 없음(자동 검사로 확인).
- **참고 — `major_profiles.jsonl`은 건드리지 않았다.** C의 `career_build_major_profiles.py`
  가 만드는 `data/master/major_profiles.jsonl`은 이번에 다룬 `VERTICAL_SLICE_MAJOR_
  PROFILES`(3개)와 다른, 8개 전공짜리 완전히 별개의 Major Profile 데이터셋이다(둘 다
  "대표 전공"이라는 같은 개념을 가리키지만 서로 연결돼 있지 않다). `/majors/{session_id}`
  는 `major_profiles.jsonl`을 전혀 쓰지 않으므로 이번 정합화 범위 밖이라 판단해 손대지
  않았다 — 이 두 데이터셋을 언젠가 하나로 합칠지는 별도 결정이 필요하다.

---

## 9. 사용자 정책 확정에 따른 후속 교정 — 2026-08-22 (`main` 병합 이후 3단계)

8번(2단계) 직후 사용자가 프로젝트 범위를 최종 확정했다: **"예체능 계열 대학 학과는
추천·탐색 대상에서 제외한다."** 8번에서 `confirm()`으로 `hci_ux`에 재확정했던 서울여대
산업디자인학과는 실제 UX 교육과정 근거가 있어도 학과 자체가 예체능(디자인) 계열이라 이
정책에 위배된다. 이 절은 그 교정 내용을 기록한다 — 8번의 industrial_engineering 관련
내용은 이 정책과 충돌하지 않아 그대로 유효하다.

- **서울여대 산업디자인학과 확정 취소**: `data/master/canonical_mapping_manual_
  confirmations.jsonl`에서 이 학과의 `hci_ux` 확정 항목을 제거했다(파일을 통째로 비움).
  빌드 파이프라인을 재실행하면 원래의 Exact-Alias 결과(`design`)로 자연스럽게
  되돌아간다 — raw/master 데이터는 삭제하지 않았고, 학과 자체는 여전히 존재한다.
  취소한 확정의 근거·취소 사유는 새 파일
  `data/master/canonical_mapping_manual_confirmations_reverted.jsonl`에 감사 기록으로
  남겼다(삭제가 아니라 "시도했다가 정책 변경으로 취소했다"는 이력 보존).
- **`design` Canonical Major 자체를 추천 경로에서 제외**: 학과명 문자열로 개별 학과를
  자동 분류하는 방식 대신, `src/services/major_exploration_service.py`(A 소유)에
  `EXCLUDED_RECOMMENDATION_MAJOR_IDS = frozenset({"design"})`를 추가해 major_id
  단위로 명시적으로 막았다. Repository·Canonical Mapping 데이터는 그대로 두고
  노출만 막는다 — `/departments/design`은 (다른 미등록 major_id와 동일하게) 200 +
  빈 목록을 반환한다.
- **이화여대 융합콘텐츠학과는 재검토 후 유지했다**: 소속이 신산업융합대학(예술대학·
  미술대학·디자인대학·체육대학 아님)이고, 같은 단과대학의 체육과학부와 달리 실기고사
  전형이 아니며, 공식 자기소개가 "인문학+공학+디자인" 융합이라 순수 예체능이 아니다.
  이 검토 근거는 새 파일 `data/master/hci_ux_department_review.jsonl`에 학과별로
  기록해, 앞으로 `hci_ux`에 학과를 추가할 때도 같은 형식으로 근거를 남기게 했다.
- **결과**: `hci_ux`는 이제 학과 1개(이화여대 융합콘텐츠학과)뿐이다. 공식 근거로
  검증 가능한 비예체능 HCI/UX 학과를 추가로 찾지 못해 억지로 채우지 않았다 —
  README_B.md에 "학과 1개"로 정직하게 남겨 뒀다(§4).
- **관심 Context는 전혀 손대지 않았다**: `src/data/contexts/context_definitions.py`는
  이번 작업에서 한 줄도 바꾸지 않았다. 미술·디자인/스포츠/미디어/패션·뷰티 Context는
  그대로 존재하고, Shared Trait 추출에 계속 쓰인다 — "관심 Context 선택"과 "예체능
  학과 추천"은 완전히 다른 경로다(§16).
