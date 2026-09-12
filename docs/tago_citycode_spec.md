# TAGO 도시코드 목록조회 명세 및 대상 5개 지자체 확정 리포트

## 1. 개요
* **서비스명**: 국토교통부 버스노선정보조회 서비스 (`BusRouteInfoInqireService`)
* **오퍼레이션**: `getCtyCodeList` (도시코드 목록 조회)
* **Raw 응답 저장 경로**: `evidence/citycode/getCtyCodeList_raw.json`
* **호출 일시**: 2026-09-03 KST (HTTP 200 수신)

---

## 2. 5개 대상 지자체 공식 Raw 응답 원문 인용

`evidence/citycode/getCtyCodeList_raw.json`의 원본 응답 내 `response.body.items.item` 배열에서 추출한 5개 대상 지자체 항목 원문입니다:

### 1) 성남시 (`31020`)
```json
{
  "citycode": 31020,
  "cityname": "성남시"
}
```

### 2) 남양주시 (`31130`) — 7C 스모크 정류소(`GGB222001318`) 소재지
```json
{
  "citycode": 31130,
  "cityname": "남양주시"
}
```

### 3) 하남시 (`31180`)
```json
{
  "citycode": 31180,
  "cityname": "하남시"
}
```

### 4) 김포시 (`31230`)
```json
{
  "citycode": 31230,
  "cityname": "김포시"
}
```

### 5) 화성시 (`31240`)
```json
{
  "citycode": 31240,
  "cityname": "화성시"
}
```

---

## 3. G1 게이트 연계
* 위 5개 지자체 정류소의 `raw_citycode_response_path`는 디스크에 실존하는 `evidence/citycode/getCtyCodeList_raw.json`을 참조합니다.
* 파케이 및 원본 JSON 응답 모두에 해당 5개 `citycode`가 존재함을 대조 확인하였으므로 G1 탈락 사유가 해소되었습니다.
