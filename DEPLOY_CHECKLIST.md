# 🚀 Railway 배포 체크리스트

Railway에 배포하기 전 확인사항입니다.

## ✅ 사전 준비

### 1. 텔레그램 봇 토큰 발급
- [ ] [@BotFather](https://t.me/BotFather)에서 봇 생성
- [ ] 토큰 복사 및 안전하게 보관

### 2. GitHub 저장소 준비
- [ ] 코드가 GitHub에 푸시되어 있는지 확인
- [ ] `.env` 파일은 **절대** 푸시하지 않았는지 확인

### 3. 설정 서버 준비
- [ ] 로컬에서 `config_server.py` 실행 테스트 완료
- [ ] 설정 서버를 Railway에 별도로 배포하거나
- [ ] 로컬 서버를 Cloudflare Tunnel로 외부 노출

## 🔧 Railway 배포 단계

### 1. Railway 프로젝트 생성
- [ ] Railway 계정 생성/로그인
- [ ] "New Project" 클릭
- [ ] "Deploy from GitHub repo" 선택
- [ ] 저장소 선택

### 2. 환경 변수 설정 (Railway 대시보드)

**필수 환경 변수:**
```
CONFIG_SERVER_URL=http://localhost:5001  (또는 외부 서버 URL)
CONFIG_SERVER_TOKEN=your-secret-token-here
OSTIUM_PRIVATE_KEY=0x...
VARIATIONAL_WALLET_ADDRESS=0x...
VARIATIONAL_PRIVATE_KEY=0x...
OSTIUM_RPC_URL=https://your-rpc-url
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

**선택적 환경 변수:**
```
VARIATIONAL_TOKEN=your-token (자동 발급되므로 선택사항)
RPC_URL=https://your-rpc-url (OSTIUM_RPC_URL 대신 사용 가능)
```

### 3. 배포 확인
- [ ] Railway가 자동으로 배포 시작
- [ ] "Deployments" 탭에서 배포 상태 확인
- [ ] "Logs" 탭에서 에러 확인

## 🧪 배포 후 테스트

### 1. 텔레그램 봇 테스트
- [ ] `/start` 명령어로 봇 응답 확인
- [ ] `/status` 명령어로 상태 확인
- [ ] `/settings` 명령어로 설정 메뉴 확인

### 2. 설정 변경 테스트
- [ ] 진입 갭 변경 테스트
- [ ] 목표 이익 변경 테스트
- [ ] 레버리지 변경 테스트
- [ ] 포지션 크기 변경 테스트

### 3. 거래 테스트
- [ ] `/start_trading` 명령어로 차익거래 시작
- [ ] 로그에서 정상 작동 확인
- [ ] `/stop_trading` 명령어로 중지 확인

## ⚠️ 중요 사항

### 보안
- [ ] Private Key를 절대 코드에 하드코딩하지 않음
- [ ] `.env` 파일이 `.gitignore`에 포함되어 있음
- [ ] Railway 환경 변수는 안전하게 보관

### 설정 서버
- [ ] 설정 서버가 Railway에서 접근 가능한지 확인
- [ ] 로컬 서버를 사용하는 경우 Cloudflare Tunnel 사용
- [ ] 또는 설정 서버도 Railway에 별도 배포

### 모니터링
- [ ] Railway 로그를 정기적으로 확인
- [ ] 텔레그램 봇 응답 속도 확인
- [ ] 거래 실행 시 로그 확인

## 🔄 업데이트 방법

1. 로컬에서 코드 수정
2. GitHub에 푸시:
   ```bash
   git add .
   git commit -m "업데이트 내용"
   git push origin main
   ```
3. Railway가 자동으로 재배포

## 📞 문제 해결

### 봇이 응답하지 않음
- Railway 로그 확인
- `TELEGRAM_BOT_TOKEN` 확인
- 봇이 실행 중인지 확인

### 설정 서버 연결 실패
- `CONFIG_SERVER_URL` 확인
- 설정 서버가 실행 중인지 확인
- 네트워크 연결 확인

### 거래가 실행되지 않음
- `/status`로 연결 상태 확인
- 잔고 확인
- 설정값 확인

