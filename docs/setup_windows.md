# Windows 설정 가이드 (Setup Windows)

이 프로젝트는 Windows 랩탑(GPU 미지원) 환경에서 실행되도록 설계되었습니다. 아래의 PowerShell 명령어를 통해 환경을 구성할 수 있습니다.

## 1. 가상 환경 생성 및 활성화
```powershell
# Python 3.12를 사용하여 가상 환경 생성
python -m venv .venv

# 가상 환경 활성화
.\.venv\Scripts\Activate.ps1
```

## 2. 의존성 설치
```powershell
# pip 업그레이드
python -m pip install --upgrade pip

# 프로젝트 종속성 설치 (pyproject.toml 기반)
pip install -e .

# 선택적 AI 패키지 설치가 필요한 경우
pip install -e .[ai]
```

## 3. 환경 변수 설정
.env 파일을 생성하고 필요한 시크릿 키를 기입합니다.
```powershell
# .env.example을 복사하여 .env 파일 생성
Copy-Item .env.example .env
```
생성된 `.env` 파일을 메모장 등으로 열어 시크릿 키를 안전하게 입력하십시오.

## 4. 설치 확인 및 구문 검사
```powershell
# 문법 검사 (Syntax Check)
python -m py_compile src/config.py src/logging_utils.py

# 단위 테스트 실행
pytest tests/
```
