# 📦 저장소 분리 가이드

설정 서버와 봇을 별도의 GitHub 저장소로 분리하는 방법입니다.

## 🎯 장점

- ✅ Procfile, railway.json 충돌 없음
- ✅ 각 프로젝트 독립 관리
- ✅ 배포 설정이 명확함
- ✅ 유지보수 용이

## 📁 저장소 구조

### 1. 설정 서버 저장소 (`config-server`)

```
config-server/
├── config_server.py
├── requirements.txt
├── Procfile
├── railway.json (선택사항)
├── .gitignore
└── README.md
```

### 2. 봇 저장소 (`arbitrage-bot`)

```
arbitrage-bot/
├── trader_telegram_bot.py
├── trader_with_server.py
├── config_client.py
├── requirements.txt
├── Procfile
├── railway.json (선택사항)
├── .gitignore
└── README.md
```

## 🚀 분리 방법

### 1단계: 설정 서버 저장소 생성

```bash
# 새 폴더 생성
mkdir config-server
cd config-server

# Git 초기화
git init

# 필요한 파일 복사
cp ../config_server.py .
cp ../requirements.txt .
cp ../.gitignore .

# Procfile 생성
echo "web: python config_server.py" > Procfile

# railway.json 생성 (선택사항)
cat > railway.json << EOF
{
  "\$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python config_server.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF

# README.md 생성
cat > README.md << EOF
# 설정 서버

Railway 배포용 설정 서버입니다.

## 환경 변수

- SERVER_TOKEN: 서버 인증 토큰
EOF

# Git 커밋
git add .
git commit -m "Initial commit: Config server"

# GitHub에 새 저장소 생성 후
git remote add origin https://github.com/your-username/config-server.git
git push -u origin main
```

### 2단계: 봇 저장소 생성

```bash
# 원래 폴더에서
cd /Users/myunggeunjung/Ostiational-Bot-main

# 필요한 파일만 포함하는 새 저장소 생성
# (또는 현재 저장소를 봇 전용으로 변경)

# Procfile 확인 (이미 있음)
# railway.json 확인 (이미 있음)

# config_server.py는 제거하거나 .gitignore에 추가
# (봇 저장소에는 필요 없음)

# Git 커밋
git add .
git commit -m "Bot repository setup"

# GitHub에 새 저장소 생성 후
git remote set-url origin https://github.com/your-username/arbitrage-bot.git
git push -u origin main
```

## 🔧 Railway 배포

### 설정 서버 배포

1. Railway → New Project
2. GitHub 저장소: `config-server` 선택
3. 환경 변수:
   ```
   SERVER_TOKEN=your-secret-token-here
   ```
4. 배포 완료 후 URL 확인

### 봇 배포

1. Railway → New Project
2. GitHub 저장소: `arbitrage-bot` 선택
3. 환경 변수:
   ```
   CONFIG_SERVER_URL=https://config-server-xxxx.up.railway.app
   CONFIG_SERVER_TOKEN=your-secret-token-here
   OSTIUM_PRIVATE_KEY=0x...
   VARIATIONAL_WALLET_ADDRESS=0x...
   VARIATIONAL_PRIVATE_KEY=0x...
   OSTIUM_RPC_URL=https://your-rpc-url
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```
4. 배포 완료

## 📝 주의사항

1. **공통 파일**: `requirements.txt`는 각 저장소에 맞게 조정
2. **config_client.py**: 봇 저장소에만 포함
3. **config_server.py**: 설정 서버 저장소에만 포함
4. **.env**: 두 저장소 모두 `.gitignore`에 포함

## 🔄 업데이트 방법

### 설정 서버 업데이트
```bash
cd config-server
# 파일 수정
git add .
git commit -m "Update config server"
git push
# Railway 자동 재배포
```

### 봇 업데이트
```bash
cd arbitrage-bot
# 파일 수정
git add .
git commit -m "Update bot"
git push
# Railway 자동 재배포
```

