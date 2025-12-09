# 🚂 Railway 배포 가이드

이 가이드는 차익거래 봇을 Railway 서버에 배포하는 방법을 설명합니다.

## 📋 사전 준비

### 1. 텔레그램 봇 토큰 발급

1. [@BotFather](https://t.me/BotFather)에게 `/newbot` 명령어 전송
2. 봇 이름과 사용자명 설정
3. 발급받은 토큰을 복사 (예: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. GitHub 저장소 준비

코드를 GitHub에 푸시합니다:

```bash
git add .
git commit -m "텔레그램 봇 버전 추가"
git push origin main
```

## 🚀 Railway 배포

### 1. Railway 계정 생성 및 프로젝트 생성

1. [Railway](https://railway.app)에 가입/로그인
2. "New Project" 클릭
3. "Deploy from GitHub repo" 선택
4. 저장소 선택

### 2. 환경 변수 설정

Railway 대시보드에서 "Variables" 탭으로 이동하여 다음 환경 변수들을 추가합니다:

#### 필수 환경 변수

```
CONFIG_SERVER_URL=https://your-config-server.com
CONFIG_SERVER_TOKEN=your-config-token
OSTIUM_PRIVATE_KEY=0x...
VARIATIONAL_WALLET_ADDRESS=0x...
VARIATIONAL_PRIVATE_KEY=0x...
OSTIUM_RPC_URL=https://your-rpc-url
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

#### 선택적 환경 변수

```
VARIATIONAL_TOKEN=your-variational-token (자동 발급되므로 선택사항)
RPC_URL=https://your-rpc-url (OSTIUM_RPC_URL 대신 사용 가능)
```

### 3. 배포 설정 확인

Railway는 자동으로 다음 파일들을 인식합니다:
- `Procfile`: 실행 명령어 정의
- `railway.json`: 배포 설정 (선택사항)
- `requirements.txt`: Python 패키지 의존성

### 4. 배포 시작

1. Railway가 자동으로 코드를 감지하고 배포를 시작합니다
2. "Deployments" 탭에서 배포 상태를 확인할 수 있습니다
3. 배포가 완료되면 "Logs" 탭에서 로그를 확인할 수 있습니다

## 📱 텔레그램 봇 사용법

### 기본 명령어

- `/start` - 봇 시작 및 도움말
- `/status` - 현재 상태 확인 (연결 상태, 가격, 잔고)
- `/start_trading` - 차익거래 시작
- `/stop_trading` - 차익거래 중지
- `/settings` - 설정 변경 메뉴
- `/balance` - 잔고 확인
- `/positions` - 현재 포지션 확인
- `/close_all` - 모든 포지션 청산
- `/stats` - 거래 통계 확인

### 설정 변경

1. `/settings` 명령어 입력
2. 변경할 항목 선택:
   - 진입 갭: 차익거래 진입 조건 ($)
   - 목표 이익: 청산 목표 수익 ($)
   - 레버리지: 포지션 레버리지 (배)
   - 포지션 크기: 콜래터럴 금액 (USDC)

## 🔍 문제 해결

### 배포 실패

1. **로그 확인**: Railway 대시보드의 "Logs" 탭 확인
2. **환경 변수 확인**: 모든 필수 환경 변수가 설정되었는지 확인
3. **의존성 확인**: `requirements.txt`에 모든 패키지가 포함되어 있는지 확인

### 봇이 응답하지 않음

1. **Railway 로그 확인**: 봇이 정상적으로 실행 중인지 확인
2. **텔레그램 토큰 확인**: `TELEGRAM_BOT_TOKEN`이 올바른지 확인
3. **재배포**: Railway에서 "Redeploy" 버튼 클릭

### 연결 오류

1. **설정 서버 확인**: `CONFIG_SERVER_URL`과 `CONFIG_SERVER_TOKEN` 확인
2. **RPC URL 확인**: `OSTIUM_RPC_URL`이 올바른지 확인
3. **Private Key 확인**: 모든 Private Key가 올바른 형식인지 확인

## 📊 모니터링

### Railway 대시보드

- **Metrics**: CPU, 메모리 사용량 확인
- **Logs**: 실시간 로그 확인
- **Deployments**: 배포 이력 확인

### 텔레그램 명령어

- `/status`: 실시간 상태 확인
- `/stats`: 거래 통계 확인

## 🔄 업데이트

코드를 업데이트하려면:

1. 로컬에서 코드 수정
2. GitHub에 푸시:
   ```bash
   git add .
   git commit -m "업데이트 내용"
   git push origin main
   ```
3. Railway가 자동으로 재배포합니다

## ⚠️ 주의사항

1. **보안**: Private Key를 절대 공개하지 마세요
2. **비용**: Railway 무료 플랜에는 제한이 있습니다
3. **가용성**: Railway 무료 플랜은 일정 시간 비활성 시 슬리프 모드로 전환됩니다
4. **백업**: 중요한 설정은 별도로 백업하세요

## 💡 팁

- Railway Pro 플랜을 사용하면 슬리프 모드 없이 24/7 실행 가능
- 로그를 정기적으로 확인하여 문제를 조기에 발견
- 텔레그램 봇을 통해 원격으로 봇을 제어할 수 있습니다

---

**문제가 발생하면 Railway 로그와 텔레그램 봇 응답을 확인하세요!**

