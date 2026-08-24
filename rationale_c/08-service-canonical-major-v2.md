# Service Canonical Major v2 — 39개 전공군 중앙 계약

2026-08-25 지시서(a/service-major-catalog-v2), 2026-08-25 후속 보완(04096a4 후속
— hci_ux 서비스 Major 보존). 이 문서는 `data/master/
service_canonical_majors_v2.jsonl`·`data/master/canonical_major_group_to_service_major_v2.jsonl`
두 산출물을 다른 작업자가 안전하게 소비하기 위한 개발 가이드다.

## 이 라운드가 하는 일 / 하지 않는 일

**한다**: 42개 Canonical Major Group(`data/canonical_major_groups.draft.jsonl`,
분류 Ontology 초안) 중 추천 제외 예체능 4개를 뺀 38개를 "서비스가 실제로 추천해도
되는 Major 목록"(`mapping_scope="FULL_GROUP"`)으로 확정하고, 여기에 어느 Group에도
통째로 속하지 않는 특수 융합 Major 1개(`hci_ux`, `mapping_scope=
"DEPARTMENT_LEVEL_ONLY"`)를 더해 총 39개를 만든다. 각 Major에 label·description·
aliases·keywords·(canonical_major_group_id 또는 source_group_ids)·mapping_scope·
recommendation_status·official_source_urls·catalog_version을 채운 Catalog와,
42개 Group 전부에 대한 Migration/Bridge 기록을 만든다(hci_ux는 어느 Group의
"기본 서비스 Major"도 아니라 이 Bridge 42행에는 없다 — 아래 hci_ux 절 참고).

**하지 않는다**(지시서 §3/§5):

- Trait Weight·학과·과목 Mapping을 만들지 않는다 — 이 38개는 아직 "이름·설명만
  확정된" Major다. Matching Engine이 실제로 쓰려면 후속 라운드가 `major_profiles_v2`
  류 Trait Vector를 별도로 만들어야 한다.
- `src/api/main.py`·Matching Engine(`matching_engine.py`/`matching_engine_v2.py`)·
  `vertical_slice_major_profiles_v2.py`·Department Master·과목/Subgraph·공개 API를
  손대지 않는다. 이 Catalog는 아직 **Runtime에 배선되지 않은 정본 데이터**일 뿐이다.
- Review를 자동 생성하지 않는다 — `data/reviews/`는 무변경이다.

## 42개 Group → 38개 서비스 Major 매핑 원칙

| Group ID | 서비스 Major ID | 근거 |
|---|---|---|
| `fine_arts_design`/`music`/`performing_media_arts`/`sports_dance` | (없음, `EXCLUDED_RECOMMENDATION`) | 지시서가 명시한 예체능 4개 — 분류 Ontology·Context는 유지, 추천 후보에서만 제외 |
| `business` | `business_administration` | 지시서 §1 명시 Bridge(표기만 다름) |
| `mechanical_transport` | `mechanical_engineering` | 지시서 §1 명시 Bridge(표기만 다름) |
| `computer_science`/`media_communication`/`industrial_engineering`/`psychology`/`life_science`/`education` | Group ID와 동일 | 기존 10개 Canonical Major와 Group ID가 이미 같다 — Bridge 불필요, 그대로 재사용 |
| 나머지 30개 | Group ID와 동일 | 기존 10개와 안 겹치는 신규 서비스 Major — Group 자체의 label/description/공식 소계열로 새로 만든다 |

기존 10개 중 `design`만 이번 39개에 없다 — `fine_arts_design`(예체능) Group에
해당해 추천 제외 대상이다.

## hci_ux — 특수 융합 Major(04096a4 후속 보완)

최초 버전(04096a4)은 hci_ux를 "42개 Group 중 어디에도 없는 교차 개념"이라는
이유로 통째로 뺐다. 후속 보완은 그 판단을 뒤집지 않고 더 정확하게 만든다 —
hci_ux를 **없는 것**이 아니라 **Group 기반이 아닌 것**으로 표현한다.

`data/master/canonical_major_group_bridge.draft.jsonl`(worker-c 정본, 이 라운드가
전혀 건드리지 않는다)에 이미 실제로 기록된 두 행이 근거다.

| Group | hci_ux에 대한 실제 기록 | 이 Catalog에서의 뜻 |
|---|---|---|
| `computer_science` | `mapping_status="REVIEW_REQUIRED"`, `scope_type="DEPARTMENT_REVIEW_REQUIRED"` — 응용소프트웨어공학·인공지능공학과 개념적으로만 연관, 158개 공식 소계열에 HCI·UX·인터랙션 직접 대응 코드 없음 | Group 전체를 넘기지 않는다 — 개별 학과만 후속 검토 대상 |
| `fine_arts_design` | `mapping_status="EXCLUDED_RECOMMENDATION"` — 예체능 Group 자체가 추천 제외 | 마찬가지로 Group 전체를 넘기지 않는다 |

**두 Group 다 hci_ux에 "Group 전체"를 승격해 준 적이 없다** — 그래서 hci_ux는
`canonical_major_group_id`(단일 필수 Group) 대신 다음 세 필드를 쓴다.

- `canonical_major_group_id: null`
- `source_group_ids: ["computer_science", "fine_arts_design"]` — 참고용 출처일
  뿐 소속 선언이 아니다.
- `mapping_scope: "DEPARTMENT_LEVEL_ONLY"`

**`source_group_ids`에 Group ID가 있다는 사실 자체는 그 Group 소속 학과를 자동으로
hci_ux에 편입시키는 근거가 아니다.** `fine_arts_design`이 `source_group_ids`에
있어도 그 Group은 여전히 `EXCLUDED_RECOMMENDATION`이고, `computer_science`가
있어도 그 Group의 Bridge 행(`service_major_id="computer_science"`)은 전혀
바뀌지 않는다 — `computer_science` Group의 "기본 서비스 Major"는 여전히
`computer_science` 자신이다. 학과 단위로 실제 HCI·UX 근거(교육과정에서 확인되는
사용자 연구·인터랙션 설계 등)가 검토·승인된 것만 나중에 hci_ux에 연결될 수 있다
— 이 라운드는 그 개별 학과 검토 자체를 하지 않는다(Trait Weight·학과 Mapping과
같은 이유로 범위 밖).

label/description/aliases/keywords는 `data/master/canonical_majors.jsonl`의
기존 hci_ux 행에서 한 글자도 바꾸지 않고 그대로 가져온다.

## 데이터 출처 — 지어낸 값 없음

모든 필드는 세 정본에서만 온다(어느 것도 새로 지어내지 않는다).

1. **Group label/description** — `data/canonical_major_groups.draft.jsonl`. 새
   Major의 description은 Group description을 "…전공 분야입니다." 관례로만 옮긴다.
2. **기존 10개 Canonical Major** — `data/master/canonical_majors.jsonl`. Group ID가
   겹치면(직접 동일 또는 위 표의 Bridge 2건) label/description/aliases/keywords를
   그대로 재사용한다.
3. **대학알리미 공식 표준분류 소계열 이름표** — `getCodeBySmallSeries`
   (`data/academyinfo_raw/2025/codes/getCodeBySmallSeries.jsonl.gz`). 기존 10개와
   안 겹치는 30개 Major의 keywords는 그 Group에 실제로 속한 공식 소계열 이름
   (예: `civil_architecture` → 건축학·건축공학·조경학·토목공학·도시공학·환경공학)을
   그대로 쓴다. Aliases는 Group label을 `·`로 쪼갠 조각이다.

## Alias 모호성 처리

Group label을 `·`로 쪼개다 보면 서로 다른 두 Group에 같은 조각 단어가 우연히
나타날 수 있다(실측: `civil_architecture`(건축·토목·환경)와
`earth_environment`(지구·지리·환경) 양쪽에 "환경"이 나온다, `bio_medical_
engineering`의 "생명공학"이 기존 `life_science` alias의 "생명공학"과 겹친다).
생성 스크립트(`_remove_ambiguous_cross_major_aliases()`)가 이런 alias를 **양쪽
Major 모두에서** 제거한다 — 전체 label 자체("건축·토목·환경")는 항상 별도로 남아
있으므로 목록이 비지는 않는다. `life_science`의 alias 목록이 기존 10개 시절과 한
글자 다른 이유가 바로 이것이다(설명·label·나머지 alias 4개는 그대로다) — "가능한
한 보존"의 유일한 예외가 이 모호성 제거다.

## 사용 방법

```python
from src.services.service_canonical_major_v2_loader import (
    load_service_canonical_majors_v2,
    load_canonical_major_group_to_service_major_bridge_v2,
)

majors = load_service_canonical_majors_v2()          # 39개(FULL_GROUP 38 + DEPARTMENT_LEVEL_ONLY 1), Fail-Fast
bridge = load_canonical_major_group_to_service_major_bridge_v2()  # 42개, Fail-Fast(hci_ux는 여기 없다)
```

Loader가 로드 시점에 강제하는 것(하나라도 깨지면 즉시 예외):

1. description 공백 금지
2. 별칭 중복 감사(같은 Major 안 중복 + 서로 다른 Major 간 공유 모두 금지)
3. `canonical_major_group_id`(FULL_GROUP)와 `source_group_ids`(DEPARTMENT_LEVEL_ONLY)가
   가리키는 모든 Group ID가 실제 42개 Group 중 하나인지 확인
4. 예체능 4개 Group이 ACTIVE(FULL_GROUP)로 로드되지 않는지 확인 — DEPARTMENT_
   LEVEL_ONLY Major가 `source_group_ids`로 예체능 Group을 참고하는 것은 금지
   대상이 아니다(그 자체가 Group을 승격시키지 않는다)
5. description 금지 표현(적합 보장·취업 보장·점수 표현) 재확인

재생성하려면:

```
PYTHONPATH=. ./.venv/bin/python scripts/career_build_service_canonical_majors_v2.py
```

입력이 전부 정적 정본(Group 42개·기존 10개·소계열 코드표·hci_ux Bridge Draft 2행)
이라 몇 번을 다시 돌려도 byte-identical하다(`GenerationDeterminismTest`가 이를
실제로 확인한다).

## 다음 라운드가 할 일(이번 범위 밖)

- 39개 서비스 Major 각각에 Trait Weight(24-Trait Vector)를 붙이는 작업.
- 전국 학과 Master(`data/master/departments.jsonl`)의 `canonical_major_id`를 이
  체계로 다시 연결하는 작업(department_recommendation_scope.jsonl 재검토 포함).
  hci_ux는 특히 "학과 단위 검토"가 이 재연결 작업의 전제조건이다 — Group
  전체를 자동으로 편입시키면 안 된다(위 hci_ux 절 참고).
- `MajorExplorationService`/`matching_engine_v2`가 이 39개를 실제로 소비하도록
  배선하는 작업 — 이번 라운드는 명시적으로 이 배선을 하지 않는다.
