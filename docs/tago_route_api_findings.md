# TAGO 버스노선정보 서비스(15098529) 분석 리포트

## 1. 개요
- **서비스명**: 국토교통부 (TAGO) 버스노선정보조회 서비스 (`BusRouteInfoInqireService`)
- **데이터셋 ID**: `15098529`
- **기본 Endpoint**: `https://apis.data.go.kr/1613000/BusRouteInfoInqireService`
- **목적**: 대중교통 사각지대 감사(Transport Gap Audit) 파이프라인에서 기본서비스(Basic Service, 첫차 ≤ 06:30, 막차 ≥ 22:00, 배차간격) 판정을 위한 사전 규격 검증 및 API 조사

---

## 2. 오퍼레이션별 상세 명세

### 1) 도시코드 목록조회 (`getCtyCodeList`)
- **엔드포인트 경로**: `/BusRouteInfoInqireService/getCtyCodeList`
- **기능**: 전국 시·군별 도시코드 및 도시명 목록을 조회
- **요청 파라미터**:
  | 파라미터명 | 구분 | 타입 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `serviceKey` | **필수** | String | 공공데이터포털 발급 인증키 (URL-encoded 또는 Decoded) |
  | `_type` | 선택 | String | 응답 데이터 형식 (`json` 또는 `xml`, 기본값 xml) |
  | `pageNo` | 선택 | Integer | 페이지 번호 (기본값 1) |
  | `numOfRows` | 선택 | Integer | 한 페이지 결과 수 (기본값 10) |
- **응답 필드 목록**:
  | 필드명 | 한글 설명 | 타입 | 비고 |
  | :--- | :--- | :--- | :--- |
  | `citycode` | 도시코드 | Number/String | 5자리 행정구역 식별코드 (예: 31240 화성시) |
  | `cityname` | 도시명 | String | 행정구역 명칭 (예: 경기도 화성시) |

---

### 2) 노선번호 목록조회 (`getRouteNoList`)
- **엔드포인트 경로**: `/BusRouteInfoInqireService/getRouteNoList`
- **기능**: 특정 도시코드에 속한 버스 노선 목록을 조회 (노선번호 필터 가능)
- **요청 파라미터**:
  | 파라미터명 | 구분 | 타입 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `serviceKey` | **필수** | String | 공공데이터포털 발급 인증키 |
  | `cityCode` | **필수** | Number | 조회할 지역의 도시코드 (예: 31240) |
  | `routeNo` | 선택 | String | 검색할 노선번호 (생략 시 전체 노선 목록) |
  | `_type` | 선택 | String | 응답 데이터 형식 (`json` / `xml`) |
  | `pageNo` | 선택 | Integer | 페이지 번호 |
  | `numOfRows` | 선택 | Integer | 한 페이지 결과 수 |
- **응답 필드 목록**:
  | 필드명 | 한글 설명 | 타입 | 비고 |
  | :--- | :--- | :--- | :--- |
  | `routeid` | 노선 ID | String | 표준 노선 고유 식별자 (예: GGB200000010) |
  | `routeno` | 노선 번호 | String/Number | 버스 표시 노선번호 (예: 10, 700-2) |
  | `routetp` | 노선 유형 | String | 일반형시내버스, 직행좌석형, 마을버스 등 |
  | `startnodenm` | 기점 정류소명 | String | 노선 기점(출발지) 명칭 |
  | `endnodenm` | 종점 정류소명 | String | 노선 종점(도착지) 명칭 |
  | `startvehicletime` | 기점 첫차시간 | String | 기점 출발 첫차 운행 시각 (HHMM, 옵션 제공) |
  | `endvehicletime` | 기점 막차시간 | String | 기점 출발 막차 운행 시각 (HHMM, 옵션 제공) |

---

### 3) 노선별 경유정류소 목록조회 (`getRouteAcctoThrghSttnList`)
- **엔드포인트 경로**: `/BusRouteInfoInqireService/getRouteAcctoThrghSttnList`
- **기능**: 특정 버스 노선이 정차하는 전체 정류소 목록을 경유 순서대로 조회
- **요청 파라미터**:
  | 파라미터명 | 구분 | 타입 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `serviceKey` | **필수** | String | 공공데이터포털 발급 인증키 |
  | `cityCode` | **필수** | Number | 지역 도시코드 (예: 31240) |
  | `routeId` | **필수** | String | 노선 고유 식별자 (예: GGB200000010) |
  | `_type` | 선택 | String | 응답 데이터 형식 (`json` / `xml`) |
  | `pageNo` | 선택 | Integer | 페이지 번호 |
  | `numOfRows` | 선택 | Integer | 한 페이지 결과 수 |
- **응답 필드 목록**:
  | 필드명 | 한글 설명 | 타입 | 비고 |
  | :--- | :--- | :--- | :--- |
  | `routeid` | 노선 ID | String | 표준 노선 고유 식별자 |
  | `nodeid` | 정류소 ID | String | 표준 정류소 고유 식별자 (예: GGB222001318) |
  | `nodenm` | 정류소 명칭 | String | 버스정류소 명칭 |
  | `nodeno` | 정류소 번호 | String/Number | 정류장 표지판 표기 5자리 단축번호 |
  | `nodeord` | 정류소 순번 | Integer | 해당 노선 내 정류소 정차 순서 (1, 2, 3...) |
  | `gpslati` | 위도 좌표 | Float | 정류소 WGS84 위도 (33~39) |
  | `gpslong` | 경도 좌표 | Float | 정류소 WGS84 경도 (124~132) |
  | `updowncd` | 상하행 구분 | String/Number | 상행(0/기점방향) / 하행(1/종점방향) 구분코드 |

---

### 4) 노선정보항목조회 (`getRouteInfoIem`)
- **엔드포인트 경로**: `/BusRouteInfoInqireService/getRouteInfoIem`
- **기능**: 단일 노선 ID에 대한 종합 운행 스펙(첫차, 막차, 배차간격 등) 상세 조회
- **요청 파라미터**:
  | 파라미터명 | 구분 | 타입 | 설명 |
  | :--- | :--- | :--- | :--- |
  | `serviceKey` | **필수** | String | 공공데이터포털 발급 인증키 |
  | `cityCode` | **필수** | Number | 지역 도시코드 (예: 31240) |
  | `routeId` | **필수** | String | 노선 고유 식별자 (예: GGB200000010) |
  | `_type` | 선택 | String | 응답 데이터 형식 (`json` / `xml`) |
- **응답 필드 목록**:
  | 필드명 | 한글 설명 | 타입 | 비고 |
  | :--- | :--- | :--- | :--- |
  | `routeid` | 노선 ID | String | 표준 노선 고유 식별자 |
  | `routeno` | 노선 번호 | String/Number | 버스 표시 노선번호 |
  | `routetp` | 노선 유형 | String | 일반형시내버스, 직행좌석형, 간선 등 |
  | `startnodenm` | 기점 정류소명 | String | 노선 기점(출발지) 명칭 |
  | `endnodenm` | 종점 정류소명 | String | 노선 종점(도착지) 명칭 |
  | `startvehicletime` | 기점 첫차시간 | String | **기점 출발 첫차 운행 시각 (HHMM, 옵션)** |
  | `endvehicletime` | 기점 막차시간 | String | **기점 출발 막차 운행 시각 (HHMM, 옵션)** |
  | `intervaltime` | 평일 배차간격 | Number | **평일 운행 배차간격 (분 단위, 옵션)** |
  | `intervalsattime` | 토요일 배차간격 | Number | **토요일 운행 배차간격 (분 단위, 옵션)** |
  | `intervalsuntime` | 일요일 배차간격 | Number | **일요일 운행 배차간격 (분 단위, 옵션)** |

---

## 3. 핵심 분석 과제 답변

### Q1. 첫차 시간(first-bus time)과 막차 시간(last-bus time)을 반환하는 오퍼레이션이 있는가?
- **답변**: **존재합니다.**
- **해당 오퍼레이션**:
  1. `getRouteInfoIem` (노선정보항목조회)
  2. `getRouteNoList` (노선번호 목록조회)
- **정확한 필드명**:
  - 첫차 시간: `startvehicletime` (포맷: `HHMM`, 예: `0530` = 05:30)
  - 막차 시간: `endvehicletime` (포맷: `HHMM`, 예: `2300` = 23:00)
- **주의사항 (가이드 12.2 준수)**:
  - 위 두 필드는 지자체 BIS 연계 상황 및 노선 특성(순환버스, 맞춤형 버스 등)에 따라 API 응답에서 생략되거나 빈 문자열(NULL)로 반환될 수 있는 **옵션(`옵`) 항목**입니다.
  - 가이드 12.2 원칙에 따라, **"자료 없으면 충족 판정 금지"** 원칙을 엄격 적용해야 하며, 해당 필드가 누락된 노선에 대해 임의로 "첫차 ≤ 06:30 충족"으로 단정해서는 안 됩니다.

---

### Q2. 배차간격(headway) 필드를 반환하는 오퍼레이션이 있는가?
- **답변**: **존재합니다.**
- **해당 오퍼레이션**:
  - `getRouteInfoIem` (노선정보항목조회)
- **정확한 필드명**:
  - 평일 배차간격: `intervaltime` (단위: 분, Integer)
  - 토요일 배차간격: `intervalsattime` (단위: 분, Integer)
  - 일요일 배차간격: `intervalsuntime` (단위: 분, Integer)
- **비고**:
  - `getRouteNoList`에는 배차간격 필드가 없으며, 오직 노선 단건 상세조회인 `getRouteInfoIem`에서만 반환됩니다.

---

### Q3. 응답에 차량 식별자(차량 번호 등) 필드가 있는가?
- **답변**: **존재하지 않습니다.**
- **사유 및 영향**:
  - `BusRouteInfoInqireService`의 4개 오퍼레이션 및 도착정보(`ArvlInfoInqireService`) 응답에는 차량 고유 등록번호나 차량 식별자(vehicle ID) 필드가 전혀 포함되어 있지 않습니다.
  - 따라서 서로 다른 도착정보 스냅샷 간에 동일 차량의 이동 궤적을 추적하는 것은 원천적으로 불가능하며, 도착 예정 시간(`arrtime`)과 잔여 정류소 수(`arrprevstationcnt`)를 바탕으로 한 헤드웨이 간격 분석만 유효합니다.

---

## 4. 실측 스모크(Smoke Test) 결과 및 현황


### 실측 환경
- **실행 스크립트**: `tools/smoke_tago_route.py`
- **테스트 도시코드**: 화성시 (`31240`)
- **요청 파라미터**: `numOfRows=1`, `pageNo=1`, `_type=json`
- **저장 위치**: `data/raw/tago_route_smoke/`

### 실측 호출 결과 (라이브 실측 완료)
| 오퍼레이션 | HTTP 상태 | 응답 내용 (Header) | 결과 분류 (AGENTS.md 기준) | 반환 데이터 검증 |
| :--- | :--- | :--- | :--- | :--- |
| `getCtyCodeList` | **200 OK** | `00 NORMAL SERVICE.` | **`ok_with_items`** | 전국 도시코드 목록 수신 확인 |
| `getRouteNoList` | **200 OK** | `00 NORMAL SERVICE.` | **`ok_with_items`** | `startvehicletime`("0430"), `endvehicletime`(2300) 반환 확인 |
| `getRouteAcctoThrghSttnList` | **200 OK** | `00 NORMAL SERVICE.` | **`ok_with_items`** | 246개 경유 정류소 순번(`nodeord`), GPS 좌표 수신 확인 |
| `getRouteInfoIem` | **200 OK** | `00 NORMAL SERVICE.` | **`ok_with_items`** | `startvehicletime`("0430"), `endvehicletime`(2300), `intervaltime`(30분), `intervalsattime`(50분), `intervalsuntime`(50분) 반환 확인 |

### 결과 분석 및 확정
1. **API 키 및 엔드포인트 확정**:
   - 사용자가 제공한 일반 인증키(`2c5f...5772`)를 환경변수 `TAGO_SERVICE_KEY`로 설정하여 호출한 결과, **4개 오퍼레이션 전체가 `200 NORMAL SERVICE.` 및 `ok_with_items`로 정상 수신**되었습니다.
   - Endpoint: `https://apis.data.go.kr/1613000/BusRouteInfoInqireService`
2. **실측 반환 필드 검증 (화성시 400번 버스 `GGB200000008`)**:
   - `getRouteInfoIem` 실측 JSON:
     ```json
     {
       "endnodenm": "궁평항",
       "endvehicletime": 2300,
       "intervalsattime": 50,
       "intervalsuntime": 50,
       "intervaltime": 30,
       "routeid": "GGB200000008",
       "routeno": 400,
       "routetp": "일반형시내버스",
       "startnodenm": "광교",
       "startvehicletime": "0430"
     }
     ```
   - `AGENTS.md`에 명시된 "데이터 사실"의 모든 필드(`routeid`, `routeno`, `routetp`, `startnodenm`, `endnodenm`, `startvehicletime`, `endvehicletime`, `intervaltime`, `intervalsattime`, `intervalsuntime`)가 실제 API 응답과 100% 동일함을 실측으로 확인하였습니다.
3. **최소서비스 판정 연계 전략**:
   - 노선별 `startvehicletime`(첫차) 및 `endvehicletime`(막차) 필드가 실제로 정상 제공되므로, 7단계 도착 스냅샷 수집 파이프라인에서 각 경유 노선의 운행 시간대 충족 여부를 프로그래밍 방식으로 판정할 수 있습니다.
   - 다만 일부 노선/지자체에서 해당 값이 누락(NULL)될 경우를 대비하여 가이드 12.2 원칙("자료 없으면 충족 판정 금지")에 따라 결측 시 판정 보류 로직을 유지합니다.

---

## 5. 7A′ 노선정보 검증 및 서비스 시간 Coverage 실측

### 실측 개요
- **대상 정류소**: 남양주시 다산동 정류소 (`citycode=31130`, `nodeid=GGB222001318`)
- **실측 노선 수**: 7C 스모크에서 식별된 12개 고유 노선 (총 12회 호출, Cap 20 준수)
- **산출물**: `data/staged/route_service_hours.parquet` (총 12행)

### 노선별 서비스 시간 실측 Coverage 테이블
| routeid | routeno | start_time | status_start | end_time | status_end | interval (분) | first_bus_ok | last_bus_ok |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GGB222000009` | 9 | `0430` | **present** | `2340` | **present** | 13 | **True** | **True** |
| `GGB222000013` | 23 | `0350` | **present** | `2230` | **present** | 12 | **True** | **True** |
| `GGB222000027` | 97 | `0445` | **present** | `2215` | **present** | 25 | **True** | **True** |
| `GGB222000028` | 165 | `0430` | **present** | `2230` | **present** | 12 | **True** | **True** |
| `GGB222000031` | 65 | `0500` | **present** | `2310` | **present** | 15 | **True** | **True** |
| `GGB222000032` | 1-4 | `0500` | **present** | `2200` | **present** | 20 | **True** | **True** |
| `GGB222000048` | 166-1 | `0520` | **present** | `2330` | **present** | 15 | **True** | **True** |
| `GGB222000078` | 1200 | `0500` | **present** | `2230` | **present** | 15 | **True** | **True** |
| `GGB222000180` | 땡큐12 | `0530` | **present** | `2230` | **present** | 30 | **True** | **True** |
| `GGB222000199` | 땡큐50 | `0525` | **present** | `2200` | **present** | 12 | **True** | **True** |
| `GGB234000003` | 30 | `0400` | **present** | `2225` | **present** | 50 | **True** | **True** |
| `GGB234000028` | 10-5 | `0455` | **present** | `2225` | **present** | 25 | **True** | **True** |

- **요약**:
  - 12개 노선 모두 `startvehicletime`과 `endvehicletime`이 누락 없이 존재(100% Coverage).
  - 12개 노선 모두 `startvehicletime <= '0630'` (03:50~05:30) 및 `endvehicletime >= '2200'` (22:00~23:40) 조건을 충족하여 `first_bus_ok=True`, `last_bus_ok=True` 판정.
  - 시간 필드는 반드시 4자리 zero-padded 문자열(`'0430'`, `'0600'`)로 유지되어 안정적으로 사전순 비교가 가능함을 입증.

