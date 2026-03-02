# 로컬 실행 가이드 (Local Execution Guide)

이 문서는 로컬 환경 및 가상환경에서 `lottery-bot`을 실행하는 방법을 설명합니다.

## 1. 사전 준비

### 환경 변수 설정

프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 아래 내용을 입력합니다. (또는 `.env.local` 파일 확인)

```env
USERNAME=동행복권_아이디
PASSWORD=동행복권_비밀번호
AMOUNT=충전금액 (예: 5000, 10000, 20000, 30000, 50000, 100000, 150000)
ACCOUNT_PASSWORD=간편충전_비밀번호 (숫자 6자리)
OPENROUTER_API_KEY=OpenRouter_API_키 (키패드 이미지 인식용)
HEADLESS=false (로컬 실행 시 브라우저 확인을 위해 false 권장)
```

## 2. 가상환경 설정 및 실행 (권장)

가상환경을 사용하면 시스템 패키지와 충돌 없이 독립적으로 실행할 수 있습니다.

### (1) 가상환경 생성 및 활성화

```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화 (macOS/Linux)
source .venv/bin/activate
```

### (2) 필수 패키지 설치

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### (3) 실행 방법

가상환경이 활성화된 상태에서 아래 명령어를 실행합니다.

```bash
# 방법 A: Makefile 사용 (권장)
make recharge

# 방법 B: Python 직접 실행
python3 controller.py recharge
```

---

## 3. 기타 명령어

- **구매하기**: `make buy` 또는 `python3 controller.py buy`
- **당첨 확인**: `make check` 또는 `python3 controller.py check`
- **가상환경 종료**: `deactivate`
