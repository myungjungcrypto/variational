"""
설정 클라이언트 V3.1 (핑퐁 메커니즘 + 자동 갱신)
- 주기적으로 서버에 핑 전송
- 서버 응답 없으면 자동 종료
- 거래 실행 전 검증
- 설정 버전 자동 감지 및 갱신
"""

import requests
import os
import time
import threading
import sys
from datetime import datetime

class ConfigClient:
    def __init__(self, server_url, token):
        self.server_url = server_url.rstrip('/')
        self.token = token
        self.session_id = None
        self.config = None
        self.is_alive = True
        self.heartbeat_interval = 60
        self.last_ping_time = 0
        self.ping_count = 0
        self.shutdown_callbacks = []
        self.config_version = 0  # 현재 설정 버전
        self.on_config_update = None  # 설정 업데이트 콜백

        # 핑퐁 스레드
        self.heartbeat_thread = None
        self.heartbeat_running = False

    def add_shutdown_callback(self, callback):
        """종료 시 실행할 콜백 등록"""
        self.shutdown_callbacks.append(callback)

    def _execute_shutdown(self, reason="Unknown"):
        """강제 종료 실행"""
        print(f"\n{'='*70}")
        print(f"❌ 봇 강제 종료")
        print(f"{'='*70}")
        print(f"사유: {reason}")
        print(f"시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")

        # 등록된 콜백 실행
        for callback in self.shutdown_callbacks:
            try:
                callback()
            except:
                pass

        # 강제 종료
        time.sleep(2)
        os._exit(1)

    def load_config(self):
        """초기 설정 로드"""
        try:
            response = requests.get(
                f"{self.server_url}/config",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                self.config = data.get('config')
                self.session_id = data.get('session_id')
                self.config_version = self.config.get('config_version', 0)

                # 하트비트 설정
                heartbeat_config = self.config.get('heartbeat', {})
                self.heartbeat_interval = heartbeat_config.get('interval_seconds', 60)

                print(f"✅ 설정 로드 완료!")
                print(f"   세션 ID: {self.session_id[:16]}...")
                print(f"   설정 버전: v{self.config_version}")
                print(f"   하트비트: {self.heartbeat_interval}초마다")

                # 하트비트 시작
                if heartbeat_config.get('required', True):
                    self.start_heartbeat()

                return self.config
            else:
                print(f"❌ 설정 로드 실패: {response.status_code}")
                return None

        except Exception as e:
            print(f"❌ 서버 연결 실패: {e}")
            return None

    def _reload_config(self):
        """설정 자동 갱신"""
        try:
            response = requests.get(
                f"{self.server_url}/config",
                headers={"Authorization": f"Bearer {self.token}"},
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                new_config = data.get('config')
                new_version = new_config.get('config_version', 0)

                old_version = self.config_version
                self.config = new_config
                self.config_version = new_version

                print(f"✅ 설정 갱신! v{old_version} → v{new_version}")
                print(f"   업데이트: {new_config.get('last_updated')}")

                # 콜백 실행 (봇에서 전역 변수 업데이트)
                if self.on_config_update:
                    self.on_config_update(new_config)
                    print(f"   📡 봇 설정 자동 적용 완료!")

                return True
            else:
                print(f"⚠️ 설정 갱신 실패: {response.status_code}")
                return False

        except Exception as e:
            print(f"⚠️ 설정 갱신 에러: {e}")
            return False

    def start_heartbeat(self):
        """하트비트 시작"""
        if self.heartbeat_running:
            return

        self.heartbeat_running = True
        self.heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=False  # 데몬이 아님 - 명시적으로 관리
        )
        self.heartbeat_thread.start()
        print(f"💓 하트비트 시작!")

    def _heartbeat_loop(self):
        """하트비트 루프 (백그라운드)"""
        consecutive_failures = 0
        max_failures = 3

        while self.heartbeat_running and self.is_alive:
            try:
                # 인터벌 대기
                time.sleep(self.heartbeat_interval)

                # 핑 전송
                response = requests.post(
                    f"{self.server_url}/ping",
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json"
                    },
                    json={"session_id": self.session_id},
                    timeout=10
                )

                if response.status_code == 200:
                    data = response.json()

                    if data.get('alive'):
                        self.last_ping_time = time.time()
                        self.ping_count += 1
                        consecutive_failures = 0

                        # 🔄 설정 버전 체크
                        server_version = data.get('config_version', 0)
                        if server_version > self.config_version:
                            print(f"🔄 새 설정 감지! v{self.config_version} → v{server_version}")
                            self._reload_config()

                        if self.ping_count % 5 == 0:  # 5번마다 출력
                            print(f"💓 하트비트 #{self.ping_count} - 정상 (v{self.config_version})")
                    else:
                        print(f"⚠️ 서버가 alive=False 응답")
                        consecutive_failures += 1

                elif response.status_code in [401, 403]:
                    print(f"❌ 인증 실패 또는 세션 만료")
                    self._execute_shutdown("서버 인증 실패")
                    break

                else:
                    print(f"⚠️ 핑 실패: {response.status_code}")
                    consecutive_failures += 1

            except Exception as e:
                print(f"⚠️ 하트비트 에러: {e}")
                consecutive_failures += 1

            # 연속 실패 체크
            if consecutive_failures >= max_failures:
                print(f"❌ 하트비트 {max_failures}회 연속 실패!")
                self._execute_shutdown(f"서버 연결 끊김 ({max_failures}회 실패)")
                break

        print(f"💓 하트비트 종료")

    def verify_before_trade(self):
        """
        거래 실행 전 검증 (필수)
        이 함수를 통과하지 못하면 거래 불가
        """
        try:
            response = requests.post(
                f"{self.server_url}/verify",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json"
                },
                json={"session_id": self.session_id},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()

                if data.get('verified'):
                    return True
                else:
                    print(f"❌ 거래 검증 실패: {data.get('error')}")
                    if data.get('action') == 'restart':
                        self._execute_shutdown("세션 만료 - 재시작 필요")
                    return False

            elif response.status_code in [401, 403]:
                print(f"❌ 거래 검증 - 인증 실패")
                self._execute_shutdown("거래 검증 실패")
                return False

            else:
                print(f"⚠️ 거래 검증 실패: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ 거래 검증 에러: {e}")
            return False

    def stop_heartbeat(self):
        """하트비트 중지"""
        self.heartbeat_running = False
        if self.heartbeat_thread:
            self.heartbeat_thread.join(timeout=5)

    def shutdown(self):
        """정상 종료"""
        print(f"\n🛑 클라이언트 종료 중...")
        self.is_alive = False
        self.stop_heartbeat()


# 전역 클라이언트 인스턴스
_config_client = None

def get_config_client():
    """클라이언트 인스턴스 반환"""
    return _config_client

def load_api_config():
    """설정 로드 (메인 함수)"""
    global _config_client

    server_url = os.getenv('CONFIG_SERVER_URL')
    token = os.getenv('CONFIG_SERVER_TOKEN')

    if not server_url or not token:
        raise Exception(
            "❌ CONFIG_SERVER_URL 또는 CONFIG_SERVER_TOKEN이 .env에 없습니다!\n"
            "   .env 파일에 다음을 추가하세요:\n"
            "   CONFIG_SERVER_URL=http://서버주소:5000\n"
            "   CONFIG_SERVER_TOKEN=발급받은토큰"
        )

    print(f"\n📡 설정 서버 연결 중...")
    print(f"   URL: {server_url}")

    _config_client = ConfigClient(server_url, token)
    config = _config_client.load_config()

    if not config:
        raise Exception("❌ 설정 로드 실패! 서버 상태를 확인하세요.")

    return config


if __name__ == '__main__':
    # 테스트
    from dotenv import load_dotenv
    load_dotenv()

    try:
        print("\n" + "="*60)
        print("🧪 설정 클라이언트 테스트")
        print("="*60)

        config = load_api_config()

        print("\n📋 설정 로드 완료:")
        print(f"  버전: {config.get('version', 'unknown')}")
        print(f"  설정 버전: v{config.get('config_version', 0)}")
        print(f"  Ostium: ✅")
        print(f"  Variational: ✅")

        print("\n💓 하트비트 테스트 중... (30초)")
        time.sleep(30)

        client = get_config_client()
        print(f"\n📊 통계:")
        print(f"  핑 횟수: {client.ping_count}")
        print(f"  설정 버전: v{client.config_version}")

        print("\n✅ 테스트 성공!")
        print("="*60 + "\n")

        client.shutdown()

    except KeyboardInterrupt:
        print("\n\n⏹️  사용자가 테스트를 중지했습니다.")
        if _config_client:
            _config_client.shutdown()

    except Exception as e:
        print(f"\n❌ 에러: {e}\n")
        if _config_client:
            _config_client.shutdown()
