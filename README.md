<img width="1188" height="873" alt="image" src="https://github.com/user-attachments/assets/c66f43a6-996e-4c1e-a986-e01ebcf8a696" />



전 오스티움과 베리나 레버리지 3배씩 하고 위에 셋팅처럼 돌립니다. 참고하세요.

손해가 목표 이익이 높을 수록 안날 확률이 높습니다. 대신에 거래는 자주 일어나지 않아요.

# 🤖 Ostium ↔️ Variational 차익거래 봇

완전 자동화된 암호화폐 차익거래 봇 (중앙 설정 서버 기반)

## ✨ 주요 기능

### 🔐 완전 자동 인증
- Variational 토큰 자동 발급
- 토큰 만료 시 자동 재발급
- 쿠키 수동 복사 불필요

### 🌐 중앙 집중식 API 관리
- 모든 API URL은 서버에서 자동 수신
- 코드 업데이트 불필요
- 관리자가 서버에서 URL 실시간 변경 가능

### ⚡ 극한 최적화
- 초고속 가격 모니터링 (5ms 주기)
- 병렬 실행으로 진입/청산 동시 처리
- 실시간 bid/ask 기반 정확한 PnL 계산

### 🔒 강력한 보안
- API URL 코드에 노출 안됨
- 토큰 기반 인증
- Private Key 로컬 저장만

### 🛡️ 자동 복구
- 네트워크 끊김 자동 재연결
- 토큰 만료 자동 갱신
- 에러 발생 시 자동 재시도

## 📋 요구사항

- Python 3.8 이상
- Ostium 계정 (USDC 잔고 필요)
- Variational 계정 (USDC 잔고 필요)
- 설정 서버 접속 정보 (관리자에게 문의)

## 🚀 빠른 시작

### 1. 설치

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정
```bash
# .env.example을 .env로 복사
cp .env.example .env

# .env 파일 편집
nano .env
```

**필수 입력 항목:**
```bash
# 관리자에게 받은 정보
CONFIG_SERVER_URL=https://bio-rebound-solo-rat.trycloudflare.com
CONFIG_SERVER_TOKEN=your-token-here

# 자신의 지갑 정보
OSTIUM_PRIVATE_KEY=0x...
VARIATIONAL_WALLET_ADDRESS=0x...
VARIATIONAL_PRIVATE_KEY=0x...
```

### 3. 실행
```bash
python trader_with_server.py
```

## ⚙️ 설정 파라미터

| 파라미터 | 설명 | 기본값 | 권장값 |
|---------|------|--------|--------|
| 진입 갭 | 진입 조건 가격차 | $20 | $15-30 |
| 목표 이익 | 청산 목표 수익 | $1 | $1-20 |
| 레버리지 | 포지션 레버리지 | 1x | 1-5x |
| 포지션 크기 | 콜래터럴 금액 | $300 | $200-1500 |

## 🛠️ 유틸리티

### 토큰 수동 생성
```bash
# Variational 토큰 수동 발급
python tokengen.py
```

## ⚠️ 주의사항

1. **Private Key 보안**
   - `.env` 파일을 절대 공유하지 마세요
   - GitHub에 업로드하지 마세요
   - `.gitignore`에 포함되어 있는지 확인하세요

2. **자금 관리**
   - 테스트넷에서 먼저 테스트하세요
   - 감당 가능한 금액만 사용하세요
   - 손실 가능성을 항상 고려하세요

3. **모니터링**
   - 봇 실행 중 주기적으로 확인하세요
   - 비정상 동작 시 즉시 중지하세요
   - 로그를 정기적으로 검토하세요

## 🐛 문제 해결

### 설정 서버 연결 실패
```
❌ 설정 서버에 연결할 수 없습니다
```
**해결:**
1. `CONFIG_SERVER_URL` 확인
2. 서버 실행 여부 확인 (관리자에게 문의)
3. 인터넷 연결 확인

### 토큰 발급 실패
```
❌ 토큰 발급 실패
```
**해결:**
1. `VARIATIONAL_PRIVATE_KEY` 확인
2. `VARIATIONAL_WALLET_ADDRESS` 확인
3. Private Key와 Address 일치 여부 확인

### 거래소 연결 실패
```
❌ Ostium 연결 실패
```
**해결:**
1. `OSTIUM_PRIVATE_KEY` 확인
2. 지갑에 ETH(가스비)와 USDC 확인
3. RPC URL 상태 확인

## 📞 지원

- **설정 관련**: [서버 관리자에게 문의](https://t.me/JUSTCRYT)
- **버그 리포트**: https://t.me/JUSTCRYT
- **기능 제안**: https://t.me/JUSTCRYT

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## ⚖️ 법적 고지

이 소프트웨어는 교육 목적으로 제공됩니다. 실제 거래에서 발생하는 모든 손실에 대한 책임은 사용자에게 있습니다. 사용 전 관련 법규를 확인하세요.

---

**Made with ⚡ by the community**
