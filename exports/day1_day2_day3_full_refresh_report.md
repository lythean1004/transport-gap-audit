# 교통 공백 감사 Day 1·2·3 전수 재실행 보고서

**결론: PIVOT(A22)** — 원본 폴더의 PDF 112개(고유 해시 92개)를 모두 추출·매칭했습니다. 추출 실패는 0건이며, 이미지형 PDF 1건은 Windows 한국어 OCR로 처리했습니다.

## Day 1 — 전수 추출·필드 QA

- 통합 레지스트리: 197행
- 목표 이벤트 활성 후보: 180행
- 필수필드 QA 통과: 117행
- human_verified: 0행
- 원문 PDF는 수정하지 않았고 모든 파일의 SHA-256, 페이지 수, 추출 상태, 레지스트리 연결 여부를 기록했습니다.

| 이벤트 유형 | 활성 후보 |
|---|---:|
| occupancy_planned_block | 58 |
| promise_date | 59 |
| basic_service | 14 |
| actual_operation | 34 |
| occupancy_first_actual | 10 |
| occupancy_first_planned | 5 |

## Day 2 — 과거 약속↔이행

| 지구 | 약속 | 실제 운행 | 판정 | 대표 지연일 |
|---|---|---|---|---:|
| 화성 동탄2 | SRC-H003 | SRC-H005 | fulfilled | -92 |
| 김포 한강 | SRC-H010 | SRC-H011 | fulfilled | 271 |
| 위례 | SRC-E1-C05 | — | unfulfilled | — |
| 남양주 다산 | SRC-H022 | SRC-H023 | fulfilled | 588 |
| 하남 미사 | SRC-H028 | SRC-H029 | fulfilled | — |

## 입주–동일 약속시설 운행 공백

| 지구 | 최초 실제 입주 | 동일 시설 운행 | 공백 범위(일) |
|---|---|---|---:|
| 화성 동탄2 | Jan-15 | 2024-03-30 | 3346~3376 |
| 김포 한강 | Jun-11 | 2019-09-28 | 3012~3041 |
| 위례 | Dec-13 | ongoing_as_of_2026-09-02 | 4628~4658 |
| 남양주 다산 | 2018 | 2024-08-10 | 2049~2413 |
| 하남 미사 | Jun-14 | 2020-08-08 | 2231~2260 |

## 전방 모니터링 5곳

| 지구 | 최초 예정 블록 | 교통 약속 | 상태 | 시간관계 |
|---|---|---|---|---|
| 인천 계양 | A2 2026년 12월 | 계양~대장 S-BRT 미정 | unfulfilled | target_date_missing |
| 남양주 왕숙 | A-1 2028년 08월 | 강동하남남양주선 2028 | unfulfilled | overlapping_or_ambiguous_period |
| 하남 교산 | A2 2029년 06월 | 송파하남선 2028 | unfulfilled | promise_before_planned_occupancy |
| 고양 창릉 | A-4 Jan-28 | 고양은평선 미정 | unfulfilled | target_date_missing |
| 부천 대장 | A5 Nov-27 | 계양~대장 S-BRT 미정 | unfulfilled | target_date_missing |

## Day 3 — 엄격 게이트

과거 5곳 모두 FAIL입니다. 전체 PDF 추출 완료는 사람 검증 완료를 의미하지 않으므로, exact excerpt·페이지·노선·날짜를 사람이 확인한 뒤에만 승격합니다.
