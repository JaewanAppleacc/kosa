"""과목 정본(`data/master/subjects.jsonl`) + Alias 표 + Draft 결정론적 빌드.

2026-08-24 14차 리뷰(A): 원래 전체가 C 지시서 §3("고교 과목 Master + Subject-Trait Mapping
초안을 작성한다")에 따른 C 소유 파일이었다 — `SUBJECTS` 튜플에 사람이 직접 매긴 등급을
그대로 `trait_vector`로 썼다(공식 근거 없는 손입력, 12차 리뷰 이전의 Major Profile과 같은
문제). 이번 라운드는 대표 전공 3개(media_communication/hci_ux/industrial_engineering)
후보로 논의된 12개 과목만 실제 2022 개정 교육과정 공식 성취기준 근거로 옮긴다 — 나머지
6개(이번 라운드의 IE·HCI·미디어 후보 목록에 없었던 과목)는 C의 원래 `SUBJECTS` 항목을
`LEGACY_SUBJECTS`에 그대로 보존한다(§14 "새로운 과목 대량 수집 안 함"과 같은 정신).

두 근거 소스(12개 과목만):
    data/master/subject_trait_mapping_evidence.jsonl  — "이 과목에서 이 Trait를 관찰할
        수 있는가"(공식 성취기준 근거). EVIDENCED/NO_DIRECT_EVIDENCE만 trait_vector에
        반영한다 — UNMAPPED/REVIEW_REQUIRED는 0점이 아니라 Vector Key 자체에서 뺀다.
    data/master/subject_major_link_evidence.jsonl     — "이 과목이 이 전공과 관련
        있는가"(과목 성취기준 ↔ 전공 공식 교육과정의 직접 대응). RELATED만
        related_major_ids에 반영한다. media_communication 기존 연결 4개도 이번
        라운드에서 다시 검토했고, 자동 승인하지 않았다(§1/§2) — 공통국어1·주제 탐구
        독서는 REVIEW_REQUIRED로 내려가 related_major_ids에서 media_communication이
        빠졌고, 화법과 언어·매체 의사소통만 RELATED로 남았다.

`subject_id`는 여전히 A의 `generate_subject_id(curriculum_code, canonical_subject_name)`로
결정론적으로 만든다(§4 "기존 subject_id는 바꾸지 마세요" — label을 안 바꿨으니 ID도
그대로 재현된다. `scripts/career_audit_data_quality.py::audit_subjects`가 이 재현성을
검사한다).

출력:
    data/master/subjects.jsonl                 SubjectProfile 18개
    data/master/subject_aliases.jsonl           Alias → canonical 과목명 (Parser가 쓴다)
    data/drafts/subject_trait_mappings/*.json   등급·근거·DraftEntry (검토 대상)

실행:
    PYTHONPATH=. python scripts/career_build_subject_profiles.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.ids import generate_subject_id  # noqa: E402
from src.schemas.course import SubjectProfile  # noqa: E402
from src.schemas.review import DraftEntry, DraftReviewStage  # noqa: E402
from src.services.subject_major_link_evidence import (  # noqa: E402
    SubjectMajorLinkRecord,
    load_subject_major_link_evidence,
)
from src.services.subject_trait_mapping_evidence import (  # noqa: E402
    SubjectTraitMappingRecord,
    load_subject_trait_mapping_evidence,
)

MASTER_DIR = ROOT / "data" / "master"
DRAFTS_DIR = ROOT / "data" / "drafts" / "subject_trait_mappings"

CURRICULUM_CODE = "2022-33"  # 교육부 고시 제2022-33호 (2022 개정 교육과정)
NCIC_URL = "https://ncic.re.kr/mobile.kri.org4.inventoryList.do"
MOE_URL = "https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=141&lev=0&statusYN=W&s=moe&m=0404&opType=N&boardSeq=93458"

LEGACY_AS_OF = date(2026, 8, 21)
TOUCHED_AS_OF = date(2026, 8, 24)

# Vertical Slice 대표 전공 3개 — 이번 라운드가 근거 기반으로 다시 정한 major_id만
# 여기서 다룬다. 다른 전공(GRADES류)은 각 튜플의 major_ids로 그대로 보존한다.
VERTICAL_SLICE_MAJOR_IDS = ("media_communication", "hci_ux", "industrial_engineering")

# (canonical 과목명, 교과(군), 과목 구분, 관련 전공, {trait: 등급}, 근거, [원본 표기 Alias])
# 2026-08-24 14차 리뷰가 건드리지 않은 6개 과목 — C의 원래 손입력 값을 그대로 보존한다
# (재조사하지 않음). IE·HCI·미디어 후보 목록에 없었던 과목들이다.
LEGACY_SUBJECTS: list[tuple[str, str, str, list[str], dict[str, int], str, list[str]]] = [
    (
        "통합과학1", "과학", "공통과목", ["life_science", "mechanical_engineering"],
        {"causal_analysis": 2, "pattern_finding": 2},
        "현상의 원리를 관찰·설명하는 공통과목.",
        ["통합과학", "과학"],
    ),
    (
        "물리학", "과학", "일반선택", ["mechanical_engineering", "computer_science"],
        {"causal_analysis": 3, "tool_utilization": 2, "pattern_finding": 2},
        "실험으로 원인-결과를 규명하고 장치를 다루므로 원인 분석 3, 도구 활용 2.",
        ["물리", "물리학I", "물리학1"],
    ),
    (
        "생명과학", "과학", "일반선택", ["life_science", "psychology"],
        {"causal_analysis": 3, "pattern_finding": 3, "information_comparison": 2},
        "관찰 자료에서 규칙을 찾고 원인을 설명하는 활동이 함께 있어 둘 다 3.",
        ["생명과학I", "생명과학1", "생물"],
    ),
    (
        "미술 창작", "예술", "진로선택", ["design"],
        {"visual_expression": 3, "audience_response_prediction": 2},
        "시각적 표현이 과목 목표 자체라 3.",
        ["미술창작", "미술"],
    ),
    (
        "사회문제 탐구", "사회", "융합선택", ["psychology", "education", "business_administration"],
        {"causal_analysis": 3, "information_comparison": 3, "opinion_mediation": 2},
        "사회 현상의 원인을 자료로 규명하는 과목이라 둘 다 3.",
        ["사회문제탐구", "사회탐구"],
    ),
    (
        "인간과 심리", "사회", "융합선택", ["psychology", "education"],
        {"emotional_interpretation": 3, "causal_analysis": 2, "audience_response_prediction": 2},
        "행동과 정서를 해석하는 과목이라 감정 해석 3.",
        ["인간과심리", "심리학"],
    ),
]

# 2026-08-24 14차 리뷰가 근거 기반으로 옮긴 12개 과목 — (label, subject_group, category,
# 이번 라운드가 다시 근거화하지 않은 "기존 다른 전공(GRADES류)" 연결, [원본 표기 Alias]).
# trait_vector와 media_communication/hci_ux/industrial_engineering 연결은 근거 파일에서
# 결정론적으로 채워진다.
TOUCHED_SUBJECTS: list[tuple[str, str, str, list[str], list[str]]] = [
    ("공통국어1", "국어", "공통과목", ["education"], ["국어", "공통국어"]),
    ("화법과 언어", "국어", "일반선택", ["education", "psychology"], ["화법과언어", "화법과 작문"]),
    ("주제 탐구 독서", "국어", "진로선택", ["psychology", "education"], ["주제탐구독서", "심화국어"]),
    ("매체 의사소통", "국어", "융합선택", ["design"], ["매체의사소통", "언어와 매체"]),
    ("공통수학1", "수학", "공통과목", ["computer_science", "mechanical_engineering"], ["수학", "공통수학"]),
    ("미적분Ⅱ", "수학", "진로선택", ["mechanical_engineering", "computer_science", "life_science"], ["미적분2", "미적분 II", "미적분"]),
    ("확률과 통계", "수학", "일반선택", ["psychology", "business_administration", "life_science"], ["확률과통계", "확통"]),
    ("데이터 과학", "기술·가정/정보", "융합선택", ["computer_science", "business_administration"], ["데이터과학", "빅데이터"]),
    ("정보", "기술·가정/정보", "일반선택", ["computer_science"], ["정보과학", "컴퓨터"]),
    ("인공지능 기초", "기술·가정/정보", "진로선택", ["computer_science"], ["인공지능기초", "AI기초", "인공지능"]),
    ("소프트웨어와 생활", "기술·가정/정보", "융합선택", ["computer_science", "design"], ["소프트웨어와생활", "SW와 생활"]),
    ("창의 공학 설계", "기술·가정/정보", "진로선택", ["mechanical_engineering", "design"], ["창의공학설계", "공학일반"]),
]
TOUCHED_SUBJECT_LABELS: dict[str, str] = {
    generate_subject_id(CURRICULUM_CODE, label): label for label, *_ in TOUCHED_SUBJECTS
}

_KNOWN_TRAIT_IDS: set[str] | None = None


def _known_trait_ids() -> set[str]:
    global _KNOWN_TRAIT_IDS
    if _KNOWN_TRAIT_IDS is None:
        from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS

        _KNOWN_TRAIT_IDS = {t.trait_id for t in VERTICAL_SLICE_TRAITS}
    return _KNOWN_TRAIT_IDS


def build_touched_trait_vectors(
    trait_records: list[SubjectTraitMappingRecord],
) -> dict[str, dict[str, float]]:
    """subject_id -> {trait_id: 정규화값}. EVIDENCED/NO_DIRECT_EVIDENCE만 반영한다."""

    known = _known_trait_ids()
    by_subject: dict[str, dict[str, float]] = defaultdict(dict)
    for record in trait_records:
        if record.subject_id not in TOUCHED_SUBJECT_LABELS:
            raise SystemExit(
                f"subject_trait_mapping_evidence.jsonl: {record.subject_id!r}는 이번 라운드가 "
                f"다루는 12개 과목({sorted(TOUCHED_SUBJECT_LABELS)})에 없다"
            )
        if record.trait_id not in known:
            raise SystemExit(
                f"subject_trait_mapping_evidence.jsonl: {record.subject_id}/{record.trait_id} — "
                "현재 Trait Ontology에 없는 trait_id다"
            )
        if record.mapping_status not in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
            continue  # UNMAPPED/REVIEW_REQUIRED — Vector Key 자체에 안 넣는다.
        if record.trait_id in by_subject[record.subject_id]:
            raise SystemExit(f"{record.subject_id}: trait_id 중복 Mapping 레코드 {record.trait_id!r}")
        by_subject[record.subject_id][record.trait_id] = normalize_grade(record.grade)
    return dict(by_subject)


def build_touched_activity_summaries(
    trait_records: list[SubjectTraitMappingRecord],
) -> dict[str, str]:
    """subject_id -> 대표 학습 활동 한 줄(추천 이유용, §4). EVIDENCED 레코드 중 grade가
    가장 높은 것을 고르고, 동점이면 trait_id 알파벳순으로 하나를 결정론적으로 고른다 —
    "여러 활동 중 아무거나"가 아니라 항상 같은 입력에서 같은 결과가 나오게 하기 위함."""

    by_subject: dict[str, list[SubjectTraitMappingRecord]] = defaultdict(list)
    for record in trait_records:
        if record.mapping_status == "EVIDENCED":
            by_subject[record.subject_id].append(record)

    summaries: dict[str, str] = {}
    for subject_id, records in by_subject.items():
        best = min(records, key=lambda r: (-r.grade, r.trait_id))
        summaries[subject_id] = best.activity_summary
    return summaries


def build_touched_related_major_ids(
    link_records: list[SubjectMajorLinkRecord],
) -> dict[str, list[str]]:
    """subject_id -> Vertical Slice 대표 전공 중 RELATED로 확정된 major_id 목록(정렬됨)."""

    by_subject: dict[str, set[str]] = defaultdict(set)
    for record in link_records:
        if record.subject_id not in TOUCHED_SUBJECT_LABELS:
            raise SystemExit(
                f"subject_major_link_evidence.jsonl: {record.subject_id!r}는 이번 라운드가 "
                f"다루는 12개 과목에 없다"
            )
        if record.major_id not in VERTICAL_SLICE_MAJOR_IDS:
            raise SystemExit(
                f"subject_major_link_evidence.jsonl: {record.major_id!r}는 Vertical Slice "
                f"대표 전공 3개({VERTICAL_SLICE_MAJOR_IDS})에 없다"
            )
        if record.link_status == "RELATED":
            by_subject[record.subject_id].add(record.major_id)
    return {subject_id: sorted(majors) for subject_id, majors in by_subject.items()}


def build() -> tuple[list[SubjectProfile], list[dict], list[Path]]:
    trait_records = load_subject_trait_mapping_evidence()
    link_records = load_subject_major_link_evidence()

    touched_trait_vectors = build_touched_trait_vectors(trait_records)
    touched_related_majors = build_touched_related_major_ids(link_records)
    touched_activity_summaries = build_touched_activity_summaries(trait_records)

    missing_trait_evidence = set(TOUCHED_SUBJECT_LABELS) - set(touched_trait_vectors)
    if missing_trait_evidence:
        raise SystemExit(
            f"subject_trait_mapping_evidence.jsonl에 근거 레코드가 아예 없는 과목: "
            f"{sorted(missing_trait_evidence)} — UNMAPPED로라도 명시적으로 기록해야 한다"
        )
    missing_activity_summary = set(TOUCHED_SUBJECT_LABELS) - set(touched_activity_summaries)
    if missing_activity_summary:
        raise SystemExit(
            f"EVIDENCED Trait가 하나도 없어 대표 학습 활동을 만들 수 없는 과목: "
            f"{sorted(missing_activity_summary)} — 추천 이유에 넣을 활동을 지어내지 않는다. "
            "이 과목이 실제로 어느 전공과도 EVIDENCED Trait로 연결되지 않는다면, 이번 라운드의 "
            "12개 대상 목록(TOUCHED_SUBJECTS)에서 빼는 게 맞는지 다시 검토하세요."
        )

    evidence_by_subject: dict[str, list[SubjectTraitMappingRecord]] = defaultdict(list)
    for record in trait_records:
        evidence_by_subject[record.subject_id].append(record)
    link_evidence_by_subject: dict[str, list[SubjectMajorLinkRecord]] = defaultdict(list)
    for record in link_records:
        link_evidence_by_subject[record.subject_id].append(record)

    profiles: list[SubjectProfile] = []
    aliases: list[dict] = []
    written: list[Path] = []

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    MASTER_DIR.mkdir(parents=True, exist_ok=True)

    # --- Legacy 6개: C의 원래 손입력 방식 그대로(재조사하지 않음) ---
    for label, subject_group, category, major_ids, grades, rationale, alias_list in LEGACY_SUBJECTS:
        unknown = set(grades) - _known_trait_ids()
        if unknown:
            raise SystemExit(f"{label}: Ontology에 없는 trait_id {sorted(unknown)}")

        subject_id = generate_subject_id(CURRICULUM_CODE, label)
        profile = SubjectProfile(
            subject_id=subject_id, label=label,
            trait_vector={t: normalize_grade(g) for t, g in grades.items()},
            related_major_ids=major_ids, source_id=NCIC_URL,
        )
        profiles.append(profile)

        for alias in [label, *alias_list]:
            aliases.append(
                {
                    "alias": alias, "canonical_subject_name": label,
                    "subject_id": subject_id, "curriculum_code": CURRICULUM_CODE,
                }
            )

        entry = DraftEntry(
            draft_id=f"subject_trait_mapping_{subject_id}", draft_type="subject_trait_mapping",
            author_id="worker_c", review_stage=DraftReviewStage.DRAFT, source_url=NCIC_URL,
            as_of_date=LEGACY_AS_OF,
            notes="2022 개정 교육과정 과목 성취기준 서술을 근거로 C가 매긴 등급 초안.",
        )
        payload = {
            "draft_entry": json.loads(entry.model_dump_json()),
            "subject_id": subject_id, "label": label, "subject_group": subject_group,
            "subject_category": category, "curriculum_code": CURRICULUM_CODE,
            "trait_grades": grades, "rationale": rationale, "related_major_ids": major_ids,
            "derived_profile": json.loads(profile.model_dump_json()),
        }
        path = DRAFTS_DIR / f"{subject_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)

    # --- Touched 12개: 2022 개정 교육과정 공식 성취기준 근거 기반(§2/§3/§4) ---
    for label, subject_group, category, legacy_major_ids, alias_list in TOUCHED_SUBJECTS:
        subject_id = generate_subject_id(CURRICULUM_CODE, label)
        vs_majors = touched_related_majors.get(subject_id, [])
        # 기존 손입력 순서(legacy_major_ids)를 그대로 유지하고, 이번 라운드에서 새로 RELATED로
        # 확정된 Vertical Slice 전공만 뒤에 정렬해서 덧붙인다.
        related = list(legacy_major_ids) + [m for m in vs_majors if m not in legacy_major_ids]

        profile = SubjectProfile(
            subject_id=subject_id, label=label, trait_vector=touched_trait_vectors[subject_id],
            related_major_ids=related, source_id=MOE_URL,
            activity_summary=touched_activity_summaries[subject_id],
        )
        profiles.append(profile)

        for alias in [label, *alias_list]:
            aliases.append(
                {
                    "alias": alias, "canonical_subject_name": label,
                    "subject_id": subject_id, "curriculum_code": CURRICULUM_CODE,
                }
            )

        entry = DraftEntry(
            draft_id=f"subject_trait_mapping_{subject_id}", draft_type="subject_trait_mapping",
            author_id="worker_a", review_stage=DraftReviewStage.DRAFT, source_url=None,
            as_of_date=TOUCHED_AS_OF,
            notes=(
                "실제 2022 개정 교육과정(교육부 고시 제2022-33호) 공식 성취기준 근거는 "
                "data/master/subject_trait_mapping_evidence.jsonl, 전공 연결 근거는 "
                "data/master/subject_major_link_evidence.jsonl 참고. UNMAPPED/REVIEW_REQUIRED "
                "Trait·전공은 Vector·related_major_ids에서 뺐다(공식 근거를 찾지 못함 ≠ "
                "중요도 0/관련 없음)."
            ),
        )
        payload = {
            "draft_entry": json.loads(entry.model_dump_json()),
            "subject_id": subject_id, "label": label, "subject_group": subject_group,
            "subject_category": category, "curriculum_code": CURRICULUM_CODE,
            "trait_evidence_summary": [
                {"trait_id": r.trait_id, "mapping_status": r.mapping_status, "grade": r.grade}
                for r in sorted(evidence_by_subject[subject_id], key=lambda r: r.trait_id)
            ],
            "major_link_summary": [
                {"major_id": r.major_id, "link_status": r.link_status}
                for r in sorted(link_evidence_by_subject[subject_id], key=lambda r: r.major_id)
            ],
            "related_major_ids": related,
            "derived_profile": json.loads(profile.model_dump_json()),
        }
        path = DRAFTS_DIR / f"{subject_id}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)

    profiles.sort(key=lambda p: p.subject_id)

    master_path = MASTER_DIR / "subjects.jsonl"
    master_path.write_text("".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8")
    written.append(master_path)

    alias_path = MASTER_DIR / "subject_aliases.jsonl"
    alias_path.write_text(
        "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in aliases), encoding="utf-8"
    )
    written.append(alias_path)

    return profiles, aliases, written


def main() -> None:
    profiles, alias_rows, written = build()
    duplicated = {
        a["alias"] for a in alias_rows if sum(1 for b in alias_rows if b["alias"] == a["alias"]) > 1
    }
    if duplicated:
        raise SystemExit(f"같은 alias가 여러 과목을 가리킨다: {sorted(duplicated)}")
    print(f"SubjectProfile {len(profiles)}개, Alias {len(alias_rows)}행")
    for path in written:
        print(f"  {path.relative_to(ROOT)}")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
