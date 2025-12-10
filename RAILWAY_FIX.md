# 🔧 Railway 배포 문제 해결

## ❌ 문제

Build command에 `python config_server.py`를 넣으면 안 됩니다!
- Build command는 **빌드 시**에만 실행됩니다
- Start command가 **실제 서버 실행** 명령어입니다

## ✅ 해결 방법

### 설정 서버 프로젝트

1. **Railway 대시보드** → 프로젝트 선택
2. **Settings** 탭 클릭
3. **"Start Command"** 섹션 찾기
4. 다음 중 하나 선택:

**방법 1: Start Command 직접 입력**
```
python config_server.py
```

**방법 2: Procfile 사용**
- 프로젝트 루트에 `Procfile` 파일 생성 (이미 있음)
- 내용: `web: python config_server.py`
- Railway가 자동으로 인식

### 봇 프로젝트

1. **Railway 대시보드** → 봇 프로젝트 선택
2. **Settings** → **"Start Command"**
3. 입력:
```
python trader_telegram_bot.py
```

## 📝 정리

### 설정 서버 프로젝트
- **Build Command**: (비워두기 또는 기본값)
- **Start Command**: `python config_server.py`
- **환경 변수**: `SERVER_TOKEN=your-token`

### 봇 프로젝트
- **Build Command**: (비워두기 또는 기본값)
- **Start Command**: `python trader_telegram_bot.py`
- **환경 변수**: 모든 봇 관련 변수들

## 🚨 중요

- **Build Command ≠ Start Command**
- Build: 패키지 설치 등 빌드 작업
- Start: 실제 서버 실행

## 🔄 재배포

설정 변경 후:
1. "Deployments" 탭에서 "Redeploy" 클릭
2. 또는 코드를 다시 푸시하면 자동 재배포

