"""39개 Service Major v2 Catalog을 위한 Subject-Major Link Evidence —
a/subject-mapping-38-majors 지시서.

기존 v2 파이프라인(`career_build_subject_profiles_v2.py`)은 Vertical Slice 대표
전공 3개(media_communication/hci_ux/industrial_engineering)에 연결된 과목 6개만
다뤘다 — 나머지 대부분의 서비스 Major는 v2 희망과목 화면이 완전히 비어 있었다
(candidate subjects 0건).

이 스크립트는 그 빈틈을 근거 기반으로 채운다. 결정론적으로 정본 하나를 만든다.

    data/master/subject_major_link_evidence_v2.jsonl (신규)
        기존 `subject_major_link_evidence.jsonl`(Vertical Slice 3개 전공 전용, Legacy
        Builder가 Fail-Fast로 그 3개만 허용)과 별개다 — v2의 39개 서비스 Major
        (`data/master/service_canonical_majors_v2.jsonl`) 전부를 대상으로 한다.

과목의 Trait Evidence(24-Trait v2)는 이 스크립트가 아니라
`career_build_subject_trait_mapping_evidence_v2.py`가 소유한다(그 파일의
`NEW_SUBJECT_TRAIT_EVIDENCE`/`EXPANDED_LEGACY_SUBJECT_LABELS`) — "v2 신규 12개
Trait는 REVIEW_REQUIRED만 허용" 규칙이 그 파일에 이미 있고, 두 곳에서 같은 규칙을
따로 관리하면 어긋나기 쉽다(단일 정본 원칙).

**hci_ux 특수 규칙(지시서 필수 준수)**: hci_ux는 `mapping_scope=DEPARTMENT_LEVEL_ONLY`
다 — `computer_science`/`fine_arts_design` Group 소속이라는 이유만으로 그 Group의
과목을 hci_ux에 자동 연결하지 않는다. 이 파일은 hci_ux를 대상으로 하는 어떤 행도
만들지 않는다(`main()`이 Fail-Fast로 확인한다) — Legacy `subjects.jsonl`에 이미
있던 2개 연결(정보·소프트웨어와 생활, 2026-08-24 14차 리뷰가 개별 검토해 확정)만
`career_build_subject_profiles_v2.py`가 그대로 보존한다.

fine_arts_design은 추천 제외 Group이라 여기서 만드는 어떤 신규 Major 연결도 그
Group을 대상으로 하지 않는다(애초에 서비스 Major 목록에 없다).

이 파일 자체는 "정본"이 아니라 "정본을 채우는 저작 스크립트"다 — 실행 결과인 JSONL
파일이 정본이고(다른 검토된 Evidence 파일과 같은 관례), 사람 검토는 여전히
`review_status="draft"`로 남는다(자동 승인 없음).

실행:
    PYTHONPATH=. ./.venv/bin/python scripts/career_build_subject_major_mapping_v2_expansion.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.career_console import use_utf8_stdout  # noqa: E402

from src.ids import generate_subject_id  # noqa: E402
from src.services.subject_major_link_evidence import (  # noqa: E402
    SubjectMajorLinkCurriculumEvidence,
    SubjectMajorLinkRecord,
)

CURRICULUM_CODE = "2022-33"  # 교육부 고시 제2022-33호 (2022 개정 교육과정)
MOE_URL = "https://www.moe.go.kr/boardCnts/viewRenew.do?boardID=141&lev=0&statusYN=W&s=moe&m=0404&opType=N&boardSeq=93458"
LINK_MAPPING_VERSION = "subject_major_link_v2_39majors"
AUTHOR_ID = "worker_a"

MAJOR_LINK_EVIDENCE_V2_PATH = ROOT / "data" / "master" / "subject_major_link_evidence_v2.jsonl"

FORBIDDEN_MAJOR_IDS = frozenset({"hci_ux", "fine_arts_design", "music", "performing_media_arts", "sports_dance"})

# {label: [(major_id, reason), ...]} — RELATED만 담는다.
MAJOR_LINKS: dict[str, list[tuple[str, str]]] = {
    # --- 신규 24개 과목 ---
    "화학": [
        ("chemistry", "화학 반응·물질 구조를 다루는 과목 성취기준이 화학 전공 교육과정과 직접 대응"),
        ("chemical_energy", "화학 반응 원리가 화학공학·에너지 전공의 기초 교육과정과 대응"),
        ("pharmacy", "물질의 화학적 성질 이해가 약학 전공 기초 교육과정과 대응"),
        ("semiconductor_materials", "물질의 성질·반응 원리가 반도체·신소재 전공 기초와 대응"),
    ],
    "지구과학": [
        ("earth_environment", "지구 시스템 탐구가 지구·지리·환경 전공 교육과정과 직접 대응"),
        ("civil_architecture", "지반·지질 이해가 건축·토목 전공의 기초 교육과정과 대응"),
    ],
    "행성우주과학": [("physics_astronomy", "천체·우주 현상 탐구가 물리·천문 전공 교육과정과 직접 대응")],
    "기후변화와 지속가능한 세계": [
        ("earth_environment", "기후·환경 시스템 분석이 지구·지리·환경 전공 교육과정과 직접 대응"),
        ("agriculture_fisheries", "지속가능성·자원 관리 논의가 농림·수산 전공의 환경 기초와 대응"),
    ],
    "융합과학 탐구": [
        ("life_science", "생명 현상을 포함한 융합 탐구가 생명과학 전공 교육과정과 대응"),
        ("bio_medical_engineering", "여러 과학 분야를 통합하는 탐구가 생명공학·의공학 전공 기초와 대응"),
    ],
    "대수": [("mathematics_statistics", "수·식의 구조를 다루는 과목이 수학·통계 전공 기초 교육과정과 직접 대응")],
    "기하": [
        ("civil_architecture", "도형·공간 이해가 건축·토목 전공의 설계 기초와 대응"),
        ("mechanical_engineering", "공간 도형 계산이 기계공학 설계 기초와 대응"),
    ],
    "인공지능 수학": [
        ("mathematics_statistics", "수학적 모델링이 수학·통계 전공 교육과정과 직접 대응"),
        ("computer_science", "인공지능 알고리즘의 수학적 기초가 컴퓨터·소프트웨어 전공과 대응"),
    ],
    "경제 수학": [
        ("economics", "경제 현상의 수리적 분석이 경제학 전공 기초 교육과정과 직접 대응"),
        ("trade_logistics", "수리적 의사결정이 무역·유통 전공의 분석 기초와 대응"),
    ],
    "정치": [
        ("political_science", "정치 제도·과정 탐구가 정치외교·국제학 전공 교육과정과 직접 대응"),
        ("public_administration", "정치·행정 제도 이해가 행정·정책 전공 기초와 대응"),
        ("law", "정치와 법 제도의 관계 이해가 법학 전공 기초와 대응"),
    ],
    "법과 사회": [("law", "법 조항·판례 해석이 법학 전공 교육과정과 직접 대응")],
    "경제": [
        ("economics", "경제 현상의 원인·결과 분석이 경제학 전공 교육과정과 직접 대응"),
        ("business_administration", "시장·기업 활동 이해가 경영학 전공 기초와 대응"),
        ("trade_logistics", "국제 거래·유통 이해가 무역·유통 전공 기초와 대응"),
    ],
    "국제 관계의 이해": [
        ("political_science", "국제 관계·외교 탐구가 정치외교·국제학 전공 교육과정과 직접 대응"),
        ("foreign_language", "국제 사회 이해가 외국어·언어학 전공의 지역 연구 기초와 대응"),
    ],
    "여행지리": [("tourism", "지역별 여행 자원 탐구가 관광 전공 교육과정과 직접 대응")],
    "인문학과 윤리": [("humanities", "여러 사상·철학 비교가 철학·역사·종교 전공 교육과정과 직접 대응")],
    "사회와 문화": [
        ("sociology", "사회·문화 현상 분석이 사회학·문헌정보 전공 교육과정과 직접 대응"),
        ("social_welfare", "사회 구조 이해가 사회복지·아동가족 전공 기초와 대응"),
        ("public_administration", "사회 제도 이해가 행정·정책 전공 기초와 대응"),
    ],
    "한국지리 탐구": [
        ("earth_environment", "지역 지리 자료 탐구가 지구·지리·환경 전공 교육과정과 직접 대응"),
        ("tourism", "지역별 특성 이해가 관광 전공의 지역 자원 기초와 대응"),
    ],
    "로봇과 공학세계": [
        ("mechanical_engineering", "로봇 설계·제작이 기계공학 전공 교육과정과 직접 대응"),
        ("electrical_electronic", "센서·구동 제어가 전기·전자·정보통신 전공 기초와 대응"),
        ("semiconductor_materials", "로봇 부품·소재 활용이 반도체·신소재 전공 응용 기초와 대응"),
    ],
    "생활과학 탐구": [
        ("food_nutrition", "식생활 관련 과학 탐구가 식품·영양·조리 전공 교육과정과 직접 대응"),
        ("clothing_housing", "의생활·주생활 탐구가 의류·주거·소비자 전공 교육과정과 직접 대응"),
        ("health_science", "생활 속 건강 관련 탐구가 보건·재활 전공 기초와 대응"),
    ],
    "문학": [
        ("korean_literature", "작품 감상·해석이 국어국문·문예창작 전공 교육과정과 직접 대응"),
        ("humanities", "인간과 삶에 대한 문학적 탐구가 철학·역사·종교 전공 기초와 대응"),
    ],
    "문학과 영상": [
        ("korean_literature", "문학의 서사 구조 이해가 국어국문·문예창작 전공 교육과정과 대응"),
        ("media_communication", "문학의 영상적 재구성이 미디어·커뮤니케이션 전공 기초와 대응"),
    ],
    "영어 발표와 토론": [
        ("foreign_language", "영어 의사소통·발표가 외국어·언어학 전공 교육과정과 직접 대응"),
        ("political_science", "국제 이슈 토론이 정치외교·국제학 전공의 소통 기초와 대응"),
    ],
    "중국어": [("foreign_language", "제2외국어 의사소통 학습이 외국어·언어학 전공 교육과정과 직접 대응")],
    "보건": [
        ("health_science", "건강관리·응급처치 절차가 보건·재활 전공 교육과정과 직접 대응"),
        ("nursing", "건강 문제 이해와 관리가 간호학 전공 기초와 대응"),
    ],
    # --- 기존 11개 과목: 신규 39개 체계로 확장 연결 ---
    "통합과학1": [("life_science", "통합 자연 현상 탐구가 생명과학 전공 기초와 대응")],
    "물리학": [
        ("mechanical_engineering", "실험 기반 원인-결과 규명이 기계공학 전공 교육과정과 직접 대응"),
        ("electrical_electronic", "물리 법칙 이해가 전기·전자·정보통신 전공 기초와 대응"),
        ("physics_astronomy", "물리 현상 탐구가 물리·천문 전공 교육과정과 직접 대응"),
        ("semiconductor_materials", "물질의 물리적 성질 이해가 반도체·신소재 전공 기초와 대응"),
    ],
    "생명과학": [
        ("life_science", "생명 현상 원인 설명이 생명과학 전공 교육과정과 직접 대응"),
        ("medicine", "생명 현상 이해가 의학 전공 기초 교육과정과 대응"),
        ("dentistry", "생명과학 기초가 치의학 전공 기초 교육과정과 대응"),
        ("pharmacy", "생명·물질 상호작용 이해가 약학 전공 기초와 대응"),
        ("nursing", "인체·생명현상 이해가 간호학 전공 기초와 대응"),
        ("veterinary", "생명 현상 이해가 수의학 전공 기초 교육과정과 대응"),
        ("korean_medicine", "생명 현상 이해가 한의학 전공 기초 교육과정과 대응"),
        ("bio_medical_engineering", "생명 현상 원리가 생명공학·의공학 전공 기초와 대응"),
        ("agriculture_fisheries", "생명체의 생장 원리 이해가 농림·수산 전공 기초와 대응"),
    ],
    "사회문제 탐구": [("sociology", "사회 현상 탐구가 사회학·문헌정보 전공 교육과정과 직접 대응")],
    "인간과 심리": [("social_welfare", "인간 행동·정서 이해가 사회복지·아동가족 전공 기초와 대응")],
    "미술 창작": [("clothing_housing", "시각·조형 표현 활동이 의류·주거·소비자 전공의 디자인 기초와 대응")],
    "공통수학1": [
        ("mathematics_statistics", "수·식 규칙 탐구가 수학·통계 전공 교육과정과 직접 대응"),
        ("civil_architecture", "수리적 계산이 건축·토목 전공 설계 기초와 대응"),
    ],
    "미적분Ⅱ": [("mathematics_statistics", "함수 변화 분석이 수학·통계 전공 교육과정과 직접 대응")],
    "창의 공학 설계": [
        ("mechanical_engineering", "공학 도구를 활용한 설계·제작이 기계공학 전공 교육과정과 직접 대응"),
        ("civil_architecture", "설계 도구 활용이 건축·토목 전공 기초와 대응"),
    ],
}


def _generate_link_records() -> list[SubjectMajorLinkRecord]:
    records: list[SubjectMajorLinkRecord] = []
    for label, links in MAJOR_LINKS.items():
        subject_id = generate_subject_id(CURRICULUM_CODE, label)
        for major_id, reason in links:
            records.append(
                SubjectMajorLinkRecord(
                    subject_id=subject_id, major_id=major_id, link_status="RELATED",
                    evidence=[
                        SubjectMajorLinkCurriculumEvidence(
                            source_url=MOE_URL, source_type="OFFICIAL_CURRICULUM_MOE_NOTICE", reason=reason,
                        )
                    ],
                    author_id=AUTHOR_ID, review_status="draft", mapping_version=LINK_MAPPING_VERSION,
                    note="39개 서비스 Major 확장(a/subject-mapping-38-majors) — 사람 검토 전 draft.",
                )
            )
    return records


def main() -> None:
    use_utf8_stdout()

    bad = {
        (label, major_id) for label, links in MAJOR_LINKS.items() for major_id, _ in links
        if major_id in FORBIDDEN_MAJOR_IDS
    }
    if bad:
        raise SystemExit(
            f"hci_ux(DEPARTMENT_LEVEL_ONLY, 자동 연결 금지)·예체능 추천 제외 Group으로의 "
            f"연결이 발견됐다: {sorted(bad)}"
        )

    link_records = _generate_link_records()
    MAJOR_LINK_EVIDENCE_V2_PATH.write_text(
        "\n".join(r.model_dump_json() for r in link_records) + "\n", encoding="utf-8"
    )
    print(f"{MAJOR_LINK_EVIDENCE_V2_PATH.relative_to(ROOT)}: {len(link_records)}행")
    print(f"Major Link 대상 과목 {len(MAJOR_LINKS)}개")


if __name__ == "__main__":
    main()
