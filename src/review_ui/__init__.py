"""V2 Direct Probe 로컬 전용 검수 UI — 2026-08-23 Trait Ontology v2(2.4단계).

`src/api/main.py`(공개 FastAPI App)와 완전히 분리된 개발자용 내부 도구다. 이 패키지는
질문·선택지·Mapping을 "판단"하지 않는다 — 두 사람이 직접 판단할 수 있도록 데이터를
보여주고, 그 판단(TBD/APPROVE/REVISE/HOLD)을 안전하게 저장하는 것만 한다."""
