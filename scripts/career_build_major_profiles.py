"""대표 전공 Major-Trait Mapping 초안 → MajorProfile 산출.

원래 전체가 C 지시서 §3("대표 전공 Profile 5~8개를 구축한다 / Major-Trait Mapping
초안을 작성하고 공식 근거를 연결한다")에 따른 C 소유 파일이었다.

2026-08-22 12차 리뷰(A): Vertical Slice 대표 전공 3개(media_communication/hci_ux/
industrial_engineering)만 실제 학과 공식 자료 기반 Evidence로 교체했다 — 아래
`build_evidence_based_profiles()`가 그 부분이고, A 소유다. 나머지 major(computer_
science/design/business_administration/psychology/mechanical_engineering/
education/life_science)는 여전히 C의 원래 GRADES 손입력 방식 그대로다(이번 작업
범위 밖). media_communication은 원래 GRADES에 있었지만 Evidence 기반으로 옮기며
GRADES/LABELS/RATIONALE에서 제거했다 — 정본이 두 곳에 남지 않게 하기 위함이다.

등급(0~3)만 사람이 손으로 매기고, 0/.33/.67/1.00 변환은 A의
`src/engines/trait_normalizer.normalize_grade()`를 그대로 호출한다 — 같은 정규화 정책을
데이터 모듈이 복제하지 않기 위해서다(C 지시서 §7 "A가 소유한 로직을 데이터 모듈에
복제하지 않는다").

**"공식 근거를 찾지 못함 ≠ Trait 중요도 0"**: Evidence 기반 3개 전공은 `major_trait_
mapping_evidence.jsonl`에서 `mapping_status="EVIDENCED"`인 Trait만 Vector에 넣는다.
`UNMAPPED`/`REVIEW_REQUIRED`인 Trait는 아예 그 전공의 Vector Key에서 빠진다(0.00으로
채우지 않는다) — matching_engine.py는 이미 `weight > 0`인 Key만 비교에 쓰므로, 이 방식이
"0.00으로 채우기"와 코드 동작상으로는 같은 결과를 내면서도("weight>0" 필터가 어차피
0.00도 걸러낸다) 의미상 정직하다(§16 매칭 공식 자체는 변경하지 않았다).

출력:
    data/drafts/major_trait_mappings/<major_id>.json   등급·근거·DraftEntry (검토 대상)
    data/master/major_profiles.jsonl                   MajorProfile (Schema 준수 산출물)

실행:
    python scripts/career_build_major_profiles.py
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

from src.data.trait_ontology.vertical_slice_traits import VERTICAL_SLICE_TRAITS  # noqa: E402
from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.schemas.major import MajorProfile  # noqa: E402
from src.schemas.review import DraftEntry, DraftReviewStage  # noqa: E402
from src.services.major_trait_mapping_evidence import (  # noqa: E402
    MajorTraitMappingRecord,
    load_major_trait_mapping_evidence,
)

AUTHOR_ID = "worker_c"
PROFILE_VERSION = "major_profile_v0.1"
AS_OF = date(2026, 8, 21)

CAREER_NET_MAJOR_URL = "https://www.career.go.kr/cnet/front/base/major/FunivMajorView.do"

_VECTOR_GROUP_BY_TRAIT = {t.trait_id: t.primary_vector_group for t in VERTICAL_SLICE_TRAITS}
_KNOWN_TRAIT_IDS = set(_VECTOR_GROUP_BY_TRAIT)

# 2026-08-22 12차(A): Evidence 기반으로 옮긴 3개 전공의 표시용 라벨. 이 3개는 GRADES
# 손입력 방식에서 완전히 빠져 major_trait_mapping_evidence.jsonl에서만 값을 가져온다.
EVIDENCE_BASED_MAJOR_LABELS: dict[str, str] = {
    "media_communication": "미디어·커뮤니케이션",
    "hci_ux": "HCI·UX",
    "industrial_engineering": "산업공학",
}
EVIDENCE_BASED_PROFILE_VERSION = "major_trait_mapping_v1"


def build_evidence_based_profiles(
    evidence_records: list[MajorTraitMappingRecord] | None = None,
    updated_at: datetime | None = None,
) -> list[MajorProfile]:
    """`major_trait_mapping_evidence.jsonl`을 읽어 EVIDENCED(§NO_DIRECT_EVIDENCE 포함)
    Trait만 Vector에 담은 MajorProfile을 만든다. UNMAPPED/REVIEW_REQUIRED Trait는 Vector
    Key 자체에서 뺀다("공식 근거를 찾지 못함 ≠ Trait 중요도 0") — matching_engine.py는
    이미 weight>0인 Key만 비교에 쓰므로 §16 매칭 공식은 그대로다."""

    records = evidence_records if evidence_records is not None else load_major_trait_mapping_evidence()
    now = updated_at or datetime(2026, 8, 22, tzinfo=timezone.utc)

    by_major: dict[str, list[MajorTraitMappingRecord]] = defaultdict(list)
    for record in records:
        if record.major_id not in EVIDENCE_BASED_MAJOR_LABELS:
            raise SystemExit(
                f"major_trait_mapping_evidence.jsonl: {record.major_id!r}는 "
                f"Vertical Slice 대표 전공 3개({sorted(EVIDENCE_BASED_MAJOR_LABELS)})에 없다"
            )
        if record.trait_id not in _KNOWN_TRAIT_IDS:
            raise SystemExit(
                f"major_trait_mapping_evidence.jsonl: {record.major_id}/{record.trait_id} — "
                "현재 Trait Ontology에 없는 trait_id다"
            )
        by_major[record.major_id].append(record)

    profiles: list[MajorProfile] = []
    for major_id in sorted(EVIDENCE_BASED_MAJOR_LABELS):
        major_records = by_major.get(major_id, [])
        seen_trait_ids = {r.trait_id for r in major_records}
        missing = _KNOWN_TRAIT_IDS - seen_trait_ids
        if missing:
            raise SystemExit(
                f"{major_id}: 현재 Trait Ontology 12개 중 {sorted(missing)}에 대한 "
                "Mapping 레코드 자체가 없다 — UNMAPPED로라도 명시적으로 기록해야 한다"
            )
        duplicated = [t for t in seen_trait_ids if sum(1 for r in major_records if r.trait_id == t) > 1]
        if duplicated:
            raise SystemExit(f"{major_id}: trait_id 중복 Mapping 레코드 {sorted(duplicated)}")

        vectors: dict[str, dict[str, float]] = {
            "interest": {}, "cognitive": {}, "work_style": {}, "environment": {},
        }
        source_urls: set[str] = set()
        for record in major_records:
            if record.mapping_status not in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
                continue  # UNMAPPED/REVIEW_REQUIRED — Vector Key 자체에 안 넣는다.
            group = _VECTOR_GROUP_BY_TRAIT[record.trait_id]
            vectors[group][record.trait_id] = normalize_grade(record.grade)  # type: ignore[arg-type]
            for evidence in record.evidence:
                source_urls.add(evidence.source_url)

        profiles.append(
            MajorProfile(
                major_id=major_id,
                label=EVIDENCE_BASED_MAJOR_LABELS[major_id],
                interest_vector=vectors["interest"],
                cognitive_vector=vectors["cognitive"],
                work_style_vector=vectors["work_style"],
                environment_vector=vectors["environment"],
                source_ids=sorted(source_urls),
                extraction_method="rule",
                review_status="draft",  # 실제 2인 교차검토 전에는 team_reviewed로 표시하지 않는다.
                profile_version=EVIDENCE_BASED_PROFILE_VERSION,
                updated_at=now,
            )
        )
    return profiles

# 등급 0~3. 근거는 전공별 교육목표·교육과정 서술에서 관찰되는 활동을 기준으로 매겼다.
# 0을 적은 Trait는 "그 전공에서 안 쓴다"가 아니라 "이 전공을 다른 전공과 구분하는 축이
# 아니다"라는 뜻이다 — §16 매칭은 상대 비교라 변별력 없는 축을 1로 채우면 전부 비슷해진다.
GRADES: dict[str, dict[str, int]] = {
    "computer_science": {
        "causal_analysis": 3,
        "pattern_finding": 3,
        "planning": 2,
        "immediate_execution": 2,
        "change_adaptation": 2,
        "collaboration_preference": 2,
        "opinion_mediation": 1,
        "emotional_interpretation": 0,
        "audience_response_prediction": 1,
        "visual_expression": 1,
        "information_comparison": 2,
        "tool_utilization": 3,
    },
    "design": {
        "causal_analysis": 1,
        "pattern_finding": 2,
        "planning": 2,
        "immediate_execution": 2,
        "change_adaptation": 2,
        "collaboration_preference": 2,
        "opinion_mediation": 1,
        "emotional_interpretation": 2,
        "audience_response_prediction": 3,
        "visual_expression": 3,
        "information_comparison": 1,
        "tool_utilization": 2,
    },
    "business_administration": {
        "causal_analysis": 2,
        "pattern_finding": 2,
        "planning": 3,
        "immediate_execution": 2,
        "change_adaptation": 2,
        "collaboration_preference": 3,
        "opinion_mediation": 3,
        "emotional_interpretation": 1,
        "audience_response_prediction": 2,
        "visual_expression": 0,
        "information_comparison": 2,
        "tool_utilization": 1,
    },
    "psychology": {
        "causal_analysis": 3,
        "pattern_finding": 2,
        "planning": 1,
        "immediate_execution": 0,
        "change_adaptation": 1,
        "collaboration_preference": 1,
        "opinion_mediation": 2,
        "emotional_interpretation": 3,
        "audience_response_prediction": 2,
        "visual_expression": 0,
        "information_comparison": 2,
        "tool_utilization": 1,
    },
    "mechanical_engineering": {
        "causal_analysis": 3,
        "pattern_finding": 2,
        "planning": 2,
        "immediate_execution": 2,
        "change_adaptation": 1,
        "collaboration_preference": 2,
        "opinion_mediation": 0,
        "emotional_interpretation": 0,
        "audience_response_prediction": 0,
        "visual_expression": 1,
        "information_comparison": 1,
        "tool_utilization": 3,
    },
    "education": {
        "causal_analysis": 2,
        "pattern_finding": 1,
        "planning": 3,
        "immediate_execution": 1,
        "change_adaptation": 2,
        "collaboration_preference": 3,
        "opinion_mediation": 3,
        "emotional_interpretation": 3,
        "audience_response_prediction": 2,
        "visual_expression": 0,
        "information_comparison": 1,
        "tool_utilization": 1,
    },
    "life_science": {
        "causal_analysis": 3,
        "pattern_finding": 3,
        "planning": 2,
        "immediate_execution": 1,
        "change_adaptation": 1,
        "collaboration_preference": 1,
        "opinion_mediation": 0,
        "emotional_interpretation": 0,
        "audience_response_prediction": 0,
        "visual_expression": 0,
        "information_comparison": 2,
        "tool_utilization": 2,
    },
}

LABELS: dict[str, str] = {
    "computer_science": "컴퓨터·소프트웨어",
    "design": "디자인",
    "business_administration": "경영학",
    "psychology": "심리학",
    "mechanical_engineering": "기계공학",
    "education": "교육학",
    "life_science": "생명과학",
}

# Trait별 등급 근거. 검토자가 "왜 3인가"를 되짚을 수 있어야 한다(C 지시서 §3
# "Question-Trait Mapping에 근거와 작성자를 기록한다"와 같은 요구를 Major에도 적용).
RATIONALE: dict[str, str] = {
    "computer_science": (
        "교육과정의 중심이 알고리즘·자료구조·시스템 설계라 원인 분석과 패턴 탐색이 3. "
        "실습·프로젝트 도구 사용이 상시적이라 tool_utilization 3. "
        "타인 감정 해석은 교육과정에서 직접 다루지 않아 0."
    ),
    "design": (
        "시각적 표현이 전공 정체성 자체라 3. 사용자 반응 예측(사용자 조사·UX)도 3. "
        "정보 비교는 상대적으로 비중이 낮아 1."
    ),
    "business_administration": (
        "조직 운영·전략 수립이라 계획 3, 협업 3, 의견 조정 3. "
        "시각적 표현은 전공 변별 축이 아니라 0."
    ),
    "psychology": (
        "행동의 원인 규명이 학문 목적이라 causal_analysis 3, 감정 해석 3. "
        "즉시 실행은 실험 설계·통제와 상충하는 방향이라 0."
    ),
    "mechanical_engineering": (
        "역학 원리 규명과 설계·제작 실습으로 causal_analysis 3, tool_utilization 3. "
        "대인 축(의견 조정·감정 해석·반응 예측)은 전공 변별 축이 아니라 0."
    ),
    "education": (
        "수업 설계(계획 3), 학습자 상호작용(협업 3·의견 조정 3·감정 해석 3)이 중심."
    ),
    "life_science": (
        "실험 설계와 데이터에서 규칙을 찾는 활동이 중심이라 causal_analysis 3, "
        "pattern_finding 3. 대인 축은 전공 변별 축이 아니라 0."
    ),
}

SOURCE_NOTE = (
    "커리어넷 학과정보(대분류·중분류 학과 설명)의 교육목표·주요 교과목 서술을 근거로 "
    "C가 등급을 매긴 초안이다. 등급 자체는 공식 수치가 아니라 팀 판단이며 A 검토 대상이다."
)


def _split_by_vector_group(grades: dict[str, int]) -> dict[str, dict[str, float]]:
    vectors: dict[str, dict[str, float]] = {
        "interest": {},
        "cognitive": {},
        "work_style": {},
        "environment": {},
    }
    for trait_id, grade in grades.items():
        group = _VECTOR_GROUP_BY_TRAIT[trait_id]
        vectors[group][trait_id] = normalize_grade(grade)
    return vectors


def build() -> tuple[list[MajorProfile], list[Path]]:
    known_trait_ids = set(_VECTOR_GROUP_BY_TRAIT)
    drafts_dir = ROOT / "data" / "drafts" / "major_trait_mappings"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    profiles: list[MajorProfile] = []
    written: list[Path] = []
    now = datetime(2026, 8, 21, tzinfo=timezone.utc)

    for major_id, grades in GRADES.items():
        unknown = set(grades) - known_trait_ids
        if unknown:
            raise SystemExit(f"{major_id}: Ontology에 없는 trait_id {sorted(unknown)}")
        missing = known_trait_ids - set(grades)
        if missing:
            raise SystemExit(f"{major_id}: 등급이 빠진 trait_id {sorted(missing)}")

        vectors = _split_by_vector_group(grades)
        profile = MajorProfile(
            major_id=major_id,
            label=LABELS[major_id],
            interest_vector=vectors["interest"],
            cognitive_vector=vectors["cognitive"],
            work_style_vector=vectors["work_style"],
            environment_vector=vectors["environment"],
            source_ids=[CAREER_NET_MAJOR_URL],
            extraction_method="manual",
            review_status="draft",
            profile_version=PROFILE_VERSION,
            updated_at=now,
        )
        profiles.append(profile)

        entry = DraftEntry(
            draft_id=f"major_trait_mapping_{major_id}_v0.1",
            draft_type="major_trait_mapping",
            author_id=AUTHOR_ID,
            review_stage=DraftReviewStage.DRAFT,
            source_url=CAREER_NET_MAJOR_URL,
            as_of_date=AS_OF,
            notes=SOURCE_NOTE,
        )
        payload = {
            "draft_entry": json.loads(entry.model_dump_json()),
            "major_id": major_id,
            "label": LABELS[major_id],
            "trait_grades": grades,
            "grade_scale": "0~3 (0=변별 축 아님, 3=전공 정체성 수준)",
            "rationale": RATIONALE[major_id],
            "derived_profile": json.loads(profile.model_dump_json()),
        }
        path = drafts_dir / f"{major_id}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        written.append(path)

    # 2026-08-22 12차(A): Vertical Slice 대표 전공 3개는 여기서 Evidence 기반으로 덧붙인다
    # — GRADES에는 이 3개가 없으므로 위 루프와 겹치지 않는다. 두 출처가 합쳐진 결과가
    # data/master/major_profiles.jsonl 하나의 정본이 된다(§16 "정본 하나" 요구사항).
    evidence_based = build_evidence_based_profiles()
    profiles.extend(evidence_based)
    for profile in evidence_based:
        entry = DraftEntry(
            draft_id=f"major_trait_mapping_{profile.major_id}_v1",
            draft_type="major_trait_mapping",
            author_id="worker_a",
            review_stage=DraftReviewStage.DRAFT,
            source_url=None,  # 근거가 여러 개(학과별 공식 페이지)라 단일 URL로 대표할 수 없다.
            as_of_date=date(2026, 8, 22),
            notes=(
                "실제 학과 공식 자료(교육목표·교과과정) 근거는 "
                "data/master/major_trait_mapping_evidence.jsonl 참고. "
                "EVIDENCED/NO_DIRECT_EVIDENCE Trait만 Vector에 반영했고, "
                "UNMAPPED/REVIEW_REQUIRED Trait는 Vector Key 자체에서 뺐다."
            ),
        )
        path = drafts_dir / f"{profile.major_id}.json"
        path.write_text(
            json.dumps(
                {
                    "draft_entry": json.loads(entry.model_dump_json()),
                    "major_id": profile.major_id,
                    "label": profile.label,
                    "source": "major_trait_mapping_evidence.jsonl (Evidence 기반, A 소유)",
                    "derived_profile": json.loads(profile.model_dump_json()),
                },
                ensure_ascii=False, indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        written.append(path)

    master = ROOT / "data" / "master" / "major_profiles.jsonl"
    master.parent.mkdir(parents=True, exist_ok=True)
    master.write_text(
        "".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8"
    )
    written.append(master)
    return profiles, written


if __name__ == "__main__":
    use_utf8_stdout()
    built, files = build()
    print(f"MajorProfile {len(built)}개 생성")
    for f in files:
        print(f"  {f.relative_to(ROOT)}")
