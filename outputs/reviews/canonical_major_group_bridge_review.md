# Canonical Major Group ↔ Canonical Major Bridge 검수 자료

대학알리미 표준분류 소계열 158개를 묶은 42개 Canonical Major Group(분류용 중간 Ontology)과, 학생에게 실제로 보여주는 10개 서비스 추천 전공(`data/master/canonical_majors.jsonl`) 사이의 연결을 명시적으로 남긴 자료다. **42개 Group은 10개 추천 전공을 대체하지 않는다** — 이 문서는 두 계층을 잇는 다리(Bridge)의 현재 draft 상태를 보여줄 뿐이다.

**이 문서의 어떤 항목도 이미 승인(APPROVE)된 것이 아니다.** "현재 상태" 열은 시스템이 계산한 분류 판단(`mapping_status`)이고, "사용자 검토 결과" 열은 사람이 실제로 검토하기 전까지 항상 빈 칸이다.

## 1. 영향 분석 (승격 전 후보 분석 — 실제 추천 결과가 아님)

아래 수치는 `data/master/canonical_major_group_bridge.draft.jsonl`(모두 draft 상태)과 `data/academyinfo_work/2025/classification_dry_run.json`(분류 단계 집계)을 그대로 센 것이다. 공개 API·Matching은 이 Bridge를 아직 전혀 참조하지 않는다(§3) — 학생에게 보이는 추천 결과와 무관하다.

### 1-1. 기존 10개 Major별 연결 Group 후보 수

| major_id | label | 연결 Group 후보 수 | 상태 구성 |
|---|---|---|---|
| business_administration | 경영학 | 1 | EVIDENCED 1 |
| computer_science | 컴퓨터·소프트웨어 | 1 | EVIDENCED 1 |
| design | 디자인 | 1 | EXCLUDED_RECOMMENDATION 1 |
| education | 교육학 | 1 | EVIDENCED 1 |
| hci_ux | HCI·UX | 2 | EXCLUDED_RECOMMENDATION 1, REVIEW_REQUIRED 1 |
| industrial_engineering | 산업공학 | 1 | EVIDENCED 1 |
| life_science | 생명과학 | 2 | EVIDENCED 1, REVIEW_REQUIRED 1 |
| mechanical_engineering | 기계공학 | 1 | EVIDENCED 1 |
| media_communication | 미디어·커뮤니케이션 | 1 | EVIDENCED 1 |
| psychology | 심리학 | 1 | EVIDENCED 1 |

### 1-2. 대표 전공 3개와 연결 가능한 전국 학과 후보 수 (승격 전)

| major_id | 연결 Group(상태) | 그 Group의 학과 후보 수 | 비고 |
|---|---|---|---|
| media_communication | media_communication(EVIDENCED) | 351 | 확정 아님 — Bridge 자체가 draft |
| industrial_engineering | industrial_engineering(EVIDENCED) | 316 | 확정 아님 — Bridge 자체가 draft |
| hci_ux | computer_science(REVIEW_REQUIRED) | 1284 | 확정 아님 — 사람 검토 필요 |
| hci_ux | fine_arts_design(EXCLUDED_RECOMMENDATION) | 1262 | 확정 아님 — Bridge 자체가 draft |

### 1-3. REVIEW_REQUIRED로 인해 확정에서 제외되는 수

- REVIEW_REQUIRED Bridge 행 수: 2
- 그 행들이 가리키는 Group의 학과 후보 수 합계(중복 Group 있으면 중복 합산): 1557

### 1-4. 예체능 제외 수

- EXCLUDED_RECOMMENDATION Group 수: 4개 (fine_arts_design, music, performing_media_arts, sports_dance)
- 그 Group들의 학과 후보 수 합계(`departments_per_canonical_group` 기준): 3168
- 참고: `classification_dry_run.json`의 `eligibility_breakdown.EXCLUDED_ARTS_SPORTS` = 3588(분류 자격 판정 단계 집계, Group 배정 이후 집계인 위 3168과 집계 시점이 달라 정확히 일치하지 않는다 — 두 수치를 그대로 병기한다).

### 1-5. N.C.E / UNMAPPED 수

- Bridge UNMAPPED Group 수(10개 서비스 전공 중 대응 항목 없음): 29개
- 그 Group들의 학과 후보 수 합계: 11462
- N.C.E(대학알리미 표준분류 미분류, 42개 Group 어디에도 배정되지 않음) 원본 학과 수: 3539건(`classification_dry_run.json`의 `unclassified_nce_count` — 이 수는 Bridge의 UNMAPPED와 별개다. Bridge UNMAPPED는 "42개 Group 중 하나로는 분류됐지만 10개 서비스 전공에는 대응이 없다"이고, N.C.E는 "애초에 42개 Group 중 어디에도 분류되지 않았다"이다.)

## 2. 42개 Group 전체 — 연결 후보·근거·경계 사례

| Group ID | Group 라벨 | 공식 소계열 코드·명칭 | 연결 후보 Major | 근거 | 경계 사례 | 현재 상태 | 사용자 검토 결과 |
|---|---|---|---|---|---|---|---|
| agriculture_fisheries | 농림·수산 | 058, 059, 060, 061, 063 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| bio_medical_engineering | 생명공학·의공학 | 088, 100 | life_science | 소계열 '생명공학'(Group에 포함); Major 별칭: 생명공학 | 생명과학(기초과학) vs 생명공학·의공학(응용 공학) 성격 차이 — 자동 확정하지 않고 사람 검토로 남긴다. | REVIEW_REQUIRED | |
| business | 경영학 | 033, 035, 041, 151, 152 | business_administration | 소계열 '경영학'; Major 라벨: 경영학 | Group에는 경영정보학·비서·금융보험학·회계세무학도 포함돼 Major 별칭보다 범위가 다소 넓다. | EVIDENCED | |
| chemical_energy | 화학공학·에너지 | 097, 098, 099 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| chemistry | 화학 | 055 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| civil_architecture | 건축·토목·환경 | 072, 073, 074, 075, 076, 077 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| clothing_housing | 의류·주거·소비자 | 026, 068, 069 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| computer_science | 컴퓨터·소프트웨어·AI | 089, 090, 157 | computer_science | 소계열 '전산학·컴퓨터공학'; 소계열 '응용소프트웨어공학'; 소계열 '인공지능공학'; Major 별칭: 컴퓨터공학, 컴퓨터과학, 전산학, 소프트웨어, 인공지능 | (없음) | EVIDENCED | |
| computer_science | 컴퓨터·소프트웨어·AI | 089, 090, 157 | hci_ux | Major 별칭: 인간컴퓨터상호작용, 융합콘텐츠, UX디자인; Group 소계열: 응용소프트웨어공학, 인공지능공학(개념적 연관, 공식 코드명 직접 일치 아님) | 이 Group은 computer_science Major에는 이미 EVIDENCED로 연결돼 있다 — 같은 Group이 두 Major 후보(computer_science, hci_ux)에 걸리는 경우지만, computer_science는 공식 코드 직접 일치, hci_ux는 별칭 수준 연관이라 서로 다른 근거 강도이므로 각각 다른 상태로 둔다(하나를 자동으로 확정하지 않는다). | REVIEW_REQUIRED | |
| dentistry | 치의학 | 108, 145 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| earth_environment | 지구·지리·환경 | 052, 053, 057, 062, 028 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| economics | 경제학 | 034 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| education | 교육학 | 042, 043, 046, 070, 105, 117, 141, 153, 154, 155 | education | 소계열 '교육학'; Major 라벨: 교육학 | Group에는 언어교육·초등교육·유아교육·특수교육 등 세부 교육 분야도 포함된다. | EVIDENCED | |
| electrical_electronic | 전기·전자·정보통신 | 084, 085, 086, 087, 091 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| fine_arts_design | 미술·디자인 | 118, 124, 125, 126, 127, 128, 135, 142 | design | 소계열 '디자인'; Major 라벨: 디자인 | (없음) | EXCLUDED_RECOMMENDATION | |
| fine_arts_design | 미술·디자인 | 118, 124, 125, 126, 127, 128, 135, 142 | hci_ux | Major 별칭: UX디자인, 서비스디자인, 인터랙션디자인; 소계열 '디자인'(Group에 포함) | hci_ux는 이 Group과 computer_science Group(REVIEW_REQUIRED) 두 곳에 걸쳐 있다 — 하나의 서비스 전공이 여러 Group과 연결되는 것은 지시서 §2에서 허용한다. | EXCLUDED_RECOMMENDATION | |
| food_nutrition | 식품·영양·조리 | 064, 066, 067 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| foreign_language | 외국어·언어학 | 001, 003, 004, 005, 006, 007, 008, 009, 010, 011 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| health_science | 보건·재활 | 113, 114, 115, 116, 163 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| humanities | 철학·역사·종교 | 013, 014, 015, 016, 030 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| industrial_engineering | 산업공학·안전 | 102, 103, 104 | industrial_engineering | 소계열 '산업공학'; Major 별칭: 산업공학, 산업경영공학, 산업시스템공학; 기존 시연 Department(산업경영공학과/산업경영공학부/산업·정보시스템공학과)가 이미 이 Major로 연결됨 | Group에는 안전공학·방재공학도 포함돼 있어 Major 키워드(최적화/운영관리/생산관리/데이터분석)와 결이 다른 학과가 섞일 수 있다 — 안전공학·방재공학 학과를 후보에서 뺄지는 사람 검토가 필요하다. | EVIDENCED | |
| korean_literature | 국어국문·문예창작 | 002, 148 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| korean_medicine | 한의학 | 109, 111, 146 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| law | 법학 | 019 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| life_science | 생명과학 | 056, 156 | life_science | 소계열 '생명과학'; Major 라벨: 생명과학 | (없음) | EVIDENCED | |
| mathematics_statistics | 수학·통계 | 048, 049 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| mechanical_transport | 기계·자동차·항공·조선 | 078, 079, 080, 081, 082, 083, 158, 159, 160, 161, 162 | mechanical_engineering | 소계열 '기계공학'; Major 라벨: 기계공학 | Group에는 자동차공학·항공우주공학·조선해양공학·철도공학 등 응용 분야도 포함돼 있어 실제 학과 후보 범위가 Major 별칭(기계공학/기계시스템/기계설계)보다 넓다 — 자동차/항공/조선 학과까지 '기계공학' 후보로 보여줄지는 사람 검토가 필요하다. | EVIDENCED | |
| media_communication | 미디어·광고 | 027, 038 | media_communication | 소계열 '언론·방송·매체학'; 소계열 '광고·홍보학'; Major 별칭: 신문방송학, 언론정보학 | (없음) | EVIDENCED | |
| medicine | 의학 | 107, 144, 150 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| music | 음악 | 129, 130, 131, 132, 133, 134, 140 | (대응 없음) | (없음) | (없음) | EXCLUDED_RECOMMENDATION | |
| nursing | 간호학 | 112 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| performing_media_arts | 연극·영화·영상콘텐츠 | 121, 122, 123, 136, 137, 138, 139 | (대응 없음) | (없음) | (없음) | EXCLUDED_RECOMMENDATION | |
| pharmacy | 약학 | 110 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| physics_astronomy | 물리·천문 | 050, 051 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| political_science | 정치외교·국제학 | 022, 149, 017, 023 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| psychology | 심리학 | 020 | psychology | 소계열 '심리학'(Group의 유일한 소계열); Major 라벨: 심리학 | (없음) | EVIDENCED | |
| public_administration | 행정·정책 | 029 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| semiconductor_materials | 반도체·신소재 | 092, 093, 094, 095, 096, 101 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| social_welfare | 사회복지·아동가족 | 024, 025 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| sociology | 사회학·문헌정보 | 021, 031 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| sports_dance | 체육·무용 | 119, 120 | (대응 없음) | (없음) | (없음) | EXCLUDED_RECOMMENDATION | |
| tourism | 관광 | 039 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| trade_logistics | 무역·유통·부동산 | 037, 040 | (대응 없음) | (없음) | (없음) | UNMAPPED | |
| veterinary | 수의학 | 065, 147 | (대응 없음) | (없음) | (없음) | UNMAPPED | |

## 3. 근거 문장(decision_reason) 상세

표가 좁아 잘리는 근거 설명 전문을 Group 순서대로 남긴다.

- **agriculture_fisheries → (대응 없음)** (UNMAPPED): 농림·수산은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **bio_medical_engineering → life_science** (REVIEW_REQUIRED): Major 별칭에 '생명공학'이 있고 이 Group의 소계열에도 '생명공학'이 포함되지만, Group은 의공학(응용 공학) 중심이라 life_science Major의 기초과학 성격과 결이 다르다.
- **business → business_administration** (EVIDENCED): Major 라벨 '경영학'이 Group의 핵심 소계열 '경영학'과 동일하다.
- **chemical_energy → (대응 없음)** (UNMAPPED): 화학공학·에너지는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **chemistry → (대응 없음)** (UNMAPPED): 화학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **civil_architecture → (대응 없음)** (UNMAPPED): 건축·토목·환경은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **clothing_housing → (대응 없음)** (UNMAPPED): 의류·주거·소비자는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **computer_science → computer_science** (EVIDENCED): Major 별칭(컴퓨터공학/컴퓨터과학/전산학/소프트웨어/인공지능)이 Group의 공식 소계열 3개와 명칭 수준에서 직접 일치한다.
- **computer_science → hci_ux** (REVIEW_REQUIRED): hci_ux Major 별칭(인간컴퓨터상호작용/융합콘텐츠)이 Group의 응용소프트웨어공학·인공지능공학과 개념적으로 연관되지만, 대학알리미 공식 소계열 158개 안에 'HCI'·'UX'·'인터랙션'에 정확히 대응하는 코드가 없어 직접 근거로 보기 어렵다.
- **dentistry → (대응 없음)** (UNMAPPED): 치의학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **earth_environment → (대응 없음)** (UNMAPPED): 지구·지리·환경은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **economics → (대응 없음)** (UNMAPPED): 경제학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **education → education** (EVIDENCED): Major/Group 라벨이 모두 '교육학'이며 Group의 핵심 소계열도 '교육학'이다.
- **electrical_electronic → (대응 없음)** (UNMAPPED): 전기·전자·정보통신은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **fine_arts_design → design** (EXCLUDED_RECOMMENDATION): Group의 공식 소계열 '디자인'이 design Major 라벨과 직접 일치하지만, design Canonical Major는 기존 EXCLUDED_RECOMMENDATION_MAJOR_IDS 정책(src/services/major_exploration_service.py)으로 추천에서 이미 제외돼 있다 — Bridge도 동일하게 제외 상태로 명시한다.
- **fine_arts_design → hci_ux** (EXCLUDED_RECOMMENDATION): hci_ux Major 별칭(UX디자인/서비스디자인/인터랙션디자인)이 Group의 '디자인' 소계열과 연관되지만, fine_arts_design은 예체능 4개 Group 중 하나로 정책상 추천에서 제외된다.
- **food_nutrition → (대응 없음)** (UNMAPPED): 식품·영양·조리는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **foreign_language → (대응 없음)** (UNMAPPED): 외국어·언어학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **health_science → (대응 없음)** (UNMAPPED): 보건·재활은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **humanities → (대응 없음)** (UNMAPPED): 철학·역사·종교는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **industrial_engineering → industrial_engineering** (EVIDENCED): Group의 공식 소계열 '산업공학'이 Major 라벨과 정확히 일치하며, 기존 시연 Department도 이미 이 Major로 연결돼 있다.
- **korean_literature → (대응 없음)** (UNMAPPED): 국어국문·문예창작은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **korean_medicine → (대응 없음)** (UNMAPPED): 한의학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **law → (대응 없음)** (UNMAPPED): 법학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **life_science → life_science** (EVIDENCED): Major 라벨 '생명과학'이 Group의 공식 소계열 '생명과학'과 동일하다.
- **mathematics_statistics → (대응 없음)** (UNMAPPED): 수학·통계는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **mechanical_transport → mechanical_engineering** (EVIDENCED): Group의 공식 소계열 중 '기계공학'이 Major 라벨과 정확히 일치한다.
- **media_communication → media_communication** (EVIDENCED): Major 별칭(신문방송학/언론정보학)이 Group의 공식 소계열 '언론·방송·매체학'과 직접 일치하며, 광고·홍보학도 미디어·커뮤니케이션 범주에 속한다.
- **medicine → (대응 없음)** (UNMAPPED): 의학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **music → (대응 없음)** (EXCLUDED_RECOMMENDATION): 예체능 계열이며 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 중 대응하는 항목이 없다. design Canonical Major와 동일한 예체능 제외 정책 대상으로 명시한다 — '근거 없어서 UNMAPPED'가 아니라 '실존하는 분야이지만 정책상 제외'임을 분명히 하기 위해 EXCLUDED_RECOMMENDATION을 쓴다.
- **nursing → (대응 없음)** (UNMAPPED): 간호학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **performing_media_arts → (대응 없음)** (EXCLUDED_RECOMMENDATION): 예체능 계열이며 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 중 대응하는 항목이 없다. design Canonical Major와 동일한 예체능 제외 정책 대상으로 명시한다 — '근거 없어서 UNMAPPED'가 아니라 '실존하는 분야이지만 정책상 제외'임을 분명히 하기 위해 EXCLUDED_RECOMMENDATION을 쓴다.
- **pharmacy → (대응 없음)** (UNMAPPED): 약학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **physics_astronomy → (대응 없음)** (UNMAPPED): 물리·천문은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **political_science → (대응 없음)** (UNMAPPED): 정치외교·국제학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **psychology → psychology** (EVIDENCED): Major/Group 라벨과 유일 소계열이 모두 '심리학'으로 동일하다.
- **public_administration → (대응 없음)** (UNMAPPED): 행정·정책은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **semiconductor_materials → (대응 없음)** (UNMAPPED): 반도체·신소재는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **social_welfare → (대응 없음)** (UNMAPPED): 사회복지·아동가족은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **sociology → (대응 없음)** (UNMAPPED): 사회학·문헌정보는 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **sports_dance → (대응 없음)** (EXCLUDED_RECOMMENDATION): 예체능 계열이며 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 중 대응하는 항목이 없다. design Canonical Major와 동일한 예체능 제외 정책 대상으로 명시한다 — '근거 없어서 UNMAPPED'가 아니라 '실존하는 분야이지만 정책상 제외'임을 분명히 하기 위해 EXCLUDED_RECOMMENDATION을 쓴다.
- **tourism → (대응 없음)** (UNMAPPED): 관광은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **trade_logistics → (대응 없음)** (UNMAPPED): 무역·유통·부동산은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
- **veterinary → (대응 없음)** (UNMAPPED): 수의학은 현재 10개 서비스 추천 전공(canonical_majors.jsonl) 어디에도 대응하는 항목이 없다 — 근거 없음(UNMAPPED), 향후 서비스 확장 후보로만 남긴다.
