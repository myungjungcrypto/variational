# 🖥️ 설정 서버 Railway 배포 가이드

설정 서버를 Railway에 배포하는 방법입니다.

## 📋 사전 준비

### 1. GitHub 저장소 확인
- `config_server.py` 파일이 저장소에 있는지 확인
- `.env` 파일은 **절대** 푸시하지 않음

## 🚀 Railway 배포

### 1. Railway 프로젝트 생성

1. [Railway](https://railway.app)에 로그인
2. "New Project" 클릭
3. "Deploy from GitHub repo" 선택
4. **같은 저장소** 선택 (봇과 같은 저장소 사용 가능)

### 2. 배포 설정

Railway는 자동으로 Python 앱을 감지하지만, 명시적으로 설정하려면:

**방법 1: Procfile 사용 (권장)**
- 저장소 루트에 `Procfile.server` 파일이 있음
- Railway 대시보드에서 "Settings" → "Build Command" 설정:
  ```
  (비워두기 - 자동 감지)
  ```
- "Start Command" 설정:
  ```
  python config_server.py
  ```

**방법 2: railway.json 사용**
- Railway가 자동으로 감지

### 3. 환경 변수 설정

Railway 대시보드에서 "Variables" 탭으로 이동:

```
SERVER_TOKEN=your-secret-token-here
PORT=5000  (Railway가 자동 설정하므로 선택사항)
```

**중요:** `SERVER_TOKEN`은 봇의 `CONFIG_SERVER_TOKEN`과 **동일**해야 합니다!

### 4. 배포 확인

1. Railway가 자동으로 배포 시작
2. "Deployments" 탭에서 배포 상태 확인
3. 배포 완료 후 "Settings" → "Domains"에서 URL 확인
   - 예: `https://your-project.up.railway.app`

### 5. 설정 서버 URL 확인

배포 완료 후:
1. "Settings" → "Domains"에서 생성된 URL 확인
2. 또는 "Deployments" → "View Logs"에서 확인:
   ```
   Running on https://your-project.up.railway.app
   ```

## 🔗 봇과 연결

### 봇의 환경 변수 업데이트

봇을 배포할 때 `CONFIG_SERVER_URL`을 설정 서버 URL로 설정:

```
CONFIG_SERVER_URL=https://your-config-server.up.railway.app
CONFIG_SERVER_TOKEN=your-secret-token-here  (설정 서버와 동일)
```

## 🧪 테스트

### 1. 설정 서버 상태 확인

브라우저에서 접속:
```
https://your-config-server.up.railway.app/health
```

정상 응답 예:
```json
{
  "status": "ok",
  "timestamp": "2025-12-09T...",
  "active_sessions": 0
}
```

### 2. 봇에서 연결 테스트

텔레그램 봇에서:
- `/status` 명령어로 연결 상태 확인
- "💓 서버: ✅ 연결됨" 메시지 확인

## ⚙️ 설정 서버 관리

### 설정 업데이트

`config_server.py`의 `API_CONFIG`를 수정하려면:

1. 로컬에서 `config_server.py` 수정
2. GitHub에 푸시
3. Railway가 자동 재배포

또는 Railway 대시보드에서:
- "Settings" → "Variables"에서 환경 변수로 설정 가능하도록 코드 수정 필요

### 로그 확인

- Railway 대시보드 → "Deployments" → "View Logs"
- 실시간 로그 확인 가능

## 🔒 보안

### 토큰 관리
- `SERVER_TOKEN`은 강력한 랜덤 문자열 사용 권장
- 봇과 설정 서버의 토큰이 일치해야 함
- 토큰을 절대 코드에 하드코딩하지 않음

### 접근 제어
- 설정 서버는 인증이 필요하므로 안전
- `/health` 엔드포인트만 공개 (인증 불필요)

## 📊 모니터링

### Railway 대시보드
- **Metrics**: CPU, 메모리 사용량
- **Logs**: 실시간 로그
- **Deployments**: 배포 이력

### 설정 서버 상태
- `/health` 엔드포인트로 상태 확인
- 활성 세션 수 확인 가능

## 🔄 업데이트

코드를 업데이트하려면:

1. 로컬에서 `config_server.py` 수정
2. GitHub에 푸시:
   ```bash
   git add config_server.py
   git commit -m "설정 서버 업데이트"
   git push origin main
   ```
3. Railway가 자동으로 재배포

## ⚠️ 주의사항

1. **포트 설정**: Railway는 `PORT` 환경 변수를 자동 설정
2. **토큰 일치**: 봇과 설정 서버의 토큰이 반드시 일치해야 함
3. **API URL**: `config_server.py`의 `API_CONFIG`에서 실제 API URL 확인 필요

## 💡 팁

- 설정 서버와 봇을 같은 Railway 프로젝트의 서로 다른 서비스로 배포 가능
- 또는 별도 프로젝트로 배포 가능 (권장)
- 무료 플랜 사용 시 슬리프 모드 주의

