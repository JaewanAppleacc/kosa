# C 작업자 핸드오프 번들 — 2026-08-21

이 폴더 하나로 독립 실행됩니다. 전체 저장소를 clone할 필요 없습니다. (단, 이건 특정 시점 스냅샷이라 이후 변경사항은 못 받습니다 — 최신 상태가 필요하면 `https://github.com/JaewanAppleacc/kosa.git` 전체를 보세요.)

## 1. 실행 확인

```bash
cd handoff_C
python3 -m venv .venv
./.venv/bin/pip install pydantic
./.venv/bin/python -c "
from eval.trait_eval import evaluate_persona_against_fixture
from src.data.personas.demo_user_01 import DEMO_USER_01_PERSONA, DEMO_USER_01_FIXTURE, BLUEPRINT_BY_QUESTION_ID
result = evaluate_persona_against_fixture(DEMO_USER_01_PERSONA, DEMO_USER_01_FIXTURE, BLUEPRINT_BY_QUESTION_ID)
print('passed:', result.passed)
"
```

`passed: True`가 나오면 정상입니다.

## 2. 폴더 구성

```
handoff_C/
├ README.md                          (이 파일)
├ eval/trait_eval.py                  Persona↔Fixture 자동 비교 도구
└ src/
   ├ ids.py                           ID 생성 규칙 (department_id/subject_id 포함)
   ├ schemas/                         Department, AdmissionReference, CourseProfile,
   │                                  RetrievedDocument, MCP Tool 8개, Persona/Fixture
   ├ repositories/protocols.py        C가 구현할 Repository의 Protocol 정의
   ├ engines/                         evidence_engine, trait_normalizer, policy_guard
   └ data/
      ├ trait_ontology/                확정된 Trait 12개
      ├ contexts/                      확정된 Context 15개
      └ personas/demo_user_01.py       실제로 동작하는 Persona+Fixture 예시(템플릿)
```

## 3. C가 실제로 구현할 파일 (이 번들엔 없음 — C가 새로 만들 것)

```
src/repositories/department_repository.py
src/repositories/admission_repository.py
src/rag/ (ingest.py, normalize.py, chunk.py, embed.py, retrieve.py)
src/mcp/education_server.py
src/agents/course/course_document_parser.py
src/engines/canonical_mapper.py
src/engines/admission_filter.py
```

## 4. 지켜야 할 계약

| 만들 것 | 따라야 할 Protocol/Schema (이 번들 안 경로) |
|---|---|
| `department_repository.py` | `src/repositories/protocols.py`의 `DepartmentRepository` — `search()`, `get()`이 `src/schemas/major.py`의 `Department` 반환 |
| `admission_repository.py` | 같은 파일의 `AdmissionRepository` — `find_comparable()`이 `AdmissionReference` 리스트 반환. **같은 `data_comparability_group`끼리만** 묶어서 반환 (다른 학년도·전형·지표 섞지 않기) |
| `src/rag/retrieve.py` | `DocumentRetriever` Protocol — `search()`이 `src/schemas/retrieval.py`의 `RetrievedDocument` 반환 |
| `src/mcp/education_server.py` | `src/schemas/mcp_contracts.py`에 8개 Tool Input/Output 전부 정의됨. `MCPToolResult`로 감싸 `ok`/`empty`/`error`/`source_missing` 구분 |
| `course_document_parser.py` | `src/schemas/course.py`의 `ParsedSubjectCandidate` 반환. Agent 판단·최종 추천은 여기서 안 함 |
| `canonical_mapper.py` | `src/schemas/major.py`의 `CanonicalMappingResult` 반환. 확신 낮으면 `mapping_status="REVIEW_REQUIRED"` |

## 5. ID 규칙 (직접 만들지 말고 이 함수를 그대로 쓰세요)

```python
from src.ids import generate_department_id, generate_subject_id

generate_department_id(schl_id, department_name, college_name)  # 조사년도(svyYr) 넣지 않음
generate_subject_id(curriculum_code, canonical_subject_name)     # 정규화된 과목명 사용
```

`department_id`에 조사년도를 넣으면 재수집할 때마다 같은 학과가 새 ID를 받아 이력 추적이 끊깁니다. 연도는 `Department.source_svy_year`에 따로 저장하세요. `subject_id`는 원본 표기가 아니라 Alias 정규화된 이름으로 해시하세요.

## 6. Persona / Hand-Calculated Fixture 작성법

설계안 §26이 요구하는 8개 Persona(분석·표현·관계·실행·관심분산·Conflict형 등)를 만들 때:

- Schema: `src/schemas/persona.py`의 `Persona`, `PersonaAnswer`, `HandCalculatedFixture`, `HandCalculatedTraitExpectation`
- **실제 동작하는 예시**: `src/data/personas/demo_user_01.py` — 게임·미디어·학교생활 8개 답변으로 6가지 Trait 상태(STRONG/MODERATE/LIMITED/INSUFFICIENT 3종)를 손계산해 만든 완성본입니다. 그대로 복사해서 답변만 바꾸세요.
- 검증:
  ```python
  from eval.trait_eval import evaluate_persona_against_fixture
  result = evaluate_persona_against_fixture(persona, fixture, blueprint_by_question_id)
  assert result.passed, result.mismatches
  ```
- `calculation_notes`에는 숫자만 적지 말고 **왜 그 숫자가 나오는지** 반드시 서술하세요 — `demo_user_01.py` 참고.

## 7. 아직 초안 단계라 검토 필요한 것

이 번들엔 안 들어있지만, 저장소 `outputs/` 폴더의 다음 문서가 C의 콘텐츠 작업과 직결됩니다:

- `outputs/context_definition_table_draft.md` — 15개 Context 확정본
- `outputs/trait_ontology_draft.md` — 12개 Trait 확정본
- `src/data/question_frames/frame_role_map.py`(저장소 원본) — 질문 Frame↔위치 매핑 **1차 초안**, 아직 팀 검토 전이니 참고만 하세요

## 8. 문제 발견 시

Schema에 없는 필드가 필요하면 직접 추가하지 말고 A에게 변경 요청하세요.
