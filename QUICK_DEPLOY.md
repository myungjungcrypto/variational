# ⚡ 빠른 배포 가이드

Railway에 설정 서버와 봇을 빠르게 배포하는 방법입니다.

## 📝 배포 순서

### 1단계: 설정 서버 배포

1. **Railway 프로젝트 1 생성**
   - Railway → "New Project"
   - "Deploy from GitHub repo" 선택
   - 저장소 선택

2. **환경 변수 설정**
   ```
   SERVER_TOKEN=your-secret-token-here
   ```
   ⚠️ 이 토큰을 복사해두세요!

3. **배포 확인**
   - 배포 완료 후 "Settings" → "Domains"에서 URL 확인
   - 예: `https://config-server-xxxx.up.railway.app`
   - 브라우저에서 `/health` 접속하여 테스트

### 2단계: 봇 배포

1. **Railway 프로젝트 2 생성** (새 프로젝트)
   - Railway → "New Project"
   - "Deploy from GitHub repo" 선택
   - **같은 저장소** 선택

2. **환경 변수 설정**
   ```
   CONFIG_SERVER_URL=https://config-server-xxxx.up.railway.app
   CONFIG_SERVER_TOKEN=your-secret-token-here  (1단계에서 복사한 토큰!)
   OSTIUM_PRIVATE_KEY=0x...
   VARIATIONAL_WALLET_ADDRESS=0x...
   VARIATIONAL_PRIVATE_KEY=0x...
   OSTIUM_RPC_URL=https://your-rpc-url
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

3. **배포 확인**
   - 배포 완료 후 로그 확인
   - 텔레그램에서 `/start` 명령어로 테스트

## ✅ 배포 확인 체크리스트

### 설정 서버
- [ ] Railway에서 배포 완료
- [ ] `/health` 엔드포인트 접속 가능
- [ ] URL 확인 완료

### 봇
- [ ] Railway에서 배포 완료
- [ ] 텔레그램 봇 응답 확인
- [ ] `/status` 명령어로 연결 상태 확인
- [ ] "💓 서버: ✅ 연결됨" 메시지 확인

## 🔧 문제 해결

### 설정 서버 연결 실패
- `CONFIG_SERVER_URL`이 올바른지 확인
- `CONFIG_SERVER_TOKEN`이 설정 서버와 일치하는지 확인
- 설정 서버 로그 확인

### 봇이 응답하지 않음
- `TELEGRAM_BOT_TOKEN` 확인
- Railway 로그 확인
- 봇이 실행 중인지 확인

## 📱 텔레그램 봇 사용

배포 완료 후 텔레그램에서:

```
/start - 봇 시작
/settings - 설정 변경
/start_trading - 차익거래 시작
```

자세한 사용법은 `RAILWAY_DEPLOY.md` 참고!

