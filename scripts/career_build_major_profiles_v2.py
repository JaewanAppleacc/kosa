"""Service Canonical Major v2(39개) MajorProfile 정본 — 2026-08-25 지시서
(a/major-profiles-v2-38).

`data/master/major_profiles_v2.jsonl`은 두 가지 서로 다른 근거로 만들어진 39개
행을 담는다.

1. **Evidence 기반 3개**(media_communication/hci_ux/industrial_engineering) —
   `data/master/major_trait_mapping_evidence_v2.jsonl`(실제 대학 교육과정 URL을
   인용하는 EVIDENCED/NO_DIRECT_EVIDENCE 레코드)에서 그대로 만든다. 이 3개의
   구성 방식은 2026-08-23 2.6단계 이후 전혀 바뀌지 않았다(`build_from_evidence()`).
2. **공식 분류 근거 기반 36개**(39-3) — `data/canonical_major_groups.draft.jsonl`
   (42개 분류 Ontology Group, 공식 대학알리미 표준분류 소계열 근거)의 `description`·
   `classification_basis`를 사람이 직접 읽고 Trait Ontology v2 정의(`definition`·
   `positive_indicators`)와 대조해 만든다(`MANUAL_MAJOR_TRAIT_TABLE`,
   `build_from_manual_curation()`). 대학별 개별 교육과정 URL을 인용하는 1번 방식과
   근거 성격이 다르다는 것을 숨기지 않는다 — `extraction_method="manual"`로 명시
   구분하고, `source_ids`에는 그 Major가 유래한 Canonical Major Group의 공식
   출처(`official_source_urls`, 대학알리미/data.go.kr)를 그대로 쓴다.

**전공명 고정관념으로 배정하지 않는다** — 아래 표의 각 항목은 전공 "이름"이 아니라
그 Group의 실제 공식 `description`(예: "사람의 병을 진단하고 치료하는 분야")을 읽고
고른 것이다. 근거는 표 옆 주석에 그대로 남긴다(감사 가능하게).

**Weight는 0.33/0.67/1.00만 쓴다.** 1.00=핵심(core) Trait, 0.67/0.33=구분
(distinguishing) Trait라는 구분 규칙을 그대로 따른다(§1 "전공별 핵심 Trait와
구분 Trait 명시"). 모든 36개 Major가 최소 2개 Vector Group에 신호를 갖도록
설계했다 — `tests/test_major_profiles_v2_diversity.py`가 이를 실제 파일로
고정한다.

실행: PYTHONPATH=. ./.venv/bin/python scripts/career_build_major_profiles_v2.py
"""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.engines.trait_normalizer import normalize_grade  # noqa: E402
from src.schemas.major import MajorProfile  # noqa: E402
from src.services.canonical_major_group_draft_loader import load_canonical_major_groups_draft  # noqa: E402
from src.services.major_trait_mapping_evidence import (  # noqa: E402
    MajorTraitMappingRecord,
    load_major_trait_mapping_evidence,
)
from src.services.service_canonical_major_v2_loader import load_service_canonical_majors_v2  # noqa: E402
from src.services.trait_ontology_v2 import load_trait_ontology_v2  # noqa: E402

V2_EVIDENCE_PATH = ROOT / "data" / "master" / "major_trait_mapping_evidence_v2.jsonl"
OUTPUT_PATH = ROOT / "data" / "master" / "major_profiles_v2.jsonl"
PROFILE_VERSION = "major_profile_v2.0"

# Evidence(대학 교육과정 URL) 기반 3개 — 이 목록·구성 방식은 2.6단계 이후 바뀌지 않았다.
EVIDENCE_BASED_MAJOR_IDS: tuple[str, ...] = ("media_communication", "hci_ux", "industrial_engineering")

# MAJOR_LABELS는 더 이상 3개를 손으로 적지 않는다 — 39개 Service Catalog에서
# 그대로 가져온다(§2 "Catalog와 Profile ID 집합 정확히 일치"). 기존
# tests/test_trait_v2_major_subject_data.py가 이 심볼을 그대로 계속 쓴다.
MAJOR_LABELS: dict[str, str] = {m.major_id: m.label for m in load_service_canonical_majors_v2()}

# ============================================================================
# 36개 공식 분류 근거 기반 Major — Canonical Major Group Draft의 실제 description·
# classification_basis를 근거로 사람이 직접 골랐다(전공명 고정관념 아님). 값은
# (trait_id, weight, "핵심"|"구분", 근거 한 줄) 튜플이다. weight는 0.33/0.67/1.00만
# 쓴다. 근거 문구는 반드시 그 Group의 실제 description을 인용하거나 요약한다.
# ============================================================================
MANUAL_MAJOR_TRAIT_TABLE: dict[str, list[tuple[str, float, str, str]]] = {
    # ---- 의료·보건 계열 ----
    "medicine": [
        ("causal_analysis", 1.00, "핵심", "'병을 진단하고 치료' — 병의 원인을 분석해야 진단이 가능하다"),
        ("systems_thinking", 0.67, "핵심", "신체를 연결된 체계로 이해해야 여러 증상을 종합할 수 있다"),
        ("independent_judgment", 0.67, "구분", "최종 진단·치료 결정의 책임을 진다"),
    ],
    "dentistry": [
        ("causal_analysis", 1.00, "핵심", "'치아와 구강을 치료' — 질환 원인 진단이 선행된다"),
        ("detail_orientation", 1.00, "핵심", "구강 내 정밀 시술은 세부에 대한 주의가 핵심이다"),
        ("tool_utilization", 0.67, "구분", "치과 기구를 직접 다루는 실습 비중이 크다"),
    ],
    "korean_medicine": [
        ("pattern_finding", 1.00, "핵심", "'한의학 이론으로 진단' — 증상 패턴을 체계적으로 읽어 진단한다"),
        ("causal_analysis", 0.67, "핵심", "치료를 위해 증상의 원인을 분석한다"),
        ("independent_judgment", 0.33, "구분", "진단·처방의 최종 판단 책임"),
    ],
    "pharmacy": [
        ("causal_analysis", 1.00, "핵심", "'약을 개발하고 다루는' — 약물 작용 원리를 이해해야 한다"),
        ("detail_orientation", 1.00, "핵심", "정확한 조제·품질관리가 요구된다"),
        ("persistence_completion", 0.67, "구분", "품질관리·검증 과정을 꾸준히 지속한다"),
    ],
    "nursing": [
        ("collaboration_preference", 1.00, "핵심", "'환자를 돌보고' — 의료진·환자와의 협업이 중심이다"),
        ("emotional_interpretation", 1.00, "핵심", "환자의 상태·감정을 파악해 돌봄을 제공한다"),
        ("immediate_execution", 0.67, "구분", "돌봄 현장에서 즉각적인 처치·대응이 필요하다"),
    ],
    "veterinary": [
        ("causal_analysis", 1.00, "핵심", "'동물의 병을 진단하고 치료' — 원인 분석이 진단의 기반이다"),
        ("emotional_interpretation", 0.67, "구분", "말로 표현하지 못하는 동물의 상태를 관찰해 해석한다"),
        ("detail_orientation", 0.67, "구분", "정밀한 진료·처치가 요구된다"),
    ],
    "health_science": [
        ("collaboration_preference", 1.00, "핵심", "'건강을 지키고 회복을 돕는' — 환자·의료진과 협업하는 재활 지원"),
        ("persistence_completion", 1.00, "핵심", "장기간 이어지는 재활 과정을 끝까지 지원한다"),
        ("emotional_interpretation", 0.67, "구분", "회복 과정에서 대상자의 상태를 세심히 살핀다"),
    ],
    # ---- 공학 계열 ----
    "computer_science": [
        ("systems_thinking", 1.00, "핵심", "'컴퓨터 원리를 배우는' — 시스템 구조를 이해하는 것이 핵심이다"),
        ("causal_analysis", 1.00, "핵심", "프로그램 오류의 원인을 분석하는 디버깅이 핵심 활동이다"),
        ("tool_utilization", 0.67, "구분", "프로그래밍 도구·개발 환경을 직접 다룬다"),
    ],
    "electrical_electronic": [
        ("systems_thinking", 1.00, "핵심", "'전기 신호와 회로, 통신을 다루는' — 회로·통신을 하나의 체계로 이해한다"),
        ("tool_utilization", 1.00, "핵심", "전자 장비·계측기를 직접 다뤄 회로를 구성·검증한다"),
        ("causal_analysis", 0.67, "구분", "신호·회로 이상의 원인을 분석한다"),
    ],
    "mechanical_engineering": [
        ("systems_thinking", 1.00, "핵심", "'움직이는 것을 설계하고 만드는' — 기계를 하나의 체계로 설계한다"),
        ("tool_utilization", 1.00, "핵심", "공구·장비를 다뤄 직접 설계·제작한다"),
        ("persistence_completion", 0.67, "구분", "설계-제작-검증을 반복하며 끝까지 완성한다"),
    ],
    "civil_architecture": [
        ("systems_thinking", 1.00, "핵심", "'건물과 도시 기반시설을 설계' — 구조 전체를 체계적으로 설계한다"),
        ("planning", 1.00, "핵심", "시공 순서·자원을 계획하는 활동이 핵심이다"),
        ("tool_utilization", 0.67, "구분", "설계·시공 도구를 활용한다"),
    ],
    "chemical_energy": [
        ("causal_analysis", 1.00, "핵심", "'물질을 대량으로 만들고 에너지를 다루는' — 반응 원리 이해가 기반이다"),
        ("systems_thinking", 0.67, "핵심", "대규모 생산 공정을 하나의 체계로 설계한다"),
        ("detail_orientation", 0.67, "구분", "안전·정밀한 공정 관리가 요구된다"),
    ],
    "semiconductor_materials": [
        ("causal_analysis", 1.00, "핵심", "'반도체와 새로운 재료를 만드는' — 소재의 반응·물성 원리를 이해한다"),
        ("tool_utilization", 1.00, "핵심", "정밀 공정 장비를 직접 다룬다"),
        ("persistence_completion", 0.33, "구분", "미세 공정 검증을 반복해 완성도를 높인다"),
    ],
    "bio_medical_engineering": [
        ("systems_thinking", 1.00, "핵심", "'생명 기술과 의료 기기를 만드는' — 생체·기기를 하나의 시스템으로 이해한다"),
        ("causal_analysis", 1.00, "핵심", "생명현상·기기 작동의 원리를 분석한다"),
        ("detail_orientation", 0.67, "구분", "의료기기 개발은 정밀함이 특히 중요하다"),
    ],
    # ---- 자연과학 계열 ----
    "chemistry": [
        ("causal_analysis", 1.00, "핵심", "'물질의 성질과 변화를 연구' — 변화의 원인을 규명한다"),
        ("pattern_finding", 0.67, "핵심", "반응·물성의 패턴을 탐색한다"),
        ("detail_orientation", 0.67, "구분", "정밀한 실험 절차가 요구된다"),
    ],
    "physics_astronomy": [
        ("causal_analysis", 1.00, "핵심", "'자연의 기본 법칙을 연구' — 자연현상의 원인·원리를 규명한다"),
        ("systems_thinking", 1.00, "핵심", "우주·물리계를 구조적으로 이해한다"),
        ("uncertainty_tolerance", 0.67, "구분", "아직 밝혀지지 않은 현상을 다루는 연구가 많다"),
    ],
    "life_science": [
        ("causal_analysis", 1.00, "핵심", "'생명현상을 연구' — 생명현상의 원인을 규명한다"),
        ("pattern_finding", 1.00, "핵심", "생물학적 구조·현상의 패턴을 탐색한다"),
        ("persistence_completion", 0.67, "구분", "장기간의 관찰·실험을 지속한다"),
    ],
    "earth_environment": [
        ("pattern_finding", 1.00, "핵심", "'지구와 바다, 환경 변화를 연구' — 변화의 패턴을 탐색한다"),
        ("systems_thinking", 0.67, "핵심", "지구를 하나의 연결된 시스템으로 이해한다"),
        ("information_comparison", 0.67, "구분", "지역·시기별 관측 자료를 비교한다"),
        ("change_adaptation", 0.33, "구분", "계속 변화하는 환경 현상을 다루는 연구다"),
    ],
    "mathematics_statistics": [
        ("pattern_finding", 1.00, "핵심", "'수와 데이터의 구조를 다루는' — 구조적 패턴을 탐색한다"),
        ("systems_thinking", 0.67, "핵심", "논리 체계를 구축해 문제를 푼다"),
        ("independent_judgment", 0.33, "구분", "독자적인 증명·풀이 과정이 요구된다"),
    ],
    # ---- 경상·사회 계열 ----
    "business_administration": [
        ("planning", 1.00, "핵심", "'조직을 운영하고 사업을 만드는' — 사업 계획 수립이 핵심이다"),
        ("information_comparison", 0.67, "핵심", "시장·재무 자료를 비교·분석한다"),
        ("opinion_expression", 0.67, "구분", "의사결정을 제안·설득하는 활동이 있다"),
    ],
    "economics": [
        ("causal_analysis", 1.00, "핵심", "'돈과 자원이 어떻게 움직이는지 분석' — 경제 현상의 원인을 분석한다"),
        ("pattern_finding", 0.67, "핵심", "경제 데이터의 패턴을 탐색한다"),
        ("information_comparison", 0.67, "구분", "통계 자료를 비교한다"),
        ("independent_judgment", 0.33, "구분", "이론적 해석에서 독자적 판단이 필요하다"),
    ],
    "public_administration": [
        ("planning", 1.00, "핵심", "'정책을 다루는' — 정책 기획이 핵심 활동이다"),
        ("opinion_mediation", 0.67, "핵심", "공공정책은 서로 다른 이해관계를 조정해야 한다"),
        ("information_comparison", 0.67, "구분", "정책 사례를 비교·검토한다"),
    ],
    "trade_logistics": [
        ("planning", 1.00, "핵심", "'상품과 자산이 오가는 일을 다루는' — 물류·거래 계획이 핵심이다"),
        ("information_comparison", 0.67, "핵심", "시장·물류 정보를 비교한다"),
        ("detail_orientation", 0.33, "구분", "거래·통관 절차의 세부 관리가 필요하다"),
    ],
    "tourism": [
        ("planning", 1.00, "핵심", "'여행·호텔·행사를 기획하고 운영' — 기획이 핵심 활동이다"),
        ("collaboration_preference", 0.67, "핵심", "고객·협력업체와의 협업이 많다"),
        ("audience_response_prediction", 0.33, "구분", "고객 반응을 고려해 상품·행사를 기획한다"),
    ],
    "social_welfare": [
        ("emotional_interpretation", 1.00, "핵심", "'도움이 필요한 사람을 지원' — 대상자의 어려움·감정을 이해한다"),
        ("collaboration_preference", 1.00, "핵심", "지원 기관·대상자와 협업한다"),
        ("opinion_mediation", 0.67, "구분", "지원 과정에서 이해관계를 조정한다"),
    ],
    "sociology": [
        ("systems_thinking", 1.00, "핵심", "'사회 구조가 어떻게 만들어지는지 연구' — 사회를 구조적으로 이해한다"),
        ("pattern_finding", 0.67, "핵심", "사회 현상의 패턴을 탐색한다"),
        ("information_comparison", 0.67, "구분", "자료·정보를 비교·조직화한다"),
        ("independent_judgment", 0.33, "구분", "사회 현상의 해석에 독자적 판단이 필요하다"),
    ],
    "political_science": [
        ("opinion_expression", 1.00, "핵심", "'권력과 국가 간 관계를 연구' — 논쟁적 주제에 대한 의견 표명이 핵심이다"),
        ("information_comparison", 0.67, "핵심", "국가·정책 사례를 비교한다"),
        ("opinion_mediation", 0.33, "구분", "이해관계를 조정하는 논의가 있다"),
    ],
    "psychology": [
        ("emotional_interpretation", 1.00, "핵심", "'사람의 마음과 행동을 연구' — 마음·감정을 해석하는 것이 핵심이다"),
        ("causal_analysis", 0.67, "핵심", "행동의 원인을 분석한다"),
        ("pattern_finding", 0.67, "구분", "행동·반응의 패턴을 탐색한다"),
        ("uncertainty_tolerance", 0.33, "구분", "명확히 규정되지 않는 인간 행동을 다룬다"),
    ],
    "education": [
        ("collaboration_preference", 1.00, "핵심", "'가르치고 배우는 일을 연구' — 학습자와의 상호작용이 중심이다"),
        ("opinion_expression", 0.67, "핵심", "내용을 설명·전달하는 활동이 핵심이다"),
        ("planning", 0.67, "구분", "수업·교육과정을 설계한다"),
        ("emotional_interpretation", 0.33, "구분", "학습자의 상태를 파악해야 한다"),
    ],
    # ---- 어문·인문 계열 ----
    "korean_literature": [
        ("verbal_expression", 1.00, "핵심", "'우리말과 한국문학을 읽고 쓰는' — 언어로 표현하는 활동이 핵심이다"),
        ("creative_ideation", 0.67, "핵심", "문학 창작에는 새로운 발상이 필요하다"),
        ("emotional_interpretation", 0.33, "구분", "작품 속 감정을 해석한다"),
    ],
    "foreign_language": [
        ("verbal_expression", 1.00, "핵심", "'외국어와 언어 자체를 연구' — 언어를 구사·표현하는 활동이 핵심이다"),
        ("information_comparison", 0.67, "핵심", "언어·문화 간 차이를 비교한다"),
        ("pattern_finding", 0.33, "구분", "언어 구조의 패턴을 탐색한다"),
    ],
    "humanities": [
        ("causal_analysis", 1.00, "핵심", "'사람이 어떻게 살아왔는지 다루는' — 역사·사상의 인과관계를 분석한다"),
        ("independent_judgment", 0.67, "핵심", "사료·문헌에 대한 독자적 해석이 요구된다"),
        ("information_comparison", 0.67, "구분", "여러 사료·문헌을 비교한다"),
    ],
    "law": [
        ("causal_analysis", 1.00, "핵심", "'법을 해석하고 적용하는' — 법리적 인과관계를 분석한다"),
        ("independent_judgment", 1.00, "핵심", "법적 판단에는 책임 있는 결론이 요구된다"),
        ("opinion_expression", 0.67, "구분", "논리적 주장을 전개·변론한다"),
    ],
    # ---- 생활·응용 계열 ----
    "food_nutrition": [
        ("detail_orientation", 1.00, "핵심", "'성분·안전·조리를 다루는' — 성분·안전 관리는 정밀함이 핵심이다"),
        ("tool_utilization", 0.67, "핵심", "조리·실험 도구를 직접 다룬다"),
        ("causal_analysis", 0.33, "구분", "영양·안전 문제의 원인을 분석한다"),
    ],
    "clothing_housing": [
        ("aesthetic_sensitivity", 1.00, "핵심", "'의류·주거·소비 생활을 연구' — 의류·공간의 미적 요소를 감식한다"),
        ("detail_orientation", 0.67, "핵심", "소재·구조를 세심히 관찰한다"),
        ("information_comparison", 0.33, "구분", "소비 트렌드·자료를 비교한다"),
    ],
    "agriculture_fisheries": [
        ("tool_utilization", 1.00, "핵심", "'작물·산림·수산 자원을 기르고 관리' — 현장 장비·도구를 활용한다"),
        ("persistence_completion", 1.00, "핵심", "장기간의 재배·양식 관리를 지속한다"),
        ("detail_orientation", 0.33, "구분", "자원 상태를 세심히 관찰한다"),
    ],
}


def _vector_group_by_trait(trait_definitions: dict[str, str] | None = None) -> dict[str, str]:
    return trait_definitions if trait_definitions is not None else {
        t.trait_id: t.primary_vector_group for t in load_trait_ontology_v2()
    }


def build_from_evidence(
    evidence_records: list[MajorTraitMappingRecord] | None = None,
    trait_definitions: dict[str, str] | None = None,
    updated_at: datetime | None = None,
) -> list[MajorProfile]:
    """Evidence 기반 3개(2.6단계 이후 로직 그대로 — §5 "Matching 최소 Evidence 기준
    완화 금지"와 무관하게 이 함수 자체를 조금도 바꾸지 않았다)."""

    records = (
        evidence_records if evidence_records is not None
        else load_major_trait_mapping_evidence(V2_EVIDENCE_PATH)
    )
    vector_group_by_trait = _vector_group_by_trait(trait_definitions)
    now = updated_at or datetime(2026, 8, 23, tzinfo=timezone.utc)

    by_major: dict[str, list[MajorTraitMappingRecord]] = defaultdict(list)
    for record in records:
        if record.major_id not in EVIDENCE_BASED_MAJOR_IDS:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.major_id!r}는 Evidence 기반 3개 Major"
                f"({sorted(EVIDENCE_BASED_MAJOR_IDS)})에 없다"
            )
        if record.trait_id not in vector_group_by_trait:
            raise SystemExit(
                f"{V2_EVIDENCE_PATH.name}: {record.major_id}/{record.trait_id} — 현재 v2 Trait "
                "Ontology(24개)에 없는 trait_id다"
            )
        by_major[record.major_id].append(record)

    profiles: list[MajorProfile] = []
    for major_id in sorted(EVIDENCE_BASED_MAJOR_IDS):
        major_records = by_major.get(major_id, [])
        duplicated = {
            t for t in {r.trait_id for r in major_records}
            if sum(1 for r in major_records if r.trait_id == t) > 1
        }
        if duplicated:
            raise SystemExit(f"{major_id}: trait_id 중복 Mapping 레코드 {sorted(duplicated)}")

        vectors: dict[str, dict[str, float]] = {
            "interest": {}, "cognitive": {}, "work_style": {}, "environment": {},
        }
        source_urls: set[str] = set()
        for record in major_records:
            if record.mapping_status not in ("EVIDENCED", "NO_DIRECT_EVIDENCE"):
                continue
            group = vector_group_by_trait[record.trait_id]
            vectors[group][record.trait_id] = normalize_grade(record.grade)  # type: ignore[arg-type]
            for evidence in record.evidence:
                source_urls.add(evidence.source_url)

        profiles.append(
            MajorProfile(
                major_id=major_id, label=MAJOR_LABELS[major_id],
                interest_vector=vectors["interest"], cognitive_vector=vectors["cognitive"],
                work_style_vector=vectors["work_style"], environment_vector=vectors["environment"],
                source_ids=sorted(source_urls), extraction_method="rule",
                review_status="draft", profile_version=PROFILE_VERSION, updated_at=now,
            )
        )
    return profiles


def build_from_manual_curation(
    table: dict[str, list[tuple[str, float, str, str]]] | None = None,
    trait_definitions: dict[str, str] | None = None,
    group_official_source_urls: dict[str, list[str]] | None = None,
    updated_at: datetime | None = None,
) -> list[MajorProfile]:
    """공식 분류 근거 기반 36개. `MANUAL_MAJOR_TRAIT_TABLE`의 major_id는 반드시
    39개 Service Catalog 중 Evidence 기반 3개를 제외한 나머지와 정확히 일치해야
    한다(Fail-Fast) — §2 "Catalog와 Profile ID 집합 정확히 일치"."""

    table = table if table is not None else MANUAL_MAJOR_TRAIT_TABLE
    vector_group_by_trait = _vector_group_by_trait(trait_definitions)
    now = updated_at or datetime(2026, 8, 25, tzinfo=timezone.utc)

    catalog = load_service_canonical_majors_v2()
    catalog_by_id = {m.major_id: m for m in catalog}
    manual_expected_ids = {m.major_id for m in catalog} - set(EVIDENCE_BASED_MAJOR_IDS)

    missing = manual_expected_ids - set(table)
    if missing:
        raise SystemExit(f"MANUAL_MAJOR_TRAIT_TABLE에 없는 Major: {sorted(missing)}")
    unexpected = set(table) - manual_expected_ids
    if unexpected:
        raise SystemExit(
            f"MANUAL_MAJOR_TRAIT_TABLE에 39개 Catalog(Evidence 기반 3개 제외)에 없는 Major: {sorted(unexpected)}"
        )

    if group_official_source_urls is None:
        groups_by_id = {g.canonical_major_id: g for g in load_canonical_major_groups_draft()}
        group_official_source_urls = {gid: g.official_source_urls for gid, g in groups_by_id.items()}

    profiles: list[MajorProfile] = []
    for major_id in sorted(manual_expected_ids):
        entries = table[major_id]
        trait_ids = [t for t, *_ in entries]
        if len(trait_ids) != len(set(trait_ids)):
            raise SystemExit(f"{major_id}: MANUAL_MAJOR_TRAIT_TABLE에 trait_id 중복이 있다 — {trait_ids}")

        vectors: dict[str, dict[str, float]] = {
            "interest": {}, "cognitive": {}, "work_style": {}, "environment": {},
        }
        for trait_id, weight, _tier, _rationale in entries:
            if trait_id not in vector_group_by_trait:
                raise SystemExit(f"{major_id}/{trait_id} — 현재 v2 Trait Ontology(24개)에 없는 trait_id다")
            if weight not in (0.33, 0.67, 1.00):
                raise SystemExit(f"{major_id}/{trait_id}: weight는 0.33/0.67/1.00만 허용한다 — got {weight!r}")
            group = vector_group_by_trait[trait_id]
            vectors[group][trait_id] = weight

        used_groups = {g for g, v in vectors.items() if v}
        if len(used_groups) < 2:
            raise SystemExit(f"{major_id}: 최소 2개 Vector Group에 신호가 있어야 한다 — 실제 {sorted(used_groups)}")

        catalog_entry = catalog_by_id[major_id]
        # DEPARTMENT_LEVEL_ONLY(hci_ux)는 애초에 이 표(manual_expected_ids)에 없다 —
        # canonical_major_group_id가 FULL_GROUP Major에만 있다는 사실 자체로 이 조회가
        # 항상 성공함을 구조적으로 보장한다.
        source_urls = group_official_source_urls.get(catalog_entry.canonical_major_group_id, [])

        profiles.append(
            MajorProfile(
                major_id=major_id, label=MAJOR_LABELS[major_id],
                interest_vector=vectors["interest"], cognitive_vector=vectors["cognitive"],
                work_style_vector=vectors["work_style"], environment_vector=vectors["environment"],
                source_ids=sorted(source_urls), extraction_method="manual",
                review_status="draft", profile_version=PROFILE_VERSION, updated_at=now,
            )
        )
    return profiles


def build(
    evidence_records: list[MajorTraitMappingRecord] | None = None,
    manual_table: dict[str, list[tuple[str, float, str, str]]] | None = None,
    trait_definitions: dict[str, str] | None = None,
    updated_at: datetime | None = None,
) -> list[MajorProfile]:
    from_evidence = build_from_evidence(evidence_records, trait_definitions, updated_at)
    from_manual = build_from_manual_curation(manual_table, trait_definitions, updated_at=updated_at)

    all_profiles = from_evidence + from_manual
    ids = [p.major_id for p in all_profiles]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"major_id 중복 — Evidence 기반과 수동 큐레이션이 겹쳤다: {sorted(ids)}")

    catalog_ids = {m.major_id for m in load_service_canonical_majors_v2()}
    built_ids = set(ids)
    if built_ids != catalog_ids:
        raise SystemExit(
            f"39개 Service Catalog와 빌드 결과 ID 집합이 다르다 — "
            f"Catalog에만: {sorted(catalog_ids - built_ids)}, 빌드에만: {sorted(built_ids - catalog_ids)}"
        )

    return sorted(all_profiles, key=lambda p: p.major_id)


def main() -> None:
    profiles = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("".join(p.model_dump_json() + "\n" for p in profiles), encoding="utf-8")
    print(f"{OUTPUT_PATH.relative_to(ROOT)}: MajorProfile {len(profiles)}개 생성")
    for p in profiles:
        total_traits = len(p.interest_vector) + len(p.cognitive_vector) + len(p.work_style_vector) + len(p.environment_vector)
        print(f"  {p.major_id}({p.extraction_method}): Vector에 담긴 Trait {total_traits}개(24개 중)")


if __name__ == "__main__":
    use_utf8_stdout()
    main()
