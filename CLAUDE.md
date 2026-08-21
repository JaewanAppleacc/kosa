# AI 진로·학업설계 Agent — 작업자 C 구현 지침 (`worker-c` 브랜치)

## 역할

이 브랜치에서 Claude Code는 작업자 C(데이터·RAG·MCP)의 구현 도구다. `outputs/work_assignments/작업자_C_개발_지시서.md`에 정의된 범위 안에서 데이터 수집·정제·Repository·RAG·MCP·Persona/Fixture를 작성한다.

Agent의 호출 여부, 다음 질문, Stop Condition, 최종 추천 판단은 이 작업 범위가 아니다(A 소유).

## Source of Truth

1. 작업자 C 개발 지시서: `outputs/work_assignments/작업자_C_개발_지시서.md`
2. Schema·Protocol 계약: `src/schemas/`, `src/repositories/protocols.py`
3. `outputs/context_definition_table_draft.md`, `outputs/trait_ontology_draft.md` — Context 15개·Trait 12개 확정본(팀 검토 진행 중)
4. 사용법 요약: `README_C.md` (repo root)
5. `main` 브랜치가 계약의 최신 상태다. `main`이 바뀌면 이 브랜치로 `git merge main` 또는 `git rebase main`해서 따라간다.

## C가 실제로 구현할 파일 (지금 이 브랜치엔 없음 — C가 새로 만든다)

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

## C가 소유하지 않는 영역 (읽고 참고하되 수정하지 않는다)

```
src/schemas/                       A 소유. 필드가 부족하면 A에게 요청
src/repositories/protocols.py       A 소유. Protocol 자체를 바꾸지 않는다
src/engines/evidence_engine.py      A 소유
src/engines/policy_guard.py         A 소유
src/engines/trait_normalizer.py     A 소유
eval/trait_eval.py                  A 소유
src/ids.py                          A 소유. 함수를 그대로 쓰고 새로 만들지 않는다
src/data/trait_ontology/, src/data/contexts/, src/data/question_frames/   A 소유 확정 데이터
src/data/personas/demo_user_01.py    A가 만든 예시 — 형식만 따라 하고 이 파일 자체는 수정하지 않는다
src/api/, src/agents/assessment/, eval/(trait_eval.py 제외한 나머지)      A 소유, C와 무관
```

브랜치를 나눴다고 소유권 규칙이 바뀌지 않는다. 이 브랜치 안에서도 위 파일은 건드리지 않는다.

## ID 규칙 (직접 만들지 말고 `src/ids.py` 함수를 그대로 쓴다)

```python
from src.ids import generate_department_id, generate_subject_id
generate_department_id(schl_id, department_name, college_name)  # 조사년도 넣지 않음
generate_subject_id(curriculum_code, canonical_subject_name)     # 정규화된 과목명 사용
```

## 아키텍처 불변식

- Repository는 조회만 한다. 다음 행동을 결정하지 않는다.
- MCP Tool은 `MCPToolResult`로 감싸서 `ok`/`empty`/`error`/`source_missing`을 명시적으로 구분한다. 실패를 성공처럼 위장하지 않는다.
- 같은 `data_comparability_group`끼리만 비교한다. 서로 다른 학년도·전형·지표를 하나의 정렬 결과로 섞지 않는다.
- Canonical Mapping 확신이 낮으면 자동 확정하지 않고 `REVIEW_REQUIRED`로 남긴다.
- 학교 개설 목록에 없는 과목을 실제 개설과목처럼 추천하지 않는다.
- 근거 없는 설명(출처 URL 없는 학과·과목 설명)을 생성하지 않는다.
- `course_document_parser.py`는 PDF(`application/pdf`)와 Excel(`.xlsx`, `.xls`)만 입력으로 받는다.

## Persona / Hand-Calculated Fixture

`src/data/personas/demo_user_01.py`를 템플릿으로 그대로 복사해서 답변만 바꾼다. `calculation_notes`에는 숫자만 적지 말고 왜 그 숫자가 나오는지 서술한다. 검증:

```python
from eval.trait_eval import evaluate_persona_against_fixture
result = evaluate_persona_against_fixture(persona, fixture, blueprint_by_question_id)
assert result.passed, result.mismatches
```

## 작업 흐름 (브랜치 기반)

- 이 브랜치(`worker-c`)에서 커밋한다. `main`에 직접 push하지 않는다.
- "C가 실제로 구현할 파일" 목록이 어느 정도 쌓이면 `main`으로 PR을 올리거나 A에게 병합을 요청한다. 참고용으로 받은 A 소유 파일은 수정했더라도 diff에 포함시키지 않는다.
- `main`의 계약(Schema/API)이 바뀌면 A가 알려준다. 그 전까지 이 브랜치가 최신이라고 가정하지 않는다 — 작업 시작 전 `git fetch origin && git log main..origin/main`으로 뒤처지지 않았는지 확인한다.
- Major–Trait·Subject–Trait Mapping 근거는 반드시 공식 출처 URL·기준일과 함께 기록한다.

## 금지 사항

- `src/schemas/`, `eval/`, LangGraph 관련 파일 직접 수정
- A가 소유한 Matching·Agent 판단 로직을 데이터 모듈에 복제
- 검증되지 않은 Mapping을 확정 데이터로 처리
- 출처 없는 학과·과목 설명 생성
- `main`에 직접 push
