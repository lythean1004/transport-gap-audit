# 한국 신도시 교통 소외 기간 감사 프로젝트 (Transport-gap Audit)

## 2026년 9월 제출용 감사

최신 논문은 `exports/submission_v1/교통데이터공모전_논문_1차.docx` 및 같은 이름의 PDF다.
상세 검토는 `docs/submission_audit/감사결과.md`를 참고한다. 기존 보고서와 코드 일부는
과거 실행의 보관자료이며 현재 확정 사실로 사용하면 안 된다.

- 활성 사건 180행 중 현재 필수항목 통과 107행, 사람 검증 완료 0행.
- 현재 관측은 1개 정류소, 6일, 정상 JSON 259개, 예측 항목 6,354개다.
- 특정 철도 개통까지의 경과기간과 대중교통 무서비스 기간을 구분한다.
- 실제 배차 준수율, 기본서비스 충족 여부 및 세대·일 노출량은 확정하지 않는다.
- 모의자료 생성기의 출력은 QA 폴더로 분리했다.

재현 명령은 프로젝트 루트에서 실행한다. 분석 명령은 외부 API를 호출하지 않는다.

```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m scripts.submission.analyze
python -m scripts.submission.build_paper
```

논문 DOCX를 Word에서 PDF로 내보낸 뒤 각 페이지를 확인한다. `build_paper.py`의 본문은
검토한 분석 스냅샷의 서술이므로 원자료 변경 후에는 본문 수치와 해석도 검토해야 한다.
원본 자료와 정제된 배포 사본의 차이는 `exports/submission_v1/package_manifest.csv`에 기록한다.
API 키는 커밋하지 않으며 TAGO 수집 시 환경변수 `TAGO_SERVICE_KEY`를 사용한다.
신청서·서명·재학증명서는 연구 패키지에 포함하지 않는다.
원본의 과거 Git 이력에 키 노출이 있어 비공개 원격 저장소에는 정제된 새 이력만 게시한다.
비공개 저장소를 공개 전환하려면 원문별 이용조건을 검토해야 한다.

## 프로젝트 목표
본 프로젝트는 한국 신도시의 대중교통 인프라 도입 지연 실태를 데이터 기반으로 분석하고 시각화하는 것을 목표로 합니다.
두 가지 주요 지표를 측정합니다:
1. 동일한 교통 수단 및 범위에 대한 **교통 약속 이행 지연 기간** (Promise delay)
2. 최초 입주 후 최소 서비스 도입까지의 **서비스 공백 기간 및 이에 노출된 누적 세대-일수** (Minimum-service gap + Exposed household-days)

## 기술 스택 및 환경
* **언어:** Python 3.12
* **데이터 처리:** DuckDB, Parquet, Polars
* **시각화:** Streamlit, PyDeck
* **제약 사항:** Windows 환경, 저사양 랩탑 호환 (GPU 없음), Docker/PostgreSQL/VectorDB 사용 안 함. 모든 시크릿 키는 환경 변수를 통하여 주입.

## 폴더 구조
* `.agents/rules/`: 프로젝트 및 데이터 검증 관련 AI 에이전트 규칙
* `app/`: Streamlit 대시보드 애플리케이션
* `config/`: 환경 설정 및 YAML 파일 (`thresholds.yaml`, `pilots.yaml`)
* `data/`: 로컬 데이터 저장소 (`raw/`, `staged/`, `curated/`, `tmp/`)
* `docs/`: 프로젝트 문서
* `evidence/documents/`: 수집된 원본 증빙 문서 보관 (불변 데이터)
* `exports/`: 최종 출력물 및 리포트 내보내기 경로
* `src/collectors/`: 외부 공공 API 데이터 수집 모듈
* `src/extractors/`: 텍스트 및 데이터 추출, 정규화 모듈
* `src/metrics/`: 지표 계산 및 로직 검증 모듈
* `tests/`: 자동화 단위 및 통합 테스트 코드

## 데이터 규칙
* 수집된 원본 데이터(Raw evidence)는 절대 임의로 수정할 수 없습니다.
* 누락되거나 알 수 없는 데이터(Unknown)는 항상 `NULL`로 처리하며, 절대 `0`으로 치환하지 않습니다.
* 현재 시점의 실시간 대중교통 API 정보로 과거의 역사적 개통일을 추정하지 않으며, 과거 이력은 텍스트 증빙에 의존합니다.
