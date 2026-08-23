# Major–Trait Mapping 2인 검토 Worksheet

**상태: 1차 검토(A) 완료, 2차 검토 미실시 — `review_status`는 전부 `draft`로 유지한다.**

이 문서는 `data/master/major_trait_mapping_evidence.jsonl`(36개 레코드 = 대표 전공 3개 ×
Trait 12개)에 대해 작업자 A가 1차로 수집·채점한 결과를 정리한 것이다. **아직 실제 2번째
사람이 검토하지 않았으므로, 이 문서나 Runtime 어디에도 "검증 완료된 적합도"라고 표시하지
않는다.** "2차 검토자 등급"·"차이"·"최종 합의" 열은 실제 2인 검토가 이뤄지기 전까지 전부
공란(TBD)이며, 이 상태로는 어떤 레코드도 `review_status="team_reviewed"`로 승격하지
않는다.

등급 채점 순서(§6): 공식 자료 수집 → 활동 추출 → Trait 연결 후보 → 공통 Rubric(0~3) 적용
→ 검토 → 등급 확정. 등급을 먼저 정하고 근거를 끼워 맞추지 않았다.

Rubric: **0** = 공식 자료가 이 활동이 명시적으로 중요하지 않다고 확인함. **1** = 일부
선택·비교과에서만 관련. **2** = 여러 교과에서 반복되거나 보조 활동으로 중요. **3** =
공식 교육목표·필수/핵심 교과에 반복 등장하는 핵심 학습 활동.

`mapping_status`가 `UNMAPPED`/`REVIEW_REQUIRED`인 행은 **"공식 근거를 찾지 못함 ≠ Trait
중요도 0"** 원칙에 따라 A의 등급 칸을 비워 뒀다(0으로 채우지 않음) — Matching 계산에서도
해당 Trait는 그 전공의 벡터에서 제외되며, 절대 0점으로 처리되지 않는다.

## industrial_engineering (고려대 산업경영공학부 / 경희대 산업경영공학과 / 숭실대 산업·정보시스템공학과)

| trait_id | A 등급 | 상태 | 근거(요약) | 2차 검토자 등급 | 차이 | 최종 합의 | 검토자 | 검토일 |
|---|---|---|---|---|---|---|---|---|
| causal_analysis | 3 | EVIDENCED | 3개교 공통: 생산·품질관리(스마트생산시스템) | TBD | TBD | TBD | TBD | TBD |
| pattern_finding | 2 | EVIDENCED | 3개교 공통: 데이터 분석(데이터마이닝) | TBD | TBD | TBD | TBD | TBD |
| planning | 3 | EVIDENCED | 3개교 공통: 최적화·운영관리(공급사슬·가치망 분석, 생산운영관리) | TBD | TBD | TBD | TBD | TBD |
| information_comparison | 3 | EVIDENCED | 3개교 공통: 의사결정(경영의사결정) | TBD | TBD | TBD | TBD | TBD |
| tool_utilization | 2 | EVIDENCED | 3개교 공통: 정보시스템(물류·교통정보시스템) | TBD | TBD | TBD | TBD | TBD |
| audience_response_prediction | — | REVIEW_REQUIRED | 3개교 공통: 인간공학(인지인간공학, 인간공학디자인) — 단서는 있으나 "사용자 반응 예측"과 "인간공학적 설계"가 동일 개념인지 확신 부족 | TBD | TBD | TBD | TBD | TBD |
| immediate_execution | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| change_adaptation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| collaboration_preference | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| opinion_mediation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| emotional_interpretation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| visual_expression | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |

## hci_ux (이화여자대학교 융합콘텐츠학과 — **연결된 학과 1곳뿐, 이 학과 하나로 HCI·UX 분야 전체를 일반화하지 않는다**)

| trait_id | A 등급 | 상태 | 근거(요약) | 2차 검토자 등급 | 차이 | 최종 합의 | 검토자 | 검토일 |
|---|---|---|---|---|---|---|---|---|
| audience_response_prediction | 3 | EVIDENCED | 사용자경험연구, UX스튜디오 | TBD | TBD | TBD | TBD | TBD |
| visual_expression | 2 | EVIDENCED | UI디자인, 인터페이스디자인연구 | TBD | TBD | TBD | TBD | TBD |
| tool_utilization | 2 | EVIDENCED | 콘텐츠프로그래밍기초, 웹콘텐츠개발, 모바일앱제작 | TBD | TBD | TBD | TBD | TBD |
| causal_analysis | — | REVIEW_REQUIRED | 사용자경험연구 — 사용자 리서치가 원인 분석과 얼마나 겹치는지 확신 부족 | TBD | TBD | TBD | TBD | TBD |
| collaboration_preference | — | REVIEW_REQUIRED | 융합콘텐츠캡스톤디자인 — 협업 프로젝트인지 개인 과제 비중이 큰지 확인 필요 | TBD | TBD | TBD | TBD | TBD |
| pattern_finding | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| planning | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| immediate_execution | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| change_adaptation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| opinion_mediation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| emotional_interpretation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| information_comparison | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |

## media_communication (경희대학교 미디어학과 / 고려대학교 미디어학부 — **영상편집 중심이 아니라 사회과학·데이터 분석 중심 학과임을 확인함**)

| trait_id | A 등급 | 상태 | 근거(요약) | 2차 검토자 등급 | 차이 | 최종 합의 | 검토자 | 검토일 |
|---|---|---|---|---|---|---|---|---|
| pattern_finding | 3 | EVIDENCED | 빅데이터분석과미디어, 미디어데이터마이닝(고려대); 데이터 커뮤니케이션 분야(경희대) | TBD | TBD | TBD | TBD | TBD |
| planning | 3 | EVIDENCED | 미디어캠페인기획, 창의적미디어기획과표현 | TBD | TBD | TBD | TBD | TBD |
| collaboration_preference | 3 | EVIDENCED | 캡스톤디자인 시리즈, 미디어캠페인기획(팀 프로젝트) | TBD | TBD | TBD | TBD | TBD |
| audience_response_prediction | 3 | EVIDENCED | 설득커뮤니케이션, 전략커뮤니케이션리서치(고려대); 여론·수용자 조사 연구방법(경희대) | TBD | TBD | TBD | TBD | TBD |
| causal_analysis | 2 | EVIDENCED | 데이터저널리즘(경희대); 미디어연구방법(고려대) | TBD | TBD | TBD | TBD | TBD |
| visual_expression | 2 | EVIDENCED | 영상콘텐츠기초제작실습, 드라마프로덕션·다큐멘터리프로덕션 — §7 경고에 따라 영상 제작 교과가 있음은 확인했으나 학과 전체가 영상 중심은 아니라고 판단해 3이 아닌 2로 제한 | TBD | TBD | TBD | TBD | TBD |
| information_comparison | 2 | EVIDENCED | 미디어연구방법, 전략커뮤니케이션리서치 | TBD | TBD | TBD | TBD | TBD |
| tool_utilization | 2 | EVIDENCED | 애널리틱스프로그래밍, 미디어데이터마이닝 — 데이터 도구 활용 중심이라 §7 경고에 따라 3이 아닌 2로 제한 | TBD | TBD | TBD | TBD | TBD |
| emotional_interpretation | — | REVIEW_REQUIRED | 설득커뮤니케이션 — 설득 대상의 감정 이해가 "타인의 감정 해석" Trait와 얼마나 겹치는지 확신 부족 | TBD | TBD | TBD | TBD | TBD |
| immediate_execution | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| change_adaptation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |
| opinion_mediation | — | UNMAPPED | 1차 조사 범위에서 확인 못함 | TBD | TBD | TBD | TBD | TBD |

## 다음 단계

1. 두 번째 사람이 위 근거(URL은 `data/master/major_trait_mapping_evidence.jsonl`의
   `evidence[].source_url`)를 직접 확인하고, 각 행의 "2차 검토자 등급"을 채운다.
2. A 등급과 2차 등급이 다르면 "차이" 열에 그 차이를 적고, 논의 후 "최종 합의" 열에 합의된
   값을 적는다.
3. 전부 채워지면 `data/master/major_trait_mapping_evidence.jsonl`의 해당 레코드
   `review_status`를 `"team_reviewed"`로 바꾸고, `scripts/career_build_major_profiles.py`를
   다시 실행해 `data/master/major_profiles.jsonl`을 재생성한다.
4. `REVIEW_REQUIRED`(industrial_engineering/audience_response_prediction,
   hci_ux/causal_analysis, hci_ux/collaboration_preference,
   media_communication/emotional_interpretation)는 이번 라운드에서 특히 2차 검토가
   필요하다 — 단서는 있지만 A 혼자 EVIDENCED로 확정하기엔 근거가 부족하다고 판단한 항목들이다.
