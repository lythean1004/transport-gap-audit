# 검토 원장 (Review Ledger)

이 문서는 프로젝트 진행 중 제기된 모든 검토 지적사항(P0, P1, P2, E1~E3 등)의 이력, 조치 내용, 근거 파일 및 검증 방법을 소급 및 추적 관리하는 공식 원장입니다.

---

## 1. 지적사항 및 조치 현황 요약 표

| ID | 구분 | 지적 내용 | 상태 | 근거 파일 | 검증/확인 방법 |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **REV-001** | P0 | 첫 줄 예외 메시지 미표시 원인 규명 | **RESOLVED** | `tests/test_stop_gate.py` | `--tb=long` 및 115자 터미널 폭 줄바꿈 실측 확인 |
| **REV-002** | P0 | 경계값 within 순수 함수 분리 및 좌표 여유 마진 적용 | **RESOLVED** | `src/verify/stop_gate.py` | `test_threshold_is_inclusive` (4건 통과) |
| **REV-003** | P0 | Reason Enum 상수 도입 및 리터럴 배제 | **RESOLVED** | `src/verify/reasons.py` | `ALLOWED` frozenset 및 멤버십 단정 |
| **REV-004** | P0 | smoke_log v2 스키마 및 원장 보존 (v1 복구 + v2 append) | **RESOLVED** | `evidence/smoke_log.csv` | raw JSON 24건 실측 대조, v1 결측 유지 + v2 추가 |
| **REV-005** | P1 | G1/G2 누락 테스트 및 GateResult 계약 검사 | **RESOLVED** | `tests/test_stop_gate.py` | `test_g1_citycode_missing`, `test_gate_result_contract` |
| **REV-006** | P1 | 전역 네트워크 차단 및 conftest allow_network 마커 | **RESOLVED** | `conftest.py` | socket 3종 차단 및 `@pytest.mark.allow_network` opt-out |
| **REV-007** | P1 | getSttnNoList 스펙 및 8,420건 전수 수집 완결성 검증 | **RESOLVED** | `docs/tago_bus_stop_api_spec.md` | 파케이 5개 지자체 건수와 API totalCount 전수 일치 대조 |
| **REV-008** | P2 | 완료 보고에서 100%·완벽 등 단정 표현 금지 (보고 시점 규율) | **OPEN** | `AGENTS.md` | 완료 보고 시 [검증된 범위]/[미검증 범위] 섹션 강제화 적용 중 |
| **REV-009** | P0 | G5 순환 모순 해소 및 candidates/registry 분리 | **RESOLVED** | `src/verify/stop_gate.py` | `evaluate_gate`는 pending 행만 평가, promote는 in-place 전이 |
| **REV-010** | P0 | G6 direction_label NaN 부동소수점 truthy 우회 버그 차단 | **RESOLVED** | `src/verify/stop_gate.py` | `is_blank()` 도입 및 `test_direction_label_empty_or_none_or_nan` |
| **REV-011** | P0 | 구버전 후보 리포트 아카이브 및 0행 리포트 정상화 | **RESOLVED** | `exports/archive/` | 구 리포트 격리 및 레지스트리 부재 시 0행 리포트 생성 확인 |
| **REV-012** | P0 | smoke_log 다중 행 정본 선택 규칙 및 순서 독립성 보장 | **RESOLVED** | `src/verify/stop_gate.py` | `select_authoritative_smoke_row` (행 순서 뒤집기 테스트 통과) |
| **REV-013** | P0 | 도시코드 원본 응답 확보 및 5개 지자체 공식 매핑 확정 | **RESOLVED** | `evidence/citycode/` | `getCtyCodeList_raw.json` 저장 및 원문 인용 |
| **REV-014** | P1 | INPUT_NOT_PENDING 분리 및 미평가 gates None 보장 | **RESOLVED** | `src/verify/stop_gate.py` | `test_evaluate_gate_rejects_non_pending_status` |
| **REV-015** | P1 | promote 임시파일+os.replace 원자적 교체 및 이력 로그 | **RESOLVED** | `evidence/promotion_log.csv` | 원자적 치환 및 append-only 승격 이력 기록 검증 |
| **REV-016** | P1 | 7D 수집기 착수 가드 명시 (human_verified 1건 이상 필수) | **RESOLVED** | `src/verify/stop_gate.py` | `check_7d_preconditions` 및 차단 단위 테스트 |
| **REV-017** | P0 | 리포트 메타데이터 사이드카 분리 (`stop_gate_report.meta.json`) | **RESOLVED** | `exports/stop_gate_report.meta.json` | 0행 리포트 상태 사이드카 생성 및 promote 검증 |
| **REV-018** | P0 | promote stale 판정 mtime 데드락 해소 $\rightarrow$ 내용 정규화 해시 도입 | **RESOLVED** | `src/verify/stop_gate.py` | `compute_registry_content_hash` (연속 승격 성공 및 수정 거부) |
| **REV-019** | P0 | 레지스트리 양식에서 stop_lat/lon TAGO 값 제시 삭제 | **RESOLVED** | `docs/stop_registry_schema.md` | 사람 직접 계측 지침 명시, 복사 유도 제거 |
| **REV-020** | P0 | 레지스트리 양식에서 cluster_lat/lon, nodenm, 유도값 제거 | **RESOLVED** | `docs/stop_registry_schema.md` | 게이트 자동 조인 컬럼 배제, 손반올림 오차 원천 방지 |
| **REV-021** | P0 | 레지스트리 최종 스키마 확정 및 헤더 검증 도입 | **RESOLVED** | `docs/stop_registry_schema.md` | `stop_gate.py` 헤더 대조 거부 로직 및 단위 테스트 |
| **REV-022** | P0 | 파일럿 클러스터 A10022364 좌표 불변 수치 증명 보완 | **RESOLVED** | `exports/complex_geocode.csv` | `check_hyphens.py` 실측: 말미 하이픈 0건 단정 |
| **REV-023** | P1 | promote gate_code_version 및 no_registry 센티널 거부 | **RESOLVED** | `src/verify/stop_gate.py` | 버전 불일치 거부 및 센티널 해시 거부 단위 테스트 |
| **REV-024** | P1 | G5 auto/api 검사 토큰 정확일치로 개선 | **RESOLVED** | `src/verify/stop_gate.py` | regex 토큰 분리 및 rapid_transit_map_check 오탐 방지 테스트 |
| **REV-025** | P1 | 해시 대상 컬럼(REGISTRY_EVAL_COLUMNS) 상수 고정 및 notes 포함 결정 | **RESOLVED** | `src/verify/stop_gate.py` | 11개 튜플 상수화 및 schema 문서 반영 |
| **REV-026** | P1 | is_blank 적용 필드 14개 전수 열거 및 출처별 명세 | **RESOLVED** | `docs/stop_registry_schema.md` | 14개 필드 출처별 분류 및 `test_g1_raw_file_missing_fails` |
| **REV-027** | P1 | run_gate_on_candidates 폐기 함수 완전 삭제 | **RESOLVED** | `src/verify/stop_gate.py` | 코드에서 완전 제거 |
| **REV-028** | E1 | 정류소 기입 양식 간소화 개정 제시 | **RESOLVED** | `docs/stop_registry_schema.md` | 최종 12개 컬럼 양식 제시 완료 |
| **REV-029** | P0 | addr_query 말미 하이픈 4건 제거 및 endswith('-').sum() == 0 단정 | **RESOLVED** | `exports/complex_geocode.csv` | `scratch/check_hyphens.py` 실행: 하이픈 0건 실측 단정 |
| **REV-030** | P0 | centroid 규칙(spread > 300m $\rightarrow$ 대표 지번 좌표): 7건 처리 | **OPEN** | `exports/complex_geocode.csv` | 6B 후속 지오코딩 정제 대기 |
| **REV-031** | P1 | dong_final 레벨 매핑 정리 + vw_level*_raw 원본 필드 보존 | **DEFER** | `src/collectors/geocode_complexes.py` | 지오코더 파이프라인 리팩토링 단계로 연기 |
| **REV-032** | P1 | fallback_road 행의 ROAD 별칭 검사 자동 규칙 | **DEFER** | `src/collectors/geocode_complexes.py` | 6C 전처리 단계로 연기 |
| **REV-033** | P1 | VWorld 좌표 30일 캐시/재배포 라이선스 판단 (TTL 이슈) | **DEFER** | `docs/licensing.md` | 6C 착수 전 법무/라이선스 가이드 확정 |
| **REV-034** | P0 | needs_review 6건과 manual_overrides.csv 반영 | **OPEN** | `exports/manual_overrides.csv` | 수동 리뷰 대장 작성 대기 |
| **REV-035** | P1 | 건수 정합(5A 289 $\rightarrow$ 6B 274 클러스터) 감소 사유 코드화 | **DEFER** | `qa/6B_geocode_summary.md` | 6C 보고서 통합 단계로 연기 |
| **REV-036** | P0 | partial_parcels 모듈 미실행 — 강제 실패 유닛 테스트 | **OPEN** | `tests/test_geocode_once.py` | 단위 테스트 작성 대기 |
| **REV-037** | P1 | timetable_effective_date 테스트와 AGENTS.md 규칙 양립 여부 판정 | **RESOLVED** | `tests/test_full_pdf_refresh.py` | 관측 데이터가 아닌 시간표 공문 문서 매핑이므로 양립 확정 |
| **REV-038** | P1 | html2text 의존성 미설치 상태 정식 해결 | **OPEN** | `tests/test_evidence_verifier.py` | importorskip 격리 완료, requirements.txt 추가 및 정식 설치 대기 |
| **REV-039** | P1 | building_hub 테스트 모킹 의도 명시 및 비-dict 응답 케이스 보강 | **OPEN** | `tests/test_building_hub.py` | json.side_effect=ValueError 의도 명시 및 단위 테스트 추가 대기 |
| **REV-040** | P1 | SettingWithCopyWarning 3건 근본 해결 | **OPEN** | `src/evidence_registry.py` | df.loc[:, col] 인덱서 적용으로 판다스 복사본 경고 해소 대기 |
| **REV-041** | P1 | redact_sensitive_url 정규식 상수 단일화 + 파라미터화 테스트 | **OPEN** | `src/config.py` | RedactingFormatter 정규식 패턴 모듈 상수 일원화 대기 |
| **REV-042** | P0 | G3 조인 유일 경로 강제, G3_CLUSTER_AMBIGUOUS/INVALID_CRS 추가 | **RESOLVED** | `src/verify/stop_gate.py` | complexes_df 필수 인자화, crs 가드, 다중 매칭 방어 및 단위 테스트 통과 |

---

## 2. 현재 상태 요약
* **전체 등록 지적 건수**: 42건
* **RESOLVED 항목 건수**: **30건**
* **OPEN 항목 건수**: **8건** (REV-008, REV-030, REV-034, REV-036, REV-038, REV-039, REV-040, REV-041)
* **DEFER 항목 건수**: **4건** (REV-031, REV-032, REV-033, REV-035)
* **산수 검증**: 30 (RESOLVED) + 8 (OPEN) + 4 (DEFER) = 42건 (완전 일치)
