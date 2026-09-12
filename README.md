<div align="center">

# 🚉 Transport Gap Audit
### 신도시 입주와 교통시설 공급의 시차에 대한 증거 기반 감사

**AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전 (2026)**
_(재)숲과나눔 풀씨행동연구소 · 한겨레신문 공동주최_

_공식 원문 날짜 · 사람 검수 계보 · 도착예정정보 재현을 결합한 다중 검증 프레임_

![status](https://img.shields.io/badge/status-V02%20submission-blue)
![python](https://img.shields.io/badge/python-3.12%2B-3776AB?logo=python&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-green)
![reproducible](https://img.shields.io/badge/reproducible-deterministic-brightgreen)
![data](https://img.shields.io/badge/data-public%20only-lightgrey)

</div>

---

## 📌 한 줄 요약 (TL;DR)

> **“신도시 광역교통 지연”을 하나의 숫자가 아니라, 원문·사람 검수·재현 세 개의 계보(Triple Provenance)의 교집합으로 산출한다.**
> 결과, 김포 한강은 2018년 목표 대비 **271–635일 지연**, 동탄2 GTX-A는 **−92 ~ +89일 범위**, 하남 미사 하남선은 **정시 개통(0일)** 으로 산정된다.

---

## 🧭 목차

- [1. 연구 배경 및 동기](#1-연구-배경-및-동기)
- [2. 핵심 결과 요약](#2-핵심-결과-요약)
- [3. 데이터셋](#3-데이터셋)
- [4. 방법론](#4-방법론)
- [5. 저장소 구조](#5-저장소-구조)
- [6. 재현 절차 (Reproducibility)](#6-재현-절차-reproducibility)
- [7. 산출 파일 안내](#7-산출-파일-안내)
- [8. AI 기술 활용](#8-ai-기술-활용)
- [9. 정책 제안](#9-정책-제안)
- [10. 한계 및 사용 시 주의](#10-한계-및-사용-시-주의)
- [11. 라이선스 · 인용 · 문의](#11-라이선스--인용--문의)

---

## 1. 연구 배경 및 동기

연구자의 처제는 **경기도 파주 운정지구**에 거주한다. 초기에는 운전이 익숙하지 않아 영등포에 사는 언니를 만나러 오는 것이 사실상 어려웠고, 결과적으로 가족의 방문 부담이 한쪽으로 이전되었다. 이 일상적 관찰이 프로젝트의 출발점이다.

신도시 광역교통망은 언제나 **“언제까지 무엇을 하겠다”는 계획의 언어**로 반복 발표된다. 그러나 실제 실행이 지연되거나 공백이 발생하는 동안, 그 비용은 자가용·가족 픽업·시간 손실이라는 형태로 **입주민 개인에게 사적으로 청구**된다.

본 저장소는 이 사적 청구서를 정량화하기 위한 프로젝트다. 단, **“피해 규모를 크게 확정하는 것”이 아니라, 원문·검수·재현이 어긋나지 않는 계산 가능한 최소한의 진술을 유지하는 것**을 목적으로 한다. 그 절제(節制)가 오히려 정책 활용 가능성을 넓힌다.

> 📄 논문 V02 PDF (7쪽): [교통데이터공모전_논문_V02.pdf](./exports/submission_v02/교통데이터공모전_논문_V02.pdf)
> 📝 논문 V02 Word: [교통데이터공모전_논문_V02.docx](./exports/submission_v02/교통데이터공모전_논문_V02.docx)

---

## 2. 핵심 결과 요약

### 2.1 발표 기준일 대비 개통 시차

| 지구 | 대표 시설 | 입주개시 근거(원문) | 실제 개통일 | 발표기준 격차 | 목표 대비 |
|---|---|---|---|---:|---:|
| 화성 동탄2 | GTX-A 수서–동탄 | 2015-01-30 | 2024-03-30 | **3,347일** | −92 ~ +89일 |
| 김포 한강 | 김포골드라인 | 2011-06 (월 단위) | 2019-09-28 | **3,012 ~ 3,041일** | **+271 ~ +635일 지연** |
| 하남 미사 | 하남선(5호선 연장) | 2014-06-30 | 2020-08-08 | **2,231일** | **0일 (정시)** |
| 위례 | 위례선 트램 | 2013-12 | _보류 (실제 개통 원문 미연결)_ | — | — |
| 남양주 다산 | 별내선(8호선 연장) | 2018년 | _보류 (준공/운행 사건 혼동)_ | — | — |

### 2.2 TAGO 도착예정정보 관측 요약

| 항목 | 값 |
|---|---:|
| 관측 기간 | 2026-09-04 ~ 2026-09-11 (6일) |
| 관측 정류소 | 1개소 |
| 관측 노선 | 15개 |
| 명목 5분 슬롯 | 288개 |
| 성공 응답 | **259개 (89.9%)** |
| 도착예정 항목 | **6,354개** |
| 예측 리셋 간격 중앙값 | **20분** (표본 확장에도 안정) |

### 2.3 사람 검수 계보

| 상태 | 행 수 |
|---|---:|
| human_verified | **131** |
| rejected | 37 |
| needs_human | 15 |
| duplicate | 14 |
| **전체 사건 레지스트리** | **197** |

---

## 3. 데이터셋

모든 자료는 원문 해시(SHA-256)와 함께 저장되어 파일 수준의 동일성을 보장한다. 배포본(V02)은 **추가 API 호출 없이** 저장된 자료만으로 재현되며, 인증키·개인 행정서류는 배포본에서 제외된다.

| # | 활용 데이터 | 제공기관 | 플랫폼 | 선정 이유 |
|---|---|---|---|---|
| 1 | 신도시 입주·개통 관련 보도자료·공식 문서 (HWP·PDF) | 국토교통부, LH, 김포시, 하남시, 대광위 | 각 기관 홈페이지 | 지연 산정의 원문 앵커 확보 |
| 2 | 버스 도착정보(TAGO) 도착예정정보 API | 국토교통부·한국교통안전공단 | [data.go.kr](https://www.data.go.kr) | 신도시 정류소 서비스 수준 실측 |
| 3 | 공동주택 단지 정보·건축물대장 | 국토교통부 | data.go.kr / [세움터](https://cloud.eais.go.kr) | 입주 시점 근접(proxy) 및 대조 |
| 4 | 도로명주소·좌표 지오코딩 | 행정안전부 | [juso.go.kr](https://juso.go.kr) | 단지·정류소·시설 공간 정합 |
| 5 | 사용자 검수대장 (Human Review Ledger) | 본 연구팀 (시민과학) | 내부 저장소 | 모델 판독의 사람 반증 |

**규모 스냅샷** — 원문 파일 112개(고유 해시 92개), 사건 레지스트리 197행, 사람 검수 131행, 도착정보 저장 응답 259개(항목 6,354개), 공동주택 21,690행 / 건축물 4,067행 / TAGO 정류소 8,420행.

---

## 4. 방법론

### 4.1 3중 계보(Triple Provenance) 프레임

“지연”을 **세 개의 독립된 검증층의 교집합**으로 정의한다. 어떤 한 층의 오류도 최종 결론을 좌우하지 못하도록 하는 구조적 방어책이다.

```
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│  ①  사람 검수층        │   │  ②  원문층             │   │  ③  재현층             │
│  (Human Review)       │   │  (Source Anchor)       │   │  (Reproducibility)     │
├───────────────────────┤   ├───────────────────────┤   ├───────────────────────┤
│  검수자·검수시각        │   │  파일 SHA-256          │   │  결정론적 재실행        │
│  인용문·페이지 번호     │   │  exact_excerpt 정합    │   │  결측 표현 통일         │
│  candidate_registry   │   │  document_date_checks │   │  scripts/submission   │
└───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
            │                           │                           │
            └───────────────────────────┼───────────────────────────┘
                                        ▼
                        ⨂  세 층의 교집합만 지표에 반영
```

### 4.2 날짜 산술: 구간–구간 차이 (Interval Arithmetic)

“상반기”·“연내”와 같은 원문의 정밀도 손실을 임의의 특정 일자로 정밀화하지 않는다.

$$
I = [I_{lo}, I_{hi}], \quad O = [O_{lo}, O_{hi}]
$$
$$
\text{Gap} = [\, O_{lo} - I_{hi},\ \  O_{hi} - I_{lo}\,]
$$

- **연 단위 목표** → `[YYYY-01-01, YYYY-12-31]`
- **반기 목표** → `[YYYY-01-01, YYYY-06-30]` 또는 `[YYYY-07-01, YYYY-12-31]`
- **월 단위 목표** → `[YYYY-MM-01, YYYY-MM-말일]`

### 4.3 도착정보 재집계와 배차 프록시

TAGO 응답의 예측값 변화 간격을 **“도착예정 리셋 간격(prediction reset proxy)”** 으로 산출한다. **실측 배차 아님**을 반복 명시하며, 정상 빈 응답(`resultCode=00`, items 없음)은 정류소 무효가 아니라 **“해당 시점에 접근 중인 차량이 없음”** 으로만 해석한다.

---

## 5. 저장소 구조

```
.
├── README.md                              # 본 파일
├── AGENTS.md                              # 에이전트·AI 협업 규약
├── pyproject.toml / requirements.txt       # Python 환경
├── .env.example                            # 인증키 템플릿 (실키 미포함)
│
├── scripts/
│   └── submission/                        # V02 분석 파이프라인 (재현용)
│       ├── run_v02.py                     # 저장 자료 기반 V02 통합 재집계
│       ├── review_v02.py                  # 사람 검수 결합·증거 필드 검사
│       ├── claims_v02.py                  # 원문 날짜 대조·시차 계산
│       ├── replay_v02.py                  # 기존 배차 프록시 재현·민감도 분석
│       ├── windows_v02.py                 # AM/PM 수집 원장·로그·원자료 대조
│       ├── build_paper_v02.py             # 그림·논문 DOCX 생성
│       ├── inventory_v02.py               # 원 작업환경 파일 감사
│       └── release_v02.py                 # 원 작업환경 배포 사본·ZIP 생성
│
├── data/
│   ├── raw/                               # 배포 검사 후 포함된 원자료
│   └── source_registry_verified_final_resolution.csv
│
├── evidence/
│   ├── candidate_registry.csv             # 197행 사건 후보
│   ├── arrival_raw/                       # 실제 수집한 도착예정 API JSON
│   ├── arrival_ledger.csv                 # 수집 요청 원장
│   └── evidence_hash_map.csv              # SHA-256 매핑
│
├── exports/
│   └── submission_v02/                    # 논문·보고서에 인용된 최종 산출물
│       ├── facility_document_comparison_v02.csv
│       ├── facility_gap_v02.csv
│       ├── document_date_checks_v02.csv
│       ├── promise_comparison_v02.csv
│       ├── forward_monitoring_v02.csv
│       ├── prediction_proxy_all_days_v02.csv
│       ├── prediction_proxy_sensitivity_v02.csv
│       ├── observation_daily.csv
│       ├── review_summary_v02.json
│       ├── analysis_summary_v02.json
│       ├── actual_collection_windows_v02.csv
│       ├── actual_collection_files_v02.csv
│       ├── figure_1_document_intervals_v02.png
│       ├── figure_2_coverage_v02.png
│       ├── 교통데이터공모전_논문_V02.pdf    # 논문 PDF (7쪽)
│       └── 교통데이터공모전_논문_V02.docx   # 논문 DOCX
│
├── docs/
│   └── submission_audit_v02/              # 전수 파일 목록·필드 변경·원문 주석
│       ├── 감사결과_V02.md
│       └── pytest_final.txt
│
├── scratch/
│   └── calc_headway_v7.py                 # 배차 추정 원본 (감사 목적 보존)
│
├── src/collectors/arrival_snapshot.py      # 실제 수집 모듈
└── tests/                                 # pytest 스위트
```

---

## 6. 재현 절차 (Reproducibility)

### 6.1 환경 준비

```bash
# 저장소 클론
git clone https://github.com/lythean1004/transport-gap-audit.git
cd transport-gap-audit

# Python 3.12 이상 (pyproject.toml 기준)
python -m venv .venv
source .venv/bin/activate

# 의존성 설치
python -m pip install -r requirements.txt
# HWP 원문 처리 의존성 (현재 requirements.txt에 별도 기재되지 않음)
python -m pip install olefile
```

Windows PowerShell에서는 활성화 명령으로 `.\.venv\Scripts\Activate.ps1`을 사용한다. V02 저장 자료 재현에는 API 인증키가 필요하지 않다. 저장소가 비공개이면 접근 권한이 있는 GitHub 계정으로 클론해야 한다.

### 6.2 V02 결과 재현 (권장, 오프라인)

```bash
# 1) 원문·검수 결합, 날짜 대조, 배차 프록시 및 수집 원장 재집계
python -m scripts.submission.run_v02

# 2) 그림과 논문 DOCX 생성
python -m scripts.submission.build_paper_v02

# 3) 테스트
python -m pytest -q
```

저장소 루트에서 실행한다. 결과는 `exports/submission_v02/`와 `docs/submission_audit_v02/`에 기록되고, 중간 집계는 `qa/submission_v02/recomputed_v01_schema/`에 생성된다. `run_v02`는 `review_v02`, `claims_v02`, `replay_v02`, `windows_v02`를 순서대로 호출한다.

논문 생성 스크립트는 DOCX와 PNG를 생성한다. PDF는 DOCX를 Word 등의 PDF 내보내기로 별도 변환한 결과이며 자동 갱신되지 않는다. 논문 본문은 V02 검토 시점의 서술을 포함하므로 입력 자료가 바뀌면 수치와 서술을 함께 재검토해야 한다. `inventory_v02`와 `release_v02`는 외부 참조 폴더·배포 작업폴더를 사용하는 감사 도구로, 위 오프라인 재집계의 필수 실행 단계가 아니다.

### 6.3 최초 관측 재실행 (선택)

실제 수집 모듈은 `src.collectors.arrival_snapshot`이다. 기존 배치 참조파일은 [run_arrival_snapshot.bat](./docs/submission_audit_v02/batch_reference/run_arrival_snapshot.bat)에 보관되어 있다. 참조파일의 로컬 Python·프로젝트 경로는 원 수집환경 값이므로 다른 환경에서는 그대로 실행하지 않는다.

```bash
# 지원 옵션 확인 (API 호출 없음)
python -m src.collectors.arrival_snapshot --help

# 가상 실행 (HTTP 호출 및 파일 쓰기 없음)
python -m src.collectors.arrival_snapshot --dry-run --obs-date 2026-09-07 --slot 0700 --no-sweep
```

새로운 실제 수집은 `TAGO_SERVICE_KEY` 환경변수, 대상 정류소, 관측 날짜·슬롯, 호출 예산을 확인한 뒤 별도로 수행한다. 단일 명령이 오전·오후 전체 기간을 자동 예약하지 않으며 Windows 예약 작업은 등록하지 않는다.

> 인증키는 저장소에 커밋하지 않는다. `.gitignore`에 `.env` 제외 규칙이 있지만 이것만으로 모든 비밀정보를 차단하지는 않는다. V02 배포 검사 기록은 [release_validation_v02.json](./exports/submission_v02/release_validation_v02.json)에 있다. `git-secrets` 훅 설치는 전제하지 않는다.

---

## 7. 산출 파일 안내

| 파일 | 규모 | 논문·보고서 대응 위치 |
|---|---:|---|
| [facility_document_comparison_v02.csv](./exports/submission_v02/facility_document_comparison_v02.csv) | 5행 | §5.1 표 3 (원문 재대조 시차) |
| [facility_gap_v02.csv](./exports/submission_v02/facility_gap_v02.csv) | 5행 | §5.1 대조용 표 (검수 날짜 기준) |
| [document_date_checks_v02.csv](./exports/submission_v02/document_date_checks_v02.csv) | 3행 | §5.1 그림 1 · 원문 충돌 근거 |
| [promise_comparison_v02.csv](./exports/submission_v02/promise_comparison_v02.csv) | 10행 | §5.1 “목표 대비 차이” |
| [forward_monitoring_v02.csv](./exports/submission_v02/forward_monitoring_v02.csv) | 5행 | §5.4 전방 모니터링 |
| [prediction_proxy_all_days_v02.csv](./exports/submission_v02/prediction_proxy_all_days_v02.csv) | 170행 | §5.3 노선·일자별 리셋 간격 |
| [prediction_proxy_sensitivity_v02.csv](./exports/submission_v02/prediction_proxy_sensitivity_v02.csv) | 8행 | §5.3 표 4 민감도 |
| [observation_daily.csv](./exports/submission_v02/observation_daily.csv) | 6행 | §5.3 그림 2 (일별 슬롯 상태) |
| [review_summary_v02.json](./exports/submission_v02/review_summary_v02.json) | — | §5.2 검수 요약 |
| [analysis_summary_v02.json](./exports/submission_v02/analysis_summary_v02.json) | — | §2 전체 규모 |

> `facility_gap_v02.csv`는 **사용자의 검수 날짜를 그대로 계산한 대조용 표**다. 원문 날짜 충돌을 반영한 `facility_document_comparison_v02.csv`와 다를 수 있으므로 **단독 인용하지 말 것**.

---

## 8. AI 기술 활용

AI는 **결론의 판단자가 아니라 대량 원문 판독·코드 재구성의 조력자**로만 사용했다. 모든 AI 산출물은 사람 검수 이력(검수자·시각·원문 해시)과 짝지어 저장했다.

| 도구 | 활용 범위 | 주요 프롬프트 유형 |
|---|---|---|
| **OpenAI Codex (로컬 CLI)** | 원문 추출 스크립트, 배차 재현 코드, 정합성 검증 코드 | “HWP 원문에서 입주개시일·배포일·준공목표일을 사건 유형별로 라벨링해 CSV로 반환하되, `exact_excerpt`에 원문 문구를 그대로 보존.” |
| **LLM 다중 호출 요약** | 사건 유형 분류(입주·약속·준공·개통), 인용문 후보 제안 | “문단에서 promise_date / plan_confirmation / actual_operation 중 어느 사건인지 라벨링하고, 판단 근거 문장을 그대로 인용.” |
| **Vision 판독** | 교통망도 이미지의 정류소·노선 후보 추출 | “교통망도에서 확인 가능한 버스·철도 노선명을 후보 목록으로만 반환.” |

- **AI가 만든 것**: 197행 사건 후보
- **최종 지표에 반영된 것**: 사람 검수를 통과한 **131행**

---

## 9. 정책 제안

1. **교통 약속 레지스트리(Transit Commitment Registry) 신설** — 대상 시설·구간·수단 / 목표일의 정밀도 / 약속의 판본과 해시 / 사업승인·준공목표·개통을 **독립 사건**으로 등록.
2. **기본서비스 최소 요건(Minimum Service Floor)** — 입주 초기 대체수단의 노선 존재만이 아니라 공식 시간표·운영 개시 공지·배차간격까지 함께 제출·검증.
3. **BIS 공표 규격 정비** — 도착예정 리셋 간격이 배차간격으로 오독되지 않도록 API 응답에 시간표 배차와 실측 통과 이벤트를 분리 필드로 제공.
4. **지연 산정 표준화** — 지연을 단일 값이 아닌 **구간**으로, 원문 정밀도와 사건 유형을 병기해 보고.
5. **시민과학 검수 창구 상시화** — 시민이 원문 해시와 인용문을 제출하면 정부 지표에 반영되는 공식 감사대장 채널 개설.

---

## 10. 한계 및 사용 시 주의

- 관측 정류소는 **1개소**, 관측 기간은 **6일**이다. 차량 식별자가 없으므로 도착예측 갱신 간격을 실측 배차로 보고하지 **않는다**.
- 건축물 사용승인일은 실제 전입일이 아니며, 행정동 세대수는 사업지구 경계와 일치하지 않는다. 따라서 “누적 피해 세대·일”과 인과효과는 산출하지 않았다.
- 위례·다산은 원문 재대조에서 사건 혼동 가능성이 남아 지연 비교를 보류했다.
- 본 판본은 **2026-09-12 이후의 이행 여부**를 주장하지 않는다.
- 파일명에 “최종”이 있다는 이유만으로 값을 채택하지 않는다.

---

## 11. 라이선스 · 인용 · 문의

### 라이선스

- **코드**: MIT로 표기되어 있으나, 현재 저장소에는 별도 `LICENSE` 파일이 포함되어 있지 않다.
- **문서·분석 결과물**: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- **원문 데이터**: 각 원출처의 이용조건을 따른다. 본 저장소는 해시·인용문만 재배포하며 원문 재배포는 별도 확인이 필요하다.

### 인용

```bibtex
@techreport{park2026transportgapaudit,
  author       = {Park, Do-hyun},
  title        = {신도시 입주와 교통시설 공급의 시차에 대한 증거 기반 감사:
                  공식 원문 날짜, 사람 검수 계보, 도착예정정보 재현을 결합한 다중 검증 프레임},
  institution  = {AI와 함께하는 교통문제 해결을 위한 데이터 분석 공모전
                  ((재)숲과나눔 · 한겨레신문)},
  year         = {2026},
  month        = {9},
  version      = {V02},
  url          = {https://github.com/lythean1004/transport-gap-audit}
}
```

### 감사의 말

- **(재)숲과나눔 풀씨행동연구소**, **한겨레신문** — 공모전 개최 및 시민과학 데이터 활용 지원
- **국토교통부·LH·김포시·하남시·대광위** — 공식 원문 자료
- **공공데이터포털(TAGO, 건축물대장, 공동주택)**, **행정안전부 도로명주소 안내시스템** — 오픈 데이터 제공
- 그리고, 이 프로젝트의 출발점이 되어 준 **파주 운정지구의 가족**에게.

### 문의

- Issue / PR 환영합니다.
- 원문 재대조·검수 오류 제보는 `evidence/` 폴더의 CSV 스키마를 따라 PR을 열어 주세요.

---

<div align="center">
<sub>V02 · 2026-09-12 · Transport Gap Audit</sub><br/>
<sub>“지연은 숫자가 아니라, 계보다.”</sub>
</div>
