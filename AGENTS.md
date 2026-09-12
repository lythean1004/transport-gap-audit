# 프로젝트 불변 규칙 (모든 작업에 적용)

## 절대 금지
- 관측 데이터만으로 boolean `basic_service_met`을 산출하지 않는다. (가이드 부록 C; 시간표 공문 등 공식 문서 기반의 이벤트 매핑은 허용하되, 실시간 도착 스냅샷 관측 데이터만으로의 충족 단정은 절대 금지)
- API 응답 필드명을 추측하지 않는다. 근거는 docs/ref/ 의 활용가이드 또는
  포털 상세페이지 표에서 온 것만 쓴다. 근거 없으면 작업을 멈추고 보고한다.
- serviceKey를 코드/커밋/로그에 하드코딩하지 않는다. 반드시 환경변수 TAGO_SERVICE_KEY.
- Windows 예약 작업(스케줄러)을 등록하지 않는다. 명령만 문서화한다.
- 스모크/수집 호출을 임의 확장하지 않는다. 호출 예산 초과 시 즉시 중단.
- 완료 보고에서 '100%', '완벽', '완전' 같은 단정 표현을 쓰지 않는다. 검증된 범위와 미검증 범위를 반드시 구분해 서술한다.
- 게이트 판정 로직(G1~G6, 해시, 헤더 검증 등) 변경 시 GATE_CODE_VERSION을 반드시 승격한다.


## 데이터 사실 (확인 완료, 재조사 불필요)
- 도착정보: apis.data.go.kr/1613000/ArvlInfoInqireService/getSttnAcctoArvlPrearngeInfoList
  필수 cityCode, nodeId / 옵션 pageNo, numOfRows, _type
  응답: nodeid nodenm routeid routeno routetp arrprevstationcnt vehicletp arrtime
  arrtime 단위 = 초. 차량 식별자 필드 없음(스냅샷 간 차량 추적 불가).
- 노선정보: apis.data.go.kr/1613000/BusRouteInfoInqireService/getRouteInfoIem
  필수 cityCode, routeId
  응답: routeid routeno routetp startnodenm endnodenm
        startvehicletime(HHMM,옵) endvehicletime(HHMM,옵)
        intervaltime intervalsattime intervalsuntime(분,옵)
- 개발계정 트래픽 표기: 각 데이터셋 10,000 (기간 단위는 마이페이지에서 확인 필요)

## resultCode 해석 규칙 (코드로 강제)
- resultCode='00' + items 비어있음  -> 'ok_empty' = 지금 운행 중인 버스 없음
- resultCode='00' + items 있음      -> 'ok_with_items'
- 그 외                             -> 'api_error'
'ok_empty'는 정류소가 무효하다는 근거가 될 수 없다. 어떤 게이트도 통과시키지 않지만,
정류소 탈락 사유로도 기록하지 않는다.

## 작업 방식
- Planning Mode. 코드 작성 전 Implementation Plan을 제출하고 승인을 기다린다.
- 테스트를 먼저 작성한 뒤 구현한다. 구현 후 `pytest -q` 를 실행해 스스로 검증한다.
- 산출물 경로는 프롬프트에 명시된 것만 생성한다. 추가 파일은 계획에 먼저 올린다.
