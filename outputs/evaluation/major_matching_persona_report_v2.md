# 39개 Service Major v2 — 고정 Persona 회귀 진단

브랜치 `a/major-profiles-v2-38`. `matching_engine_v2.py`의 공식·가중치·최소
Evidence 기준은 전혀 수정하지 않았다 — 있는 그대로 호출한 결과를 그대로 기록한다.

## 1. 요약

| 항목 | 값 |
|---|---:|
| Persona 수 | 48 |
| 전체 Major 수 | 39 |
| 최소 1회 추천 후보가 된 Major 수 | 39 |
| 한 번도 후보가 안 된 Major | (없음) |
| 자기 전공 Top-3 적중 | 45 / 46 |
| 상위 3개 Major의 전체 노출 점유율 | 21.0% |

## 2. 가장 자주 노출된 Major 3개

| major_id | 노출 횟수 |
|---|---:|
| bio_medical_engineering | 6 |
| media_communication | 6 |
| chemical_energy | 5 |

## 3. Persona별 상세

| persona_id | target | self 적중 | 관련성 높음 | 함께 탐색 |
|---|---|---|---|---|
| self_agriculture_fisheries | agriculture_fisheries | True | agriculture_fisheries | (없음) |
| self_bio_medical_engineering | bio_medical_engineering | True | bio_medical_engineering, chemical_energy | (없음) |
| self_business_administration | business_administration | True | business_administration | (없음) |
| self_chemical_energy | chemical_energy | True | bio_medical_engineering, chemical_energy | (없음) |
| self_chemistry | chemistry | True | chemistry | (없음) |
| self_civil_architecture | civil_architecture | True | civil_architecture | (없음) |
| self_clothing_housing | clothing_housing | True | clothing_housing | (없음) |
| self_computer_science | computer_science | True | computer_science, electrical_electronic | (없음) |
| self_dentistry | dentistry | True | dentistry, food_nutrition | (없음) |
| self_earth_environment | earth_environment | True | earth_environment | (없음) |
| self_economics | economics | True | economics, humanities, korean_medicine | (없음) |
| self_education | education | True | education | (없음) |
| self_electrical_electronic | electrical_electronic | True | computer_science, electrical_electronic | (없음) |
| self_food_nutrition | food_nutrition | True | dentistry, food_nutrition | (없음) |
| self_foreign_language | foreign_language | True | foreign_language | (없음) |
| self_health_science | health_science | True | health_science | (없음) |
| self_humanities | humanities | True | economics, humanities | (없음) |
| self_korean_literature | korean_literature | True | korean_literature | (없음) |
| self_korean_medicine | korean_medicine | True | economics, korean_medicine | (없음) |
| self_law | law | True | law | (없음) |
| self_life_science | life_science | True | life_science | (없음) |
| self_mathematics_statistics | mathematics_statistics | True | mathematics_statistics, sociology | (없음) |
| self_mechanical_engineering | mechanical_engineering | True | mechanical_engineering | (없음) |
| self_medicine | medicine | True | medicine | (없음) |
| self_nursing | nursing | True | nursing | (없음) |
| self_pharmacy | pharmacy | True | pharmacy | (없음) |
| self_physics_astronomy | physics_astronomy | True | physics_astronomy | (없음) |
| self_political_science | political_science | True | political_science | (없음) |
| self_psychology | psychology | True | psychology | (없음) |
| self_public_administration | public_administration | True | public_administration | (없음) |
| self_semiconductor_materials | semiconductor_materials | True | semiconductor_materials | (없음) |
| self_social_welfare | social_welfare | True | social_welfare | (없음) |
| self_sociology | sociology | True | economics, mathematics_statistics, sociology | (없음) |
| self_tourism | tourism | True | media_communication, tourism | (없음) |
| self_trade_logistics | trade_logistics | True | trade_logistics | (없음) |
| self_veterinary | veterinary | True | veterinary | (없음) |
| self_hci_ux | hci_ux | True | hci_ux, media_communication | (없음) |
| self_industrial_engineering | industrial_engineering | True | industrial_engineering, media_communication | (없음) |
| self_media_communication | media_communication | True | hci_ux, industrial_engineering, media_communication | (없음) |
| confusion_caring_cluster | nursing, social_welfare, health_science | True | health_science, nursing, social_welfare | (없음) |
| confusion_engineering_cluster | computer_science, electrical_electronic, mechanical_engineering, civil_architecture, semiconductor_materials, bio_medical_engineering | True | agriculture_fisheries, bio_medical_engineering, chemical_energy | (없음) |
| confusion_hci_design_cluster | hci_ux, media_communication | True | hci_ux, industrial_engineering, media_communication | (없음) |
| confusion_medical_cluster | medicine, dentistry, pharmacy, korean_medicine, veterinary | False | agriculture_fisheries, bio_medical_engineering, chemical_energy | (없음) |
| confusion_natural_science_cluster | chemistry, physics_astronomy, life_science, earth_environment, mathematics_statistics | True | bio_medical_engineering, chemical_energy, chemistry | (없음) |
| confusion_planning_cluster | business_administration, public_administration, trade_logistics, tourism | True | business_administration, media_communication, political_science | (없음) |
| confusion_social_science_cluster | sociology, political_science, humanities, psychology | True | economics, humanities, korean_medicine | (없음) |
| sparse_low_evidence | (대조군) | — | (없음) | (없음) |
| all_traits_strong | (대조군) | — | agriculture_fisheries, bio_medical_engineering, business_administration | (없음) |

