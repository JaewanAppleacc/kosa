# Department Offering Identity v2 — 행 단위 재검증

브랜치 `a/offering-identity-v2`. 이 검증은 16 Group·32행(이번 라운드가 실제로 건드린 범위)에만 한정한다 — career_build_national_department_promotion_dry_run.py의 24,422행 전체 재실행은 이번 라운드 범위 밖이다(그 산출물은 Git에 올리지 않는 기존 관례를 따른다).

## 1. 최종 회계

| 항목 | 값 |
|---|---:|
| 전체 행 | 32 |
| 전체 Group | 16 |
| offering_id 중복 | 0 |
| 일반과정 추천 노출 | 6 |
| 계약학과·산업체위탁 추천 제외(EXISTING) | 7 |
| ABOLISHED 추천 제외 | 17 |
| 공식 소계열 미분류(N.C.E) 추천 제외 | 2 |
| 미결 그룹 | 0 |
| 자동 대표 판정 오류(의미 있는 교정) | 6 |
| 기존 CONTRACT_DEPARTMENT 태그와 모순 없음 | True |

## 2. 지정 검증 사례

- 성균관대학교 반도체시스템공학과 추천 대표 없음: **True**
- 충남대학교 약학과는 6년 일반과정만 추천 범위: **True**

## 3. Group별 상세(16개)

| department_id | 대학·학과 | 자동 대표 | 사람 대표 | 교정 여부 | offering_id |
|---|---|---|---|---|---|
| dept_10800aff0e089ba439b3ecc1 | 영남대학교 경영학과 | src_9f231a2783e44a045f23a36a | src_dbec10f16d8b430380d72985 | 예 | off_14c073d308931b4e475c4923, off_6c859a411bc97d87f97714eb |
| dept_14ad9d052ef2f77d303f6eb3 | 서경대학교 코스메틱뷰티매니지먼트학과 | src_e0d97a4caccb8b0612fd3a68 | (없음) | 아니오 | off_39f12c4a8822f4db03ebeabe, off_bc5512850cfa033ef432a62e |
| dept_1fb390a6b08e933947ce546f | 경동대학교 간호학과 | src_17755f9f717df10c34e9757c | (없음) | 아니오 | off_840e06f28619bea548841722, off_bc328ef98001aa1f669e36b1 |
| dept_282fbbc113924e6b219824ec | 중앙대학교 약학부 | src_07213e474f85500d7929fb6f | src_5f1857f7728624ca764e0488 | 예 | off_31facaf7526b7a55a343b09c, off_42abf04ca96c262ddacb8039 |
| dept_4b358345687aed927da6a9fa | 성균관대학교 반도체시스템공학과 | src_4f4827d9551700893de144de | (없음) | 아니오 | off_2ac577cdfbfcb7d21d51233f, off_69f657a7d113ed1aa0fef03f |
| dept_4dec239f5d58c90b51c3e8ff | 서경대학교 헤어디자인학과 | src_6c9b529114533ba484d19e61 | (없음) | 아니오 | off_84d4576f505795e079516ddd, off_cde243ad91cf4cdda1990da0 |
| dept_68619097f1dbc3aaec18de8f | 서경대학교 뷰티테라피 & 메이크업학과 | src_4a9e0852ee52b3d2061c782c | (없음) | 아니오 | off_bc0f51e348d42a014364f971, off_d8acefe446e715419a87e761 |
| dept_6ea537f2938a79ba48bef719 | 충남대학교 약학과 | src_1c796c51cd964c139da0462e | src_8741cd6307fc8b4182a4dbdc | 예 | off_0004a4bec4927fe34568380e, off_b437d43468822b0614834d9d |
| dept_7df04a9c12d5f3a7b1940934 | 서경대학교 헤어？메이크업 디자인학과 | src_660449368660eb3ca02359c4 | (없음) | 아니오 | off_522032e7c84fe2e48c22c71d, off_b8bfccdb3310d9073b2d5a8e |
| dept_95498184076d8554d6c4d732 | 동국대학교 행정학전공 | src_0ec3fdd48267ca11c90846ee | (없음) | 아니오 | off_3f437583f336c66db2fb71f3, off_d1ef4fb18ebf27695ec00195 |
| dept_9a08f666b438da9bcb0b6967 | 가천대학교 인터랙티브미디어학과 | src_977ea81c679da9842e9449bb | (없음) | 아니오 | off_647fe69c12ce7a417844e706, off_c683bfe2c30168073dbdcae8 |
| dept_9d718e06d0d0d7e95945c732 | 한일장신대학교 사회복지학과 | src_4fcef86155dfa2d623d0a57c | src_3078c8a4887dde2d328affbe | 예 | off_3f95538581c1c8d04e23ef6b, off_c6420dc30dd3b469684ab410 |
| dept_b9470f162837a7b20cb243ba | 성균관대학교 반도체시스템공학전공 | src_c26c3fd5b658ffe89368a57e | (없음) | 아니오 | off_8e39bb32e1393b267372c9a7, off_a917233af774b53c7d48977a |
| dept_d4d6a4d5c2c3deffd36ac54c | 원광대학교 약학과(2+4학제) | src_8609307f9560d236343eae79 | src_fdc6fcc2d14ab14feefe1a52 | 예 | off_11bcae79fbd9cd4892192024, off_83446198e9a91c2fdde496b9 |
| dept_d88abaf818af2ba09ef78db9 | 서경대학교 코스메틱&뷰티테라피학과 | src_3724ec9904f5b267fa57bd5f | (없음) | 아니오 | off_c79023f4e334a29061f29b9c, off_cc5dd7309ebc554a4d2a220b |
| dept_e0cfd8e2595fa2ebf044a988 | 동신대학교 사회복지학과 | src_3ff8c9612cb1b70aee35f965 | src_e2c9b39d883e4e8a4911de8b | 예 | off_6cc043cff6e5e646fc88879c, off_ddde03043a6cd04de15c44b9 |

