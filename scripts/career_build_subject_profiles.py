"""고교 과목 Master + Subject-Trait Mapping 초안 (작업자 C 소유) — 설계안 §20.

과목명은 2022 개정 교육과정(교육부 고시 제2022-33호) 표기를 따른다. `subject_id`는
A의 `generate_subject_id(curriculum_code, canonical_subject_name)`로 만들며, **학교별 원본
표기가 아니라 Alias 정규화를 마친 canonical 이름**을 넣는다 — 원본 표기를 그대로 해시하면
같은 과목이 학교마다 다른 ID를 받는다(§ids.py).

출력:
    data/master/subjects.jsonl               SubjectProfile
    data/master/subject_aliases.jsonl        Alias → canonical 과목명 (Parser가 쓴다)
    data/drafts/subject_trait_mappings/*.json  등급·근거·DraftEntry

실행:
    python scripts/career_build_subject_profiles.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.ids import generate_subject_id  # noqa: E402
from src.schemas.course import SubjectProfile  # noqa: E402
from src.schemas.review import DraftEntry, DraftReviewStage  # noqa: E402

CURRICULUM_CODE = "2022-33"  # 교육부 고시 제2022-33호 (2022 개정 교육과정)
SOURCE_URL = "https://ncic.re.kr/mobile.kri.org4.inventoryList.do"
AS_OF = date(2026, 8, 21)
AUTHOR_ID = "worker_c"

_KNOWN_TRAITS = {t.trait_id for t in VERTICAL_SLICE_TRAITS}

# (canonical 과목명, 교과(군), 과목 구분, 관련 전공, {trait: 등급}, 근거, [원본 표기 Alias])
SUBJECTS: list[tuple[str, str, str, list[str], dict[str, int], str, list[str]]] = [
    (
        "공통국어1", "국어", "공통과목", ["media_communication", "education"],
        {"information_comparison": 2, "audience_response_prediction": 1},
        "읽기·쓰기 전 영역을 다루는 공통과목이라 특정 Trait로 좁히지 않고 정보 비교만 2로 둔다.",
        ["국어", "공통국어"],
    ),
    (
        "화법과 언어", "국어", "일반선택", ["media_communication", "education", "psychology"],
        {"audience_response_prediction": 3, "opinion_mediation": 2, "emotional_interpretation": 2},
        "말하기 상황에서 청자 반응을 고려하는 활동이 성취기준의 중심이라 반응 예측 3.",
        ["화법과언어", "화법과 작문"],
    ),
    (
        "주제 탐구 독서", "국어", "진로선택", ["media_communication", "psychology", "education"],
        {"causal_analysis": 2, "information_comparison": 3, "planning": 2},
        "스스로 탐구 주제를 정하고 여러 자료를 대조하는 과목이라 정보 비교 3.",
        ["주제탐구독서", "심화국어"],
    ),
    (
        "매체 의사소통", "국어", "융합선택", ["media_communication", "design"],
        {"audience_response_prediction": 3, "visual_expression": 2, "change_adaptation": 2},
        "매체 수용자와 매체 변화 자체를 다루므로 반응 예측 3, 변화 대응 2.",
        ["매체의사소통", "언어와 매체"],
    ),
    (
        "공통수학1", "수학", "공통과목", ["computer_science", "mechanical_engineering"],
        {"pattern_finding": 2, "causal_analysis": 2},
        "대수·함수 규칙을 다루는 공통과목. 특정 진로로 좁히지 않는다.",
        ["수학", "공통수학"],
    ),
    (
        "미적분Ⅱ", "수학", "진로선택", ["mechanical_engineering", "computer_science", "life_science"],
        {"causal_analysis": 3, "pattern_finding": 2},
        "변화율로 현상을 설명하는 과목이라 원인 분석 3.",
        ["미적분2", "미적분 II", "미적분"],
    ),
    (
        "확률과 통계", "수학", "일반선택", ["psychology", "business_administration", "life_science"],
        {"pattern_finding": 3, "information_comparison": 2},
        "자료에서 규칙과 분포를 읽어내는 활동이 중심이라 패턴 탐색 3.",
        ["확률과통계", "확통"],
    ),
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
        "정보", "기술·가정/정보", "일반선택", ["computer_science"],
        {"tool_utilization": 3, "causal_analysis": 2, "pattern_finding": 2, "planning": 2},
        "문제를 프로그램으로 해결하는 과목이라 도구 활용 3.",
        ["정보과학", "컴퓨터"],
    ),
    (
        "인공지능 기초", "기술·가정/정보", "진로선택", ["computer_science"],
        {"tool_utilization": 3, "pattern_finding": 3, "causal_analysis": 2},
        "데이터에서 규칙을 학습시키는 과정이라 패턴 탐색 3.",
        ["인공지능기초", "AI기초", "인공지능"],
    ),
    (
        "데이터 과학", "기술·가정/정보", "융합선택", ["computer_science", "business_administration"],
        {"pattern_finding": 3, "information_comparison": 3, "tool_utilization": 2},
        "자료 수집·비교·해석이 전 과정이라 정보 비교 3.",
        ["데이터과학", "빅데이터"],
    ),
    (
        "소프트웨어와 생활", "기술·가정/정보", "융합선택", ["computer_science", "design"],
        {"tool_utilization": 3, "audience_response_prediction": 2, "immediate_execution": 2},
        "생활 문제를 소프트웨어로 바로 만들어 보는 과목이라 즉시 실행 2.",
        ["소프트웨어와생활", "SW와 생활"],
    ),
    (
        "창의 공학 설계", "기술·가정/정보", "진로선택", ["mechanical_engineering", "design"],
        {"tool_utilization": 3, "planning": 3, "immediate_execution": 2, "visual_expression": 2},
        "설계-제작-개선 주기를 직접 도는 과목이라 계획 3, 도구 활용 3.",
        ["창의공학설계", "공학일반"],
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


def build() -> tuple[list[SubjectProfile], list[dict]]:
    drafts_dir = ROOT / "data" / "drafts" / "subject_trait_mappings"
    drafts_dir.mkdir(parents=True, exist_ok=True)
    master_dir = ROOT / "data" / "master"
    master_dir.mkdir(parents=True, exist_ok=True)

    profiles: list[SubjectProfile] = []
    aliases: list[dict] = []

    for label, subject_group, category, major_ids, grades, rationale, alias_list in SUBJECTS:
        unknown = set(grades) - _KNOWN_TRAITS
        if unknown:
            raise SystemExit(f"{label}: Ontology에 없는 trait_id {sorted(unknown)}")

        subject_id = generate_subject_id(CURRICULUM_CODE, label)
        profile = SubjectProfile(
            subject_id=subject_id,
            label=label,
            trait_vector={t: normalize_grade(g) for t, g in grades.items()},
            related_major_ids=major_ids,
            source_id=SOURCE_URL,
        )
        profiles.append(profile)

        # canonical 표기 자신도 Alias 표에 넣는다 — Parser는 Alias 표만 보고 매칭한다.
        for alias in [label, *alias_list]:
            aliases.append(
                {
                    "alias": alias,
                    "canonical_subject_name": label,
                    "subject_id": subject_id,
                    "curriculum_code": CURRICULUM_CODE,
                }
            )

        entry = DraftEntry(
            draft_id=f"subject_trait_mapping_{subject_id}",
            draft_type="subject_trait_mapping",
            author_id=AUTHOR_ID,
            review_stage=DraftReviewStage.DRAFT,
            source_url=SOURCE_URL,
            as_of_date=AS_OF,
            notes="2022 개정 교육과정 과목 성취기준 서술을 근거로 C가 매긴 등급 초안.",
        )
        payload = {
            "draft_entry": json.loads(entry.model_dump_json()),
            "subject_id": subject_id,
            "label": label,
            "subject_group": subject_group,
            "subject_category": category,
            "curriculum_code": CURRICULUM_CODE,
            "trait_grades": grades,
            "rationale": rationale,
            "related_major_ids": major_ids,
            "derived_profile": json.loads(profile.model_dump_json()),
        }
        (drafts_dir / f"{subject_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    (master_dir / "subjects.jsonl").write_text(
        "".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8"
    )
    (master_dir / "subject_aliases.jsonl").write_text(
        "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in aliases), encoding="utf-8"
    )
    return profiles, aliases


if __name__ == "__main__":
    built, alias_rows = build()
    duplicated = {
        a["alias"] for a in alias_rows if sum(1 for b in alias_rows if b["alias"] == a["alias"]) > 1
    }
    if duplicated:
        raise SystemExit(f"같은 alias가 여러 과목을 가리킨다: {sorted(duplicated)}")
    print(f"SubjectProfile {len(built)}개, Alias {len(alias_rows)}행")
