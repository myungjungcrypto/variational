# 🖥️ 설정 서버 구축 가이드

이 가이드는 로컬에서 설정 서버를 실행하는 방법을 설명합니다.

## 📋 사전 준비

### 1. 의존성 설치

```bash
pip install flask flask-cors
```

또는 전체 requirements.txt 설치:

```bash
pip install -r requirements.txt
```

## 🚀 서버 실행

### 방법 1: 직접 실행

```bash
python config_server.py
```

### 방법 2: 환경 변수 설정 후 실행

`.env` 파일에 토큰 설정 (선택사항):

```bash
SERVER_TOKEN=your-secret-token-here
PORT=5000
```

그 다음 실행:

```bash
python config_server.py
```

## ⚙️ 설정 변경

`config_server.py` 파일에서 API URL을 실제 값으로 변경하세요:

```python
API_CONFIG = {
    "ostium": {
        "price_api_url": "https://실제-ostium-api-url.com/v1/price"
    },
    "variational": {
        "base_url": "https://omni.variational.io",  # 이미 올바른 URL
        "endpoints": {
            # ... endpoints
        },
        "ws": {
            "portfolio": "wss://omni.variational.io/ws/portfolio",
            "price": "wss://omni.variational.io/ws/price"
        }
    }
}
```

## 🔐 토큰 설정

1. `config_server.py`에서 `SERVER_TOKEN` 변경
2. 또는 환경 변수로 설정: `export SERVER_TOKEN=your-token`
3. 봇의 `.env` 파일에 같은 토큰 설정:
   ```
   CONFIG_SERVER_TOKEN=your-token
   ```

## 📡 API 엔드포인트

### 1. `/config` (GET)
- 설정 조회
- 헤더: `Authorization: Bearer {token}`
- 응답: `{config: {...}, session_id: "..."}`

### 2. `/ping` (POST)
- 하트비트
- 헤더: `Authorization: Bearer {token}`
- Body: `{session_id: "..."}`
- 응답: `{alive: true, config_version: 1}`

### 3. `/verify` (POST)
- 거래 검증
- 헤더: `Authorization: Bearer {token}`
- Body: `{session_id: "..."}`
- 응답: `{verified: true}`

### 4. `/health` (GET)
- 서버 상태 확인 (인증 불필요)
- 응답: `{status: "ok", active_sessions: 0}`

## 🌐 외부 접근 (Cloudflare Tunnel)

로컬 서버를 외부에서 접근하려면:

### Cloudflare Tunnel 사용

```bash
# Cloudflare Tunnel 설치
# https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/

# 터널 실행
cloudflared tunnel --url http://localhost:5000
```

터널 URL을 `.env`에 설정:
```
CONFIG_SERVER_URL=https://your-tunnel-url.trycloudflare.com
```

## 🔧 문제 해결

### 포트가 이미 사용 중
```bash
# 다른 포트 사용
PORT=5001 python config_server.py
```

### 토큰 불일치
- 서버와 클라이언트의 토큰이 일치하는지 확인
- `.env` 파일의 `CONFIG_SERVER_TOKEN` 확인

### API URL 오류
- `config_server.py`의 `API_CONFIG`에서 실제 API URL 확인
- Ostium 가격 API URL이 올바른지 확인

## 📝 참고사항

- 기본 포트: `5000`
- 기본 토큰: `your-secret-token-here` (변경 권장)
- 세션은 메모리에 저장됨 (서버 재시작 시 초기화)
- 실제 운영 환경에서는 데이터베이스 사용 권장

