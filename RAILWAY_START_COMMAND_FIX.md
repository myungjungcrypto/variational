# 🔧 Railway Start Command 자동 변경 문제 해결

## ❌ 문제

Railway가 저장소의 `Procfile` 또는 `railway.json`을 자동 감지해서 Start command를 덮어씁니다.

## ✅ 해결 방법

### 방법 1: Railway Settings에서 Override (권장)

1. **설정 서버 프로젝트** → **Settings** 탭
2. **"Deploy"** 섹션 찾기
3. **"Custom Start Command"** 섹션에서:
   - Start command 입력: `python config_server.py`
   - **"Override"** 또는 **"Use Custom Command"** 체크박스 확인
   - 저장

### 방법 2: railway.json 파일 이름 변경

설정 서버 프로젝트에서만 사용할 수 있도록:

1. **설정 서버 프로젝트** → **Settings** → **"Source"**
2. **"Root Directory"** 설정
   - 설정 서버 전용 폴더를 만들거나
   - 또는 Railway에서 직접 Start command override

### 방법 3: Procfile 임시 제거 (비권장)

GitHub에서 `Procfile`을 임시로 제거하고:
- 설정 서버 프로젝트: Start command 직접 설정
- 봇 프로젝트: `Procfile` 다시 추가

## 🎯 가장 확실한 방법

**Railway 대시보드에서:**

1. 설정 서버 프로젝트 선택
2. **Settings** → **"Deploy"** 섹션
3. **"Start Command"** 필드에 직접 입력:
   ```
   python config_server.py
   ```
4. **"Save"** 클릭
5. **"Redeploy"** 클릭

이렇게 하면 `Procfile`이나 `railway.json`을 무시하고 직접 설정한 명령어가 사용됩니다.

## 📝 확인 방법

배포 후 로그에서:
- ✅ `python config_server.py`가 실행되면 성공
- ❌ `python trader_telegram_bot.py`가 실행되면 실패 (다시 설정 필요)

