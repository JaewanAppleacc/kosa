# C 작업자 핸드오프 번들 — 2026-08-21 (base commit `0110f07`)

이 폴더 하나로 독립 실행됩니다. 전체 저장소를 clone할 필요 없습니다. (단, 이건 특정 시점 스냅샷이라 이후 변경사항은 못 받습니다 — 최신 상태가 필요하면 `https://github.com/JaewanAppleacc/kosa.git` 전체를 보세요.)

**시작 전에 `작업자_C_개발_지시서.md`와 `CLAUDE.md`를 먼저 읽어주세요** — 담당 범위·소유권·완료 조건 전체가 거기 있고, 이 README는 계약(Schema/Protocol) 사용법만 다룹니다.

## 1. 실행 확인 (Python 3.11~3.13, 버전 고정 설치)

```bash
cd handoff_C
python3.13 -m venv .venv        # 3.11~3.13이면 됩니다. 3.14는 검증 안 됨 — 쓰지 마세요.
./.venv/bin/pip install -r requirements.txt
PYTHONPATH=. ./.venv/bin/python -c "
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
├ README.md                          (이 파일 — 계약 사용법)
├ CLAUDE.md                           C 전용 구현 지침(소유권·불변식·반환 방법)
├ 작업자_C_개발_지시서.md              담당 범위 전체
├ requirements.txt                    버전 고정된 의존성
├ docs/
│  ├ context_definition_table_draft.md  15개 Context 확정본(팀 검토 중)
│  └ trait_ontology_draft.md            12개 Trait 확정본(팀 검토 중)
├ eval/trait_eval.py                   Persona↔Fixture 자동 비교 도구
└ src/
   ├ ids.py                           ID 생성 규칙 (department_id/subject_id 포함)
   ├ schemas/                         Department, AdmissionReference, CourseProfile,
   │                                  RetrievedDocument, MCP Tool 8개, Persona/Fixture
   ├ repositories/protocols.py        C가 구현할 Repository의 Protocol 정의
   ├ engines/                         evidence_engine, trait_normalizer, policy_guard
   └ data/
      ├ trait_ontology/                확정된 Trait 12개
      ├ contexts/                      확정된 Context 15개
      ├ question_frames/frame_role_map.py  질문 Frame↔위치 매핑 **1차 초안**(팀 검토 전)
      └ personas/demo_user_01.py       실제로 동작하는 Persona+Fixture 예시(템플릿)
```

## 3. 파일 소유권 — 이 번들 안에서 뭐가 참고용이고 뭐가 C 것인지

**이 번들에 있는 코드는 전부 A 소유 참고용입니다.** `src/schemas/`, `src/repositories/protocols.py`, `src/engines/*.py`, `eval/trait_eval.py`, `src/ids.py`, `src/data/`의 확정 데이터·예시 — 전부 읽고 재사용하되 직접 수정하지 마세요.

**C가 실제로 만들 파일은 이 번들에 하나도 없습니다.** 아래 목록을 C가 새로 만들어서 위 계약(4번 표)을 만족시키면 됩니다.

```
src/repositories/department_repository.py
src/repositories/admission_repository.py
src/rag/ (ingest.py, normalize.py, chunk.py, embed.py, retrieve.py)
src/mcp/education_server.py
src/agents/course/course_document_parser.py
src/engines/canonical_mapper.py
src/engines/admission_filter.py
data/, datasets/, sources/, data/eval_fixtures/
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

## 7. `docs/`의 두 초안, 아직 확정 아님

`context_definition_table_draft.md`, `trait_ontology_draft.md`는 팀 검토가 끝나지 않은 초안입니다. `src/data/contexts/`, `src/data/trait_ontology/`의 실제 코드 데이터는 이 초안 내용을 그대로 반영한 것이라 지금 당장 써도 되지만, 최종 확정 시 값이 바뀔 수 있다는 걸 감안하세요. `frame_role_map.py`도 마찬가지로 1차 초안입니다.

## 8. 문제 발견 시

Schema에 없는 필드가 필요하면 직접 추가하지 말고 A에게 변경 요청하세요.

## 9. 작업 반환 시

- 3번 목록의 파일만 반환하세요. 참고용으로 받은 A 소유 파일은 수정했더라도 반환하지 않습니다.
- Base commit `0110f07` 기준으로 작업했다는 걸 커밋 메시지나 PR 설명에 남겨주세요.
- Major–Trait·Subject–Trait Mapping 근거는 반드시 공식 출처 URL·기준일과 함께 기록하세요.

## 참고 문서

- `작업자_C_개발_지시서.md`, `CLAUDE.md` — 이 폴더에 포함됨
- 최신 저장소: `https://github.com/JaewanAppleacc/kosa.git`
