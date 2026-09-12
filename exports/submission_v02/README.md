# V02 자료 읽는 순서

1. `교통데이터공모전_논문_V02.pdf` 또는 DOCX: 발표용 연구논문 초안.
2. `facility_document_comparison_v02.csv`: 논문 표·그림에 사용한 원문 재대조 기준 시차.
3. `source_registry_v02.csv`: 사용자 검수대장·최종 보완대장 결합 결과. 검수자·시각·입력 해시 포함.
4. `document_date_checks_v02.csv`: 검수 기록과 원문 날짜의 충돌 및 확인 근거.
5. `review_queue_v02.csv`: 사람 미검수와 검수 후 증거 필드 보완을 구분한 작업 목록.
6. `prediction_proxy_sensitivity_v02.csv`: 기존 3일 선택과 전체 6일·15노선 비교. 실제 차량 배차가 아닌 예측 변화 추정치.
7. `observation_daily.csv`: 정상 빈 응답을 포함한 저장 관측의 재집계.

`facility_gap_v02.csv`는 사용자의 검수 날짜를 그대로 계산한 대조용 표다. 원문 날짜 충돌을 반영한 논문 표와 다를 수 있으므로 단독 인용하지 않는다. 사람 검수 131행은 고유 원문 110개에 연결되며 미검수는 15행이다. 자동 필드 검사 보완 대상은 사람 검수 취소를 뜻하지 않는다.

전수 파일 목록·필드 변경·원문 주석·배차 생성 경로 및 미검증 범위는 `../../docs/submission_audit_v02/감사결과_V02.md`에 있다. 원본과 배포 사본 차이는 `package_manifest_v02.csv`를 참고한다.
