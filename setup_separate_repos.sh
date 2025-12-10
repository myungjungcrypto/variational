#!/bin/bash

# 저장소 분리 스크립트
# 사용법: ./setup_separate_repos.sh

set -e

echo "📦 저장소 분리 시작..."
echo ""

# 현재 디렉토리 확인
CURRENT_DIR=$(pwd)
echo "현재 디렉토리: $CURRENT_DIR"
echo ""

# 1. 설정 서버 저장소 생성
echo "1️⃣ 설정 서버 저장소 생성 중..."
CONFIG_SERVER_DIR="../config-server"

if [ -d "$CONFIG_SERVER_DIR" ]; then
    echo "⚠️  $CONFIG_SERVER_DIR 폴더가 이미 존재합니다."
    read -p "덮어쓰시겠습니까? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ 취소되었습니다."
        exit 1
    fi
    rm -rf "$CONFIG_SERVER_DIR"
fi

mkdir -p "$CONFIG_SERVER_DIR"
cd "$CONFIG_SERVER_DIR"

# Git 초기화
git init

# 필요한 파일 복사
cp "$CURRENT_DIR/config_server.py" .
cp "$CURRENT_DIR/.gitignore" .

# requirements.txt 생성 (설정 서버용)
cat > requirements.txt << EOF
flask==2.3.3
flask-cors==6.0.1
python-dotenv==1.2.1
EOF

# Procfile 생성
echo "web: python config_server.py" > Procfile

# railway.json 생성
cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
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
cat > README.md << 'EOF'
# 설정 서버

Railway 배포용 설정 서버입니다.

## 환경 변수

- `SERVER_TOKEN`: 서버 인증 토큰

## 배포

Railway에서 이 저장소를 연결하면 자동으로 배포됩니다.
EOF

# .gitignore 확인/수정
if ! grep -q "config_server.py" .gitignore 2>/dev/null; then
    echo "" >> .gitignore
    echo "# 로컬 설정" >> .gitignore
    echo ".env" >> .gitignore
    echo "__pycache__/" >> .gitignore
    echo "*.pyc" >> .gitignore
fi

echo "✅ 설정 서버 저장소 생성 완료: $CONFIG_SERVER_DIR"
echo ""

# 2. 봇 저장소 준비
cd "$CURRENT_DIR"
echo "2️⃣ 봇 저장소 준비 중..."

# Procfile 확인
if [ ! -f "Procfile" ]; then
    echo "web: python trader_telegram_bot.py" > Procfile
    echo "✅ Procfile 생성됨"
fi

# railway.json 확인
if [ ! -f "railway.json" ]; then
    cat > railway.json << 'EOF'
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python trader_telegram_bot.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
EOF
    echo "✅ railway.json 생성됨"
fi

echo "✅ 봇 저장소 준비 완료"
echo ""

# 3. 안내
echo "=========================================="
echo "✅ 저장소 분리 완료!"
echo "=========================================="
echo ""
echo "다음 단계:"
echo ""
echo "1️⃣ 설정 서버 저장소:"
echo "   cd $CONFIG_SERVER_DIR"
echo "   git add ."
echo "   git commit -m 'Initial commit: Config server'"
echo "   # GitHub에 새 저장소 생성 후:"
echo "   git remote add origin https://github.com/your-username/config-server.git"
echo "   git push -u origin main"
echo ""
echo "2️⃣ 봇 저장소 (현재 폴더):"
echo "   cd $CURRENT_DIR"
echo "   # config_server.py는 제거하거나 .gitignore에 추가"
echo "   git add ."
echo "   git commit -m 'Bot repository setup'"
echo "   # GitHub에 새 저장소 생성 후:"
echo "   git remote set-url origin https://github.com/your-username/arbitrage-bot.git"
echo "   git push -u origin main"
echo ""
echo "3️⃣ Railway 배포:"
echo "   - 설정 서버: config-server 저장소 연결"
echo "   - 봇: arbitrage-bot 저장소 연결"
echo ""

