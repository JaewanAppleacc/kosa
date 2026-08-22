"""CourseDocumentParsingService — A 소유, 2026-08-26 16차 리뷰, 설계안 §20 보조.

FastAPI가 받은 업로드 파일 bytes를 실제 Parser(`src.agents.course.course_document_parser`,
C 소유)로 연결한다:

    FastAPI(main.py) → CourseDocumentParsingService → course_document_parser
    → SubjectAliasIndex → ParsedSubjectCandidate

FastAPI Handler는 과목명 유사도 계산이나 JSONL 검색을 직접 하지 않는다 — 이 Service가
그 역할을 맡고, "확정 판단"(어떤 과목이 최종 개설과목인가)은 여전히
`CoursePlanningService`가 담당한다. 이 Service는 "업로드 파일 → 후보 목록"까지만
책임진다(추출·정규화, CLAUDE.md "과목 문서 Parser에는 입력 조건과 출력 Schema만
제공하고, 확정된 파싱 결과를 Course Planning에 반영한다").

파일 보안(§3)은 전부 여기서 처리한다 — FastAPI는 `UploadFile`에서 원본 bytes만 읽어
넘기고, 로컬 파일 경로 조립은 이 Service 밖에서 절대 하지 않는다:
- 사용자가 보낸 파일명(`UploadFile.filename`)을 로컬 경로로 직접 쓰지 않는다 — 임시
  파일명은 항상 이 Service가 새로 만들고(`tempfile.mkstemp`), 확장자도 검증을 통과한
  값만 suffix로 쓴다(Path Traversal 자체가 구조적으로 불가능해진다 — 사용자 입력이
  파일 경로 문자열 조립에 전혀 쓰이지 않으므로).
- 빈 파일·용량 상한(§3 MVP 권장 10MB)·Content-Type과 확장자 일치를 업로드 즉시 검사한다.
- `.xls`(97-2003 이진 형식)는 Parser가 실제로 못 읽는다 — "지원한다"고 말하지 않고
  파싱을 시도하기 전에 명확한 422로 막는다("XLSX로 다시 저장해 업로드" 안내 포함).
- 처리 후 `finally`에서 항상 임시 파일을 지운다. 업로드 원본은 어디에도(Repository·
  Git·CoursePlanningSessionState) 영구 저장하지 않는다.
- Parser가 예외를 던지면(방어적 — 현재 Parser는 대부분 ParseError로 정상 반환하지만)
  내부 Stack Trace를 그대로 노출하지 않고 안전한 PARSE_FAILED로 변환한다.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import UploadFile

from src.agents.course.course_document_parser import SubjectAliasIndex, parse_course_document
from src.memory.course_planning_store import CoursePlanningStore
from src.repositories.protocols import SubjectRepository
from src.schemas.assessment_state import AssessmentState
from src.schemas.course import (
    CoursePlanningSessionState,
    CourseParseWarning,
    CourseProfile,
    ParsedSubjectCandidate,
)
from src.services.course_planning_service import CoursePlanningService

# §3 MVP 권장 상한. 실제 개설과목 편성표는 텍스트 위주라 10MB면 충분히 넉넉하다 —
# 다른 값을 쓰려면 이 자리에 근거를 남긴다(지시서 §3).
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024

# .xls는 의도적으로 제외한다 — course_document_parser.SUPPORTED_SUFFIXES에는 .xls도
# 있지만(입력 자체는 받아서 명확한 ParseError를 남기는 용도), 이 Service는 그 단계까지
# 가지 않고 업로드 시점에 곧바로 거부한다(§3 "API에서 지원한다고 표현하지 말 것").
_ACCEPTED_SUFFIX_TO_CONTENT_TYPES: dict[str, set[str]] = {
    ".pdf": {"application/pdf"},
    ".xlsx": {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
}
_XLS_CONTENT_TYPES = {"application/vnd.ms-excel"}

# §4(17차): high > low > unmatched — 동일 subject_id가 여러 confidence로 중복 추출되면
# 더 확실한 쪽을 대표로 남긴다(숫자는 아니고 순서만 의미 있는 우선순위).
_CONFIDENCE_RANK: dict[str, int] = {"high": 0, "low": 1, "unmatched": 2}


class UnsupportedFileTypeError(ValueError):
    """PDF/XLSX가 아니거나(.xls 포함), Content-Type과 확장자가 서로 다른 형식을 가리킬 때."""


class EmptyFileError(ValueError):
    """빈 파일(0 byte)을 업로드했을 때."""


class FileTooLargeError(ValueError):
    """§3 MVP 상한(10MB)을 넘는 파일을 업로드했을 때."""


class CourseParsingFailedError(ValueError):
    """문서를 읽긴 했지만 본문에서 과목명 후보를 하나도 뽑아내지 못했을 때(이미지 스캔
    PDF, 손상된 xlsx 등) — "개설과목 0개"(정상, 200)와 구분되는 "파싱 실패"(422)."""


class CourseUploadNotFoundError(ValueError):
    """이 session_id로 먼저 POST /course/upload를 거친 적이 없는데 POST /course/confirm을
    호출했을 때."""


class CourseConfirmValidationError(ValueError):
    """confirm 요청의 confirmed_subject_ids가 유효하지 않을 때(§6) — data/master/
    subjects.jsonl에 없는 값, 이 업로드의 Parser 후보에 없는 값 등."""


async def read_upload_with_limit(
    file: UploadFile, max_bytes: int, chunk_size: int = 1024 * 1024
) -> bytes:
    """2026-08-27 17차 리뷰 §3: 업로드를 chunk 단위로 읽어, `max_bytes`를 넘는 순간
    더 이상 읽지 않고 즉시 실패시킨다 — `await file.read()`로 전체를 먼저 메모리에 다
    올린 뒤 크기를 검사하면(기존 방식) 기능적으로는 초과 파일을 거부해도, 그 사이 이미
    파일 전체가 메모리에 올라가 버려 메모리 보호 효과가 없었다.

    `Content-Length` 헤더는 신뢰하지 않는다(위·변조되거나 없을 수 있다) — 실제로 읽은
    byte 수만으로 판단한다. `max_bytes`를 인자로 받으므로 테스트에서는 굳이 수십 MB
    데이터를 만들지 않고 작은 상한을 주입해 빠르게 검증할 수 있다."""

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise FileTooLargeError(
                f"파일이 너무 큽니다(최소 {total} bytes 확인). 최대 {max_bytes} "
                "bytes(10MB)까지 업로드할 수 있습니다."
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_suffix_and_content_type(filename: str, content_type: str | None) -> str:
    """Path Traversal 방지: 원본 파일명 전체를 신뢰하지 않고, 확장자(suffix)만 확인해
    화이트리스트에 있는 값으로 정규화한다 — 반환값은 임시 파일 suffix로만 쓴다."""

    suffix = Path(filename or "").suffix.lower()

    if suffix == ".xls" or (content_type in _XLS_CONTENT_TYPES):
        raise UnsupportedFileTypeError(
            "XLS(97-2003 이진 형식)는 지원하지 않습니다. XLSX로 다시 저장해 업로드해주세요."
        )

    allowed_content_types = _ACCEPTED_SUFFIX_TO_CONTENT_TYPES.get(suffix)
    if allowed_content_types is None:
        raise UnsupportedFileTypeError(
            f"PDF 또는 XLSX 파일만 허용합니다. 받은 확장자: {suffix or '(없음)'}"
        )
    if content_type is not None and content_type not in allowed_content_types:
        raise UnsupportedFileTypeError(
            f"파일 확장자({suffix})와 Content-Type({content_type})이 서로 다른 형식을 "
            "가리킵니다. 올바른 PDF 또는 XLSX 파일인지 확인해주세요."
        )
    return suffix


def _dedupe_candidates(candidates: list[ParsedSubjectCandidate]) -> list[ParsedSubjectCandidate]:
    """§5(16차)/§4(17차): 동일 subject_id가 여러 번 추출돼도 최종 목록에는 한 번만
    남긴다. 대표로 남기는 후보는 confidence가 가장 높은 쪽이다(high > low) — 같은
    과목이 정확 매칭(high)과 fuzzy 매칭(low)으로 둘 다 잡히면, 먼저 나온 순서와
    무관하게 high가 대표로 남아야 한다(fuzzy가 먼저 추출됐다는 이유로 정확 매칭이
    사라지면 안 된다). 동일 confidence끼리는 최초 등장한 것을 그대로 유지한다(승격도
    강등도 하지 않는다 — fuzzy score를 API에 노출하지 않으므로 이 우선순위는 오직
    high/low/unmatched 세 등급만으로 결정한다).

    matched_subject_id가 없는(unmatched) 후보는 원문(raw_text 정규화 기준)이 같을
    때만 중복으로 본다 — 서로 다른 unmatched 원문은 억지로 합치지 않는다.

    출력 순서는 각 key(subject_id 또는 unmatched 정규화 원문)가 입력에서 처음 등장한
    위치 순서를 그대로 따른다(대표 후보의 confidence가 바뀌어도 순서는 안 바뀐다) —
    Parser 입력 순서에 의존하지 않는 결정론적 결과."""

    from src.agents.course.course_document_parser import normalize_subject_name

    def _key(candidate: ParsedSubjectCandidate) -> tuple[str, str]:
        if candidate.matched_subject_id is not None:
            return ("matched", candidate.matched_subject_id)
        return ("unmatched", normalize_subject_name(candidate.raw_text))

    first_index: dict[tuple[str, str], int] = {}
    best_by_key: dict[tuple[str, str], ParsedSubjectCandidate] = {}
    for index, candidate in enumerate(candidates):
        key = _key(candidate)
        if key not in first_index:
            first_index[key] = index
            best_by_key[key] = candidate
            continue
        current_best = best_by_key[key]
        if _CONFIDENCE_RANK[candidate.confidence] < _CONFIDENCE_RANK[current_best.confidence]:
            best_by_key[key] = candidate

    ordered_keys = sorted(first_index, key=lambda k: first_index[k])
    return [best_by_key[key] for key in ordered_keys]


class CourseDocumentParsingService:
    def __init__(
        self,
        alias_index: SubjectAliasIndex,
        subject_repository: SubjectRepository,
        course_planning_service: CoursePlanningService,
        course_planning_store: CoursePlanningStore,
    ) -> None:
        self._alias_index = alias_index
        self._subject_repository = subject_repository
        self._course_planning_service = course_planning_service
        self._course_planning_store = course_planning_store

    def parse_upload(
        self,
        state: AssessmentState,
        selected_major_id: str,
        content: bytes,
        filename: str,
        content_type: str | None,
    ) -> tuple[list[ParsedSubjectCandidate], list[CourseParseWarning]]:
        """§1/§2/§3 전체 흐름. 성공하면 새 `CoursePlanningSessionState`를 저장하고(§4
        "새 파일을 다시 업로드하면 이전 미확정 결과를 명시적으로 교체") 후보·경고 목록을
        반환한다. `MajorNotSelectableError`/`CourseEvidenceNotReadyError`는 그대로
        전파한다(main.py가 PRE_SURVEY 조회와 동일한 오류 코드로 매핑한다).

        검증 순서: 파일 자체의 구조적 문제(빈 파일·용량 초과·형식 불일치)를 먼저
        가볍게 걸러내고(상태 계산이 필요 없는 저렴한 검사), 그다음에 selected_major_id
        (§2, 상태 계산이 필요한 더 비싼 검사)를 확인한다 — "이 파일 자체가 애초에 못 쓸
        형식이다"와 "이 학생·전공 조합이 아직 준비가 안 됐다"는 서로 다른 문제라 순서를
        섞으면 진짜 원인과 다른 오류 코드가 먼저 뜰 수 있다."""

        if not content:
            raise EmptyFileError("빈 파일은 업로드할 수 없습니다.")
        if len(content) > MAX_UPLOAD_SIZE_BYTES:
            raise FileTooLargeError(
                f"파일이 너무 큽니다({len(content)} bytes). 최대 {MAX_UPLOAD_SIZE_BYTES} "
                "bytes(10MB)까지 업로드할 수 있습니다."
            )
        suffix = _validate_suffix_and_content_type(filename, content_type)

        # §2: PRE_SURVEY와 동일한 규칙으로 selected_major_id를 검증한다(로직 복제 없음).
        self._course_planning_service.validate_selectable_major(state, selected_major_id)

        # Path Traversal 방지: 사용자 filename은 여기까지만 쓰이고(확장자 판별), 실제
        # 임시 파일 경로는 tempfile이 전부 새로 만든다.
        fd, tmp_path_str = tempfile.mkstemp(suffix=suffix)
        tmp_path = Path(tmp_path_str)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(content)

            try:
                result = parse_course_document(tmp_path, self._alias_index, content_type)
            except Exception as exc:  # noqa: BLE001 — Parser가 예외를 던지면 절대 그대로 노출하지 않는다.
                raise CourseParsingFailedError(
                    "문서를 처리하는 중 예상하지 못한 오류가 발생했습니다. 파일이 손상되지 "
                    "않았는지 확인한 뒤 다시 시도해주세요."
                ) from exc

            if not result.succeeded:
                # §3: "개설과목 없음"과 "문서 파싱 실패"를 구분한다 — 여기 도달했다는 건
                # 본문 추출 자체(input/extract 단계)가 실패했다는 뜻이라 빈 목록으로
                # 조용히 넘어가지 않고 명시적으로 실패시킨다.
                messages = "; ".join(e.message for e in result.errors) or "문서를 읽지 못했습니다."
                raise CourseParsingFailedError(messages)
        finally:
            tmp_path.unlink(missing_ok=True)

        deduped_candidates = _dedupe_candidates(result.candidates)
        upload_status = (
            "CONFIRMATION_REQUIRED"
            if any(c.requires_user_confirmation for c in deduped_candidates)
            else "PARSED"
        )
        self._course_planning_store.save(
            CoursePlanningSessionState(
                session_id=state.session_id,
                selected_major_id=selected_major_id,
                parsed_candidates=deduped_candidates,
                confirmed_offered_subject_ids=[],
                upload_status=upload_status,
            )
        )

        # result.errors는 성공(succeeded=True) 시에는 현재 Parser 구현상 항상 비어
        # 있지만(input/extract 단계 오류만 succeeded를 False로 만든다), 앞으로 생길 수
        # 있는 normalize 단계 경고까지 그대로 옮겨서 감추지 않는다. detail(로컬 경로 등
        # 민감할 수 있는 값)은 절대 옮기지 않고 message만 옮긴다.
        warnings = [CourseParseWarning(stage=e.stage, message=e.message) for e in result.errors]
        return deduped_candidates, warnings

    def confirm(self, state: AssessmentState, confirmed_subject_ids: list[str]) -> CourseProfile:
        """§6(16차)/§2(17차) 전체 검증 + 원자적 확정.

        검증 → POST_OFFERING 추천 계산(`CoursePlanningService.build_post_offering_
        course_profile`, 이 안에서 Policy Guard까지 통과해야 한다) → 전부 성공한 뒤에만
        Store를 `CONFIRMED`로 갱신한다. 계산이나 Guard가 실패하면 이 메서드는 Store를
        전혀 건드리지 않은 채(=이전 상태 그대로) 예외를 그대로 전파한다 — "요청은
        실패했는데 Store에는 CONFIRMED가 남는" 상황을 구조적으로 막는다."""

        planning_state = self._course_planning_store.load(state.session_id)
        if planning_state is None:
            raise CourseUploadNotFoundError(
                "이 세션에 먼저 POST /course/upload로 개설과목 파일을 업로드해야 합니다."
            )

        # 중복 subject_id는 명시적으로 정규화한다(입력 순서를 유지하며 첫 등장만 남김).
        deduped_requested = list(dict.fromkeys(confirmed_subject_ids))

        unknown_subject_ids = [
            sid for sid in deduped_requested if self._subject_repository.get(sid) is None
        ]
        if unknown_subject_ids:
            raise CourseConfirmValidationError(
                f"data/master/subjects.jsonl에 없는 subject_id: {unknown_subject_ids}"
            )

        # 이 세션의 이번 업로드에서 실제로 나온 후보(matched_subject_id가 있는 high/low)
        # 만 확정할 수 있다 — 다른 세션 후보를 가져오거나 임의의 ID를 끼워 넣을 수 없다.
        # unmatched 후보는 matched_subject_id가 None이라 애초에 이 집합에 들어오지 않는다.
        eligible_subject_ids = {
            c.matched_subject_id
            for c in planning_state.parsed_candidates
            if c.matched_subject_id is not None
        }
        not_from_this_upload = [sid for sid in deduped_requested if sid not in eligible_subject_ids]
        if not_from_this_upload:
            raise CourseConfirmValidationError(
                f"이번 업로드의 과목 후보에 없는 subject_id: {not_from_this_upload}"
            )

        # §1(17차): unmatched 후보(matched_subject_id가 없는 것들)는 이 Confirm 요청으로도
        # canonical subject_id를 지정할 방법이 없으므로 최종 CourseProfile까지 계속
        # unresolved_candidates로 넘긴다 — 임의로 어떤 과목에 연결하지 않는다.
        unresolved_candidates = [
            c for c in planning_state.parsed_candidates if c.matched_subject_id is None
        ]

        # 아직 Store에 아무것도 저장하지 않는다 — 추천 계산과 Policy Guard를 먼저 전부
        # 통과시킨다(원자성, §2). 여기서 예외가 나면 그대로 전파하고 끝난다.
        course_profile = self._course_planning_service.build_post_offering_course_profile(
            state, planning_state.selected_major_id, set(deduped_requested), unresolved_candidates
        )

        # 여기 도달했다는 건 계산·Guard가 전부 성공했다는 뜻 — 이제서야 Store에 반영한다.
        # planning_state는 Store.load()가 이미 방어적으로 복사해 돌려준 객체라 그대로
        # 고쳐도 Store 원본에는 영향이 없지만, 의도를 명확히 하려고 새 객체로 만든다.
        confirmed_state = planning_state.model_copy(
            update={
                "confirmed_offered_subject_ids": deduped_requested,
                "upload_status": "CONFIRMED",
            }
        )
        self._course_planning_store.save(confirmed_state)
        return course_profile
