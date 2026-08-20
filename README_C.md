# C 작업자 핸드오프 — 2026-08-21

이 저장소(`kosa`)를 clone하면 바로 데이터 작업을 시작할 수 있습니다. 여기 적힌 것만 보고 시작하시면 됩니다.

## 1. 빠른 시작

```bash
git clone https://github.com/JaewanAppleacc/kosa.git
cd kosa
python3 -m venv .venv
./.venv/bin/pip install -r requirements-lock.txt
./.venv/bin/python -m unittest discover -s tests -v
```

74개 테스트가 전부 통과해야 정상입니다.

## 2. C가 실제로 구현할 파일 (아직 하나도 안 만들어져 있음 — 전부 C 소유)

```
src/repositories/department_repository.py
src/repositories/admission_repository.py
src/rag/                                  (ingest.py, normalize.py, chunk.py, embed.py, retrieve.py)
src/mcp/education_server.py
src/agents/course/course_document_parser.py
src/engines/canonical_mapper.py
src/engines/admission_filter.py
data/, datasets/, sources/, data/eval_fixtures/
```

이 파일들을 만들 때 아래 계약(Schema·Protocol)만 만족하면 됩니다 — A가 소유한 파일은 직접 수정하지 마세요.

## 3. 지켜야 할 계약 (Schema·Protocol 위치)

| 만들 것 | 따라야 할 Protocol/Schema |
|---|---|
| `department_repository.py` | `src/repositories/protocols.py`의 `DepartmentRepository` — `search()`, `get()`이 `src/schemas/major.py`의 `Department`를 반환해야 함 |
| `admission_repository.py` | `DepartmentRepository` 옆의 `AdmissionRepository` — `find_comparable()`이 `AdmissionReference` 리스트 반환. **같은 `data_comparability_group`끼리만 묶어서 반환** (서로 다른 학년도·전형·지표 섞지 않기) |
| `src/rag/retrieve.py` | `DocumentRetriever` Protocol — `search()`이 `src/schemas/retrieval.py`의 `RetrievedDocument` 반환 |
| `src/mcp/education_server.py` | `src/schemas/mcp_contracts.py`에 8개 Tool의 Input/Output이 전부 정의돼 있음. `MCPToolResult`로 감싸서 `ok`/`empty`/`error`/`source_missing` 상태를 명시적으로 구분할 것 |
| `course_document_parser.py` | `src/schemas/course.py`의 `ParsedSubjectCandidate` 반환. Agent 판단·최종 추천은 여기서 하지 않음 |
| `canonical_mapper.py` | `src/schemas/major.py`의 `CanonicalMappingResult` 반환. 확신 낮으면 `mapping_status="REVIEW_REQUIRED"`로, 자동 확정하지 말 것 |

## 4. ID 규칙 (반드시 `src/ids.py` 함수를 그대로 쓰세요, 직접 만들지 마세요)

```python
from src.ids import generate_department_id, generate_subject_id

generate_department_id(schl_id, department_name, college_name)  # 조사년도(svyYr) 넣지 않음
generate_subject_id(curriculum_code, canonical_subject_name)     # 정규화된 과목명 넣을 것 (원본 표기 아님)
```

- `department_id`에 조사년도를 넣으면 재수집할 때마다 같은 학과가 새 ID를 받아서 이력 추적이 끊깁니다. 연도는 `Department.source_svy_year` 필드에 따로 저장하세요.
- `subject_id`는 학교마다 다른 원본 표기가 아니라 Alias 정규화를 마친 이름으로 해시하세요. 안 그러면 같은 과목이 학교마다 다른 ID를 받습니다.

## 5. Persona / Hand-Calculated Fixture 작성 가이드

설계안 §26이 요구하는 8개 Persona(분석·표현·관계·실행·관심분산·Conflict형 등)를 만들 때 이 형식을 따르세요.

- Schema: `src/schemas/persona.py`의 `Persona`, `PersonaAnswer`, `HandCalculatedFixture`, `HandCalculatedTraitExpectation`
- **실제로 동작하는 예시**: `src/data/personas/demo_user_01.py` — 게임·미디어·학교생활 8개 답변으로 6가지 Trait 상태(STRONG/MODERATE/LIMITED/INSUFFICIENT 3종)를 전부 손계산해서 만든 완성본입니다. 그대로 복사해서 답변만 바꾸면 됩니다.
- 손계산이 실제 코드와 맞는지 직접 확인하려면:
  ```python
  from eval.trait_eval import evaluate_persona_against_fixture
  result = evaluate_persona_against_fixture(persona, fixture, blueprint_by_question_id)
  assert result.passed, result.mismatches
  ```
- `calculation_notes` 필드는 숫자만 적지 말고 **왜 그 숫자가 나오는지** 반드시 서술하세요 — 검토자가 재검산할 수 있어야 합니다(`demo_user_01.py`의 예시 참고).

## 6. 아직 초안 단계라 검토 필요한 산출물 (C가 만들 콘텐츠와 직결됨)

| 파일 | 상태 |
|---|---|
| `outputs/context_definition_table_draft.md` | 15개 Context 확정본 — C가 나머지 10개(비핵심) Context의 Seed Question·Option Blueprint 초안 쓸 때 기준 |
| `outputs/trait_ontology_draft.md` | 12개 Trait 확정본 — Major-Trait, Subject-Trait Mapping 작성 시 이 12개 `trait_id`만 사용 |
| `src/data/question_frames/frame_role_map.py` | 질문 Frame↔위치 매핑 **1차 초안**(설계안에 명시적 표가 없어 A가 임의로 판단) — 아직 팀 검토 전이니 참고만 하고 확정된 것으로 인용하지 마세요 |

## 7. A에게 제공해야 할 것 (원래 작업 지시서 §5 기준, 위 계약을 만족하는 결과물)

- 정규화된 대학·학과 Master 데이터, Canonical Mapping 결과(REVIEW_REQUIRED 포함)
- 비교 가능한 AdmissionReference, MajorProfile/CourseProfile 데이터
- 출처 포함 `RetrievedDocument[]`, 계약 준수하는 MCP Tool
- Persona·Hand-Calculated Fixture (위 형식대로)
- 데이터 품질 검사 결과 (누락·중복·타입·출처·기준일)

## 8. 문제 발견 시

Schema에 없는 필드가 필요하면 직접 추가하지 말고 A에게 변경 요청하세요. A가 소유한 `src/schemas/`, LangGraph 관련 파일은 직접 수정하지 마세요.

## 참고 문서

- `outputs/work_assignments/작업자_C_개발_지시서.md` — 원래 담당 범위 전체
- `CLAUDE.md` — A의 구현 원칙과 개발 환경
- `outputs/presentation_qna_defense.md` — Trait Ontology 근거(O*NET/Holland 그라운딩 결과) 관련 발표 대비 자료, 데이터 근거를 물어보는 질문 대비에 참고
