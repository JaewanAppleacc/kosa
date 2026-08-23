"""Canonical Major Mapping — 설계안 §17, C 지시서 §3.

파이프라인은 지시서 순서 그대로다.

    Exact / Alias Match  →  Embedding Candidate Search  →  (필요 시) LLM Structured

**자동 확정은 Exact·Alias 단계에서만 일어난다.** Embedding과 LLM 단계 결과는 항상
`REVIEW_REQUIRED`로 남긴다 — 지시서 §3 "낮은 확신 결과는 자동 확정하지 않고
REVIEW_REQUIRED로 남긴다"와 §8 완료 조건 "미확정 결과가 자동 확정되지 않고 별도로
표시된다"를 코드로 강제하기 위해서다. 사람이 검토해 확정하는 경로는 `confirm()`뿐이다.

`CanonicalMappingResult.evidence`에는 `confidence: 0.84` 같은 미보정 수치를 적지 않는다
(Schema docstring). 대신 어떤 규칙이 어떤 이유로 걸렸는지를 문장으로 남긴다.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, field_validator

from src.rag.embed import Embedder, cosine_similarity, default_embedder
from src.schemas.major import CanonicalMappingResult, Department

# A3 지시서(2026-08-24) §4/§5: 학생 화면에 노출되는 설명이라 "취업 보장"류 표현을
# 막는다 — Trait Matching 결과 문구("당신에게 잘 맞습니다")도 여기 섞이면 이 필드가
# 관련도 근거처럼 오인된다(§9 "관련도 근거 문장이 아님"과 정확히 같은 이유).
_FORBIDDEN_DESCRIPTION_PHRASES = (
    "취업이 잘", "취업률", "합격이", "합격률", "성공적인", "당신에게", "당신의 적성",
    "가장 적합", "잘 맞습니다", "잘 맞는", "적성에 맞",
)
_MAX_DESCRIPTION_LENGTH = 120

MAPPING_VERSION = "canonical_mapping_v0.1"

# 학과명 표기에서 의미를 바꾸지 않는 장식들
_BRACKETED = re.compile(r"[「」『』〈〉<>\[\]()（）]")
_PARENTHETICAL_NOTE = re.compile(r"\s*[(（][^)）]*[)）]\s*")
_SPACES = re.compile(r"\s+")
# 학과명 끝에 붙어 조직 형태만 나타내는 접미. 제거해야 "컴퓨터공학부"와 "컴퓨터공학과"가
# 같은 이름으로 모인다.
_ORG_SUFFIXES = ("학부", "학과", "학군", "전공", "계열", "과정", "부", "과")
# Embedding 단계에서 사람에게 넘길 후보 수. 이 단계 결과는 어차피 자동 확정되지 않고
# 사람이 고르므로, 후보 수는 '검토자가 한눈에 비교할 수 있는 개수'로 정한다. 1개면 검토가
# 아니라 승인 버튼이 되고, 5개 이상이면 대부분 명백히 무관한 항목이라 검토 피로만 늘린다.
_EMBEDDING_CANDIDATE_COUNT = 3


class CanonicalMajorEntry(BaseModel):
    """`data/master/canonical_majors.jsonl`의 한 행.

    A3 지시서(2026-08-24) §3/§4/§5: `description`은 학생 화면에 그대로 노출되는
    전공 설명 문장이다(고등학생이 이해할 수 있는 1~2문장, 약 40~100자) — Runtime
    LLM이 즉흥 생성하지 않고 이 정본 JSONL에서 결정론적으로 조회만 한다. `keywords`를
    쉼표로 이어붙인 것이 아니라 실제 문장이어야 한다."""

    major_id: str
    label: str
    description: str
    aliases: list[str] = []
    keywords: list[str] = []
    source_url: str
    as_of_date: str

    @field_validator("description")
    @classmethod
    def _validate_description(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("description은 빈 문자열이나 공백만 있는 값을 허용하지 않는다")
        if len(stripped) > _MAX_DESCRIPTION_LENGTH:
            raise ValueError(
                f"description이 너무 길다({len(stripped)}자, 최대 {_MAX_DESCRIPTION_LENGTH}자): {stripped!r}"
            )
        if "%" in stripped or re.search(r"\d+\s*점", stripped):
            raise ValueError(f"description에 내부 숫자 점수·백분율 표현을 넣을 수 없다: {stripped!r}")
        lowered = stripped.replace(" ", "")
        for phrase in _FORBIDDEN_DESCRIPTION_PHRASES:
            if phrase.replace(" ", "") in lowered:
                raise ValueError(f"description에 금지 표현이 포함됐다({phrase!r}): {stripped!r}")
        return stripped

    def match_texts(self) -> list[str]:
        return [self.label, *self.aliases]

    def embedding_text(self) -> str:
        # A3 지시서 §5: description을 embedding_text에 자동으로 섞지 않는다 — 설명
        # 필드 추가가 Canonical Mapping(Embedding 후보 검색) 결과를 조용히 바꾸면
        # 안 된다. 기존 그대로 label+aliases+keywords만 쓴다.
        return " ".join([self.label, *self.aliases, *self.keywords])


class MajorClassifier(Protocol):
    """LLM Structured Classification 자리. 지시서 §3 "필요한 경우 LLM Structured
    Classification을 구현한다"에 해당한다. 실제 LLM 호출은 A가 소유한 `src/llm/`을 쓰거나
    별도 구현체를 주입한다 — Mapper는 인터페이스만 안다."""

    def classify(self, department: Department, candidate_major_ids: list[str]) -> str | None: ...


def normalize_department_name(raw: str) -> str:
    """학과명 표기 정규화. 의미를 바꾸지 않는 장식만 제거한다.

    "「경영학과」", "경영학과 (주간)", "　심리학과 " 가 전부 같은 이름으로 모이도록 한다.
    조직 형태 접미(학부/학과/전공…)까지 떼는 것은 **매칭 키를 만들 때만**이고, 학생에게
    보여줄 이름은 원 표기를 그대로 쓴다 — 여기서 만든 값을 표시용으로 쓰면 안 된다.
    """

    text = unicodedata.normalize("NFKC", raw)
    text = _PARENTHETICAL_NOTE.sub(" ", text)
    text = _BRACKETED.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text


def match_keys(name: str) -> list[str]:
    """정규화된 이름에서 만들 수 있는 매칭 키를 긴 것부터 돌려준다.

    접미를 하나만 떼면 안 된다 — "컴퓨터공학부"는 "학부"를 떼면 "컴퓨터공"이 되지만
    실제로 떼야 할 것은 "부"다. 어느 쪽이 맞는지는 표기마다 달라서, 뗄 수 있는 후보를
    전부 만들어 두고 **긴 키부터** 대조한다. 긴 키가 먼저 걸리면 짧은 키의 우연한 충돌
    ("컴퓨터공" 같은 조각)이 결과를 흔들지 못한다.
    """

    text = normalize_department_name(name).replace(" ", "")
    keys = [text]
    for suffix in _ORG_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            keys.append(text[: -len(suffix)])
    return sorted(dict.fromkeys(k for k in keys if k), key=len, reverse=True)


def match_key(name: str) -> str:
    """표기 그대로의 매칭 키(접미 제거 없음). 부분 문자열 대조에 쓴다."""

    return normalize_department_name(name).replace(" ", "")


def load_canonical_majors(path: Path) -> list[CanonicalMajorEntry]:
    return [
        CanonicalMajorEntry.model_validate(json.loads(line))
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class CanonicalMapper:
    def __init__(
        self,
        entries: list[CanonicalMajorEntry],
        embedder: Embedder | None = None,
        classifier: MajorClassifier | None = None,
        mapping_version: str = MAPPING_VERSION,
    ) -> None:
        if not entries:
            raise ValueError("canonical major 목록이 비어 있다")
        self._entries = entries
        self._by_id = {e.major_id: e for e in entries}
        self._embedder = embedder or default_embedder()
        self._classifier = classifier
        self._mapping_version = mapping_version

        self._exact: dict[str, list[str]] = {}
        for entry in entries:
            for text in entry.match_texts():
                for key in match_keys(text):
                    self._exact.setdefault(key, []).append(entry.major_id)

        self._vectors = dict(
            zip(
                [e.major_id for e in entries],
                self._embedder.embed([e.embedding_text() for e in entries]),
            )
        )

    # --- 단계별 ---

    def _exact_or_alias(self, keys: list[str]) -> tuple[str, list[str]]:
        """긴 키부터 대조해 처음 걸린 키와 그 키에 걸린 major 목록을 돌려준다."""

        for key in keys:
            hits = list(dict.fromkeys(self._exact.get(key, [])))
            if hits:
                return key, hits
        return keys[0] if keys else "", []

    def _alias_contained(self, key: str) -> list[str]:
        """정규화된 학과명이 Alias를 포함하는 경우. "컴퓨터소프트웨어" ← "소프트웨어".

        더 긴 Alias가 걸린 쪽을 앞에 둔다 — 짧은 Alias는 우연히 겹칠 여지가 크다.
        """

        hits: list[tuple[int, str]] = []
        for entry in self._entries:
            longest = max(
                (len(match_key(t)) for t in entry.match_texts() if match_key(t) and match_key(t) in key),
                default=0,
            )
            if longest:
                hits.append((longest, entry.major_id))
        hits.sort(key=lambda item: (-item[0], item[1]))
        return [major_id for _, major_id in hits]

    def _embedding_candidates(self, department: Department) -> list[str]:
        query = f"{department.department_name} {department.college_name}"
        vector = self._embedder.embed([query])[0]
        scored = [
            (major_id, cosine_similarity(vector, v)) for major_id, v in self._vectors.items()
        ]
        scored.sort(key=lambda item: (-item[1], item[0]))
        return [major_id for major_id, _ in scored[:_EMBEDDING_CANDIDATE_COUNT]]

    # --- 진입점 ---

    def map(self, department: Department) -> CanonicalMappingResult:
        keys = match_keys(department.department_name)
        key, exact = self._exact_or_alias(keys)
        if len(exact) == 1:
            return CanonicalMappingResult(
                department_id=department.department_id,
                mapping_status="AUTO_MAPPED",
                primary_candidate=exact[0],
                secondary_candidates=[],
                mapping_method="exact_alias",
                evidence=[
                    f"정규화 학과명 매칭 키 '{key}'가 canonical major '{exact[0]}'의 "
                    f"label/alias와 정확히 일치",
                ],
                mapping_version=self._mapping_version,
            )
        if len(exact) > 1:
            return CanonicalMappingResult(
                department_id=department.department_id,
                mapping_status="REVIEW_REQUIRED",
                primary_candidate=exact[0],
                secondary_candidates=exact[1:],
                mapping_method="exact_alias",
                evidence=[
                    f"매칭 키 '{key}'가 여러 canonical major({', '.join(exact)})의 alias에 "
                    f"동시에 걸렸다 — alias 표를 정리하기 전에는 자동 확정하지 않는다",
                ],
                mapping_version=self._mapping_version,
            )

        contained = self._alias_contained(match_key(department.department_name))
        if len(contained) == 1:
            return CanonicalMappingResult(
                department_id=department.department_id,
                mapping_status="AUTO_MAPPED",
                primary_candidate=contained[0],
                secondary_candidates=[],
                mapping_method="exact_alias",
                evidence=[
                    f"정규화 학과명 '{key}'가 canonical major '{contained[0]}'의 alias를 "
                    f"부분 문자열로 포함하고, 다른 major의 alias에는 걸리지 않았다",
                ],
                mapping_version=self._mapping_version,
            )
        if len(contained) > 1:
            return CanonicalMappingResult(
                department_id=department.department_id,
                mapping_status="REVIEW_REQUIRED",
                primary_candidate=contained[0],
                secondary_candidates=contained[1:],
                mapping_method="exact_alias",
                evidence=[
                    f"'{key}'가 여러 major의 alias를 동시에 포함한다 "
                    f"({', '.join(contained)}) — 가장 긴 alias가 걸린 쪽을 1순위로 두되 "
                    f"자동 확정하지 않는다",
                ],
                mapping_version=self._mapping_version,
            )

        candidates = self._embedding_candidates(department)
        evidence = [
            "Exact·Alias 매칭 실패. 학과명+단과대학 텍스트 임베딩으로 후보를 순위만 뽑았다",
            f"후보 순위: {' > '.join(candidates)}",
            "임베딩 유사도는 보정되지 않은 값이라 자동 확정 근거로 쓰지 않는다 (§17)",
        ]
        method: str = "embedding_plus_curriculum"

        if self._classifier is not None:
            chosen = self._classifier.classify(department, candidates)
            if chosen in self._by_id:
                candidates = [chosen] + [c for c in candidates if c != chosen]
                method = "llm_structured"
                evidence.append(
                    f"LLM Structured Classification이 후보 중 '{chosen}'을 골랐다 — "
                    f"사람 검토 전에는 확정으로 보지 않는다"
                )
            else:
                evidence.append("LLM Structured Classification이 후보를 고르지 못했다")

        return CanonicalMappingResult(
            department_id=department.department_id,
            mapping_status="REVIEW_REQUIRED",
            primary_candidate=candidates[0],
            secondary_candidates=candidates[1:],
            mapping_method=method,  # type: ignore[arg-type]
            evidence=evidence,
            mapping_version=self._mapping_version,
        )

    def map_all(self, departments: list[Department]) -> list[CanonicalMappingResult]:
        return [self.map(d) for d in departments]


def confirm(
    result: CanonicalMappingResult, reviewer_id: str, chosen_major_id: str | None = None
) -> CanonicalMappingResult:
    """사람이 검토해 확정하는 유일한 경로. 코드가 스스로 CONFIRMED를 만들지 않는다."""

    major_id = chosen_major_id or result.primary_candidate
    secondary = [c for c in result.secondary_candidates if c != major_id]
    if result.primary_candidate != major_id:
        secondary = [result.primary_candidate] + secondary
    return result.model_copy(
        update={
            "mapping_status": "CONFIRMED",
            "primary_candidate": major_id,
            "secondary_candidates": secondary,
            "evidence": [*result.evidence, f"{reviewer_id}가 '{major_id}'로 확정"],
        }
    )


def review_required(results: list[CanonicalMappingResult]) -> list[CanonicalMappingResult]:
    """A에게 넘길 REVIEW_REQUIRED 목록 (지시서 §5)."""

    return [r for r in results if r.mapping_status == "REVIEW_REQUIRED"]
