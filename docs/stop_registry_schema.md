# 대표 정류소 레지스트리 최종 스키마 명세 (Stop Registry Schema)

## 1. 개요
* **파일 경로**: `evidence/stop_registry.csv`
* **파일 성격**: 인간 검증자가 지도를 확인하고 기입한 대표 정류소 등록 원장
* **관리 방식**: 인간이 `pending` 상태로 행을 생성하고, 게이트(`evaluate`) 통과 후 승격 CLI(`promote`)가 원자적으로 `review_status`를 `human_verified`로 전이시킴 (승격 시 새 행 생성 금지).

---

## 2. 최종 확정 컬럼 스키마 (12개 컬럼, 순서 엄수)

게이트 엔진은 실행 시작 시 `stop_registry.csv`의 헤더가 아래 12개 컬럼과 **순서 및 명칭이 정확히 일치**하는지 검증하며, 불일치 시 즉시 실행을 거부합니다.

| 순번 | 컬럼명 | 데이터 타입 | 필수 여부 | 설명 및 작성 지침 |
| :---: | :--- | :--- | :---: | :--- |
| 1 | `cluster_id` | String | **필수** | 주거 단지 클러스터 ID (예: `A10022364`) |
| 2 | `citycode` | String | **필수** | TAGO 5자리 지자체 도시코드 (예: `31130`) |
| 3 | `nodeid` | String | **필수** | TAGO 정류소 고유 ID (예: `GGB222001318`) |
| 4 | `stop_lat` | Float | **필수** | **사람이 지도(카카오맵/지적도)에서 직접 확인한 WGS84 위도** (TAGO 좌표 복사 금지) |
| 5 | `stop_lon` | Float | **필수** | **사람이 지도(카카오맵/지적도)에서 직접 확인한 WGS84 경도** (TAGO 좌표 복사 금지) |
| 6 | `direction_label` | String | **필수** | **단지 기준 이동 진행 방향 라벨** (공란/NaN 불가, 정류소명 단순 복사 금지) |
| 7 | `coord_verify_method` | String | **필수** | 지도 검증 방법 (화이트리스트 준수, 단어 `auto`/`api`/`자동` 등 포함 불가) |
| 8 | `raw_citycode_response_path` | String | **필수** | 실존하며 해당 citycode가 포함된 원본 도시코드 응답 파일 경로 (예: `evidence/citycode/getCtyCodeList_raw.json`) |
| 9 | `review_status` | String | **필수** | 초기 기입 시 **반드시 `pending`** (promote 시 `human_verified`로 전이) |
| 10 | `verified_by` | String | **필수** | 인간 지도 검증자 성명 (빈값/NaN 불가) |
| 11 | `verified_at` | String | **필수** | 인간 지도 검증 일시 (오프셋 포함 ISO-8601 KST, 미래 시각 불가) |
| 12 | `notes` | String | 선택 | 특이사항 및 현장 메모 (없을 시 빈칸) |

---

## 3. 스키마 설계 결정 사항 및 제외 컬럼 사유

1. **`nodenm` 제외**:
   * 게이트 엔진이 `(citycode, nodeid)` 키로 `data/staged/tago_stops_full.parquet`과 직접 조인하여 정본 정류소명을 가져오므로, 입력 오타를 방지하기 위해 레지스트리 입력에서 제외함.
2. **`cluster_lat`, `cluster_lon` 제외**:
   * 게이트 엔진이 `cluster_id` 키로 `exports/complex_geocode.csv`에서 원 정밀도 좌표(소수점 14자리)를 직접 조인함. 사람이 손으로 4자리 등으로 반올림하여 기입할 때 발생하는 위도 0.0001°당 약 11m의 오차 유입을 원천 차단함.
3. **`coord_delta_m`, `recomputed_dist_m` 제외**:
   * 게이트 엔진이 하버사인 공식으로 `coord_delta_recomputed_m`과 `dist_recomputed_m`을 직접 산출하므로, 외부 입력값을 일절 신뢰하지 않고 수집 입력에서 제거함.
4. **`smoke_outcome`, `smoke_test_at_kst` 제외**:
   * G4 게이트가 `evidence/smoke_log.csv`에서 정본 행을 직접 읽어 요일 및 시간대, 신선도(30일 이내), 유효 item 수를 판정하므로, 원장 간 중복 기입을 배제함.

---

## 4. G3 게이트 정의 및 계산 상수 확정 (P0-D)

* **G3 판정 대상 거리 정의**:
  $$\text{dist\_recomputed\_m} = \text{haversine}(\text{cluster\_lat}, \text{cluster\_lon}, \text{stop\_lat}, \text{stop\_lon}) \le 800.0\text{ m}$$
  * **거리 측정 대상**: 주거 단지 중심 좌표(`complex_geocode.csv` 원 정밀도) $\leftrightarrow$ **사람이 직접 지도에서 계측한 정류소 좌표(`stop_lat`, `stop_lon`)**.
  * G2에서 이미 "사람 계측 좌표 $\leftrightarrow$ TAGO 좌표" 차이가 50m 이내임을 검증하므로, 실제 보행 출발지점과 사람이 확인한 승강장 위치 사이의 거리를 측정하는 것이 현실 보행권 평가에 부합함.
* **지구 반경 상수 고정**:
  * WGS84 평균 지구 반경: $R = 6,371,000.0\text{ m}$ (`src/collectors/geo_const.py`).

---

## 5. `is_blank` 적용 필드 출처별 전수 명세 (P1-5)

결측/공백(`None`, `pd.isna`, `""`, `"nan"`, `"none"`, `"null"`) 검증 헬퍼 `is_blank()`가 적용되는 14개 필드의 출처별 분류:

1. **`[registry]` (stop_registry.csv 입력 컬럼 - 10개 필수 필드)**:
   * `cluster_id`, `citycode`, `nodeid`, `stop_lat`, `stop_lon`, `direction_label`, `coord_verify_method`, `raw_citycode_response_path`, `verified_by`, `verified_at`
   * (참고: `review_status`는 pending 검증에 사용, `notes`는 선택 필드로 결측 시 빈 문자열로 정규화됨)
2. **`[smoke_log]` (evidence/smoke_log.csv 컬럼 - 2개)**:
   * `outcome` (smoke_outcome), `schema_version`
3. **`[parquet]` (data/staged/tago_stops_full.parquet 컬럼 - 2개)**:
   * `gpslati`, `gpslong` (G2 기준 좌표)

---

## 6. 내용 정규화 해시 규칙 및 운영 절차 (P0-F, P1-7)

리포트 생성 시점과 승격 시점 사이의 레지스트리 무결성을 보장하기 위해 SHA-256 해시를 사이드카(`stop_gate_report.meta.json`)에 기록합니다.

* **해시 대상 컬럼 (11개 고정 상수 `REGISTRY_EVAL_COLUMNS`)**:
  `("cluster_id", "citycode", "nodeid", "stop_lat", "stop_lon", "direction_label", "coord_verify_method", "raw_citycode_response_path", "verified_by", "verified_at", "notes")`
  * `review_status`는 `pending` $\rightarrow$ `human_verified` 전이 시 해시 데드락을 방지하기 위해 **해시 대상에서 제외**합니다.
  * `notes`는 사후 변동 감사 무결성을 위해 **해시 대상에 포함**합니다.
* **결정론적 정규화 규칙 (P0-F)**:
  1. **행 정렬**: `(citycode, nodeid)` 오름차순으로 데이터프레임을 정렬한 후 직렬화하여 CSV 내 행 순서 변동에 독립적임.
  2. **결측 정규화**: `is_blank`가 참인 모든 값은 빈 문자열 `""`로 일원화.
  3. **유니코드 NFC 정규화**: `verified_by`, `direction_label`, `notes` 등 한글 필드에 대해 `unicodedata.normalize("NFC", s).strip()`을 적용하여 macOS(NFD)와 Windows(NFC) 입력 간 바이트 차이를 원천 해소.
  4. **좌표 자릿수 고정**: `f"{float(v):.7f}"`로 소수점 7자리 고정 포맷팅.
* **표준 운영 절차 (P1-7)**:
  1. 검증 대상 모든 정류소 행을 `evidence/stop_registry.csv`에 `review_status='pending'`으로 일괄 기입.
  2. 게이트 평가 CLI 1회 실행: `python -m src.verify.stop_gate evaluate` $\rightarrow$ 리포트 및 사이드카 메타 생성.
  3. 통과된 정류소들에 대해 개별 `promote` 연속 실행: `python -m src.verify.stop_gate promote ...` (동일 리포트로 데드락 없이 연속 승격).
  4. **주의**: 승격 도중에 레지스트리에 새로운 `pending` 행을 추가하거나 기존 행을 수정하면 내용 해시가 변경되어 기존 리포트가 stale 처리되므로, 반드시 게이트를 재실행해야 합니다.
