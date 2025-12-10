# arbitrage_bot_v3.py
# tkinter는 GUI 버전에서만 필요 (서버 환경에서는 선택적)
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
    HAS_TKINTER = True
except ImportError:
    # 서버 환경에서는 tkinter가 없을 수 있음 (텔레그램 봇 등)
    HAS_TKINTER = False
    # 더미 객체 생성 (GUI 클래스는 사용되지 않음)
    tk = None
    ttk = None
    messagebox = None
    scrolledtext = None

from curl_cffi import requests
import json
import threading
import time
from datetime import datetime
import websocket
import ssl
import asyncio
from ostium_python_sdk import OstiumSDK, NetworkConfig
from web3 import Account
from eth_account.messages import encode_defunct
import os
import sys
from dotenv import load_dotenv
from decimal import Decimal, ROUND_DOWN
from queue import Queue
from config_client import load_api_config, get_config_client

load_dotenv()

# 🌐 전역 API 설정
API_CONFIG = None

def validate_environment():
    """🔍 환경 변수 검증"""
    errors = []
    warnings = []

    required_vars = {
        'CONFIG_SERVER_URL': '설정 서버 URL',
        'CONFIG_SERVER_TOKEN': '설정 서버 토큰',
        'OSTIUM_PRIVATE_KEY': 'Ostium Private Key',
        'VARIATIONAL_WALLET_ADDRESS': 'Variational 지갑 주소',
        'VARIATIONAL_PRIVATE_KEY': 'Variational Private Key'
    }

    for var, description in required_vars.items():
        value = os.getenv(var)
        if not value or value.strip() == '':
            errors.append(f"❌ {description} ({var})이(가) 설정되지 않았습니다")

    ostium_key = os.getenv('OSTIUM_PRIVATE_KEY', '')
    if ostium_key:
        if not ostium_key.startswith('0x'):
            ostium_key = '0x' + ostium_key
        if len(ostium_key) != 66:
            errors.append(f"❌ OSTIUM_PRIVATE_KEY 길이가 올바르지 않습니다 (64자여야 함, 현재: {len(ostium_key)-2})")

    var_key = os.getenv('VARIATIONAL_PRIVATE_KEY', '')
    if var_key:
        if not var_key.startswith('0x'):
            var_key = '0x' + var_key
        if len(var_key) != 66:
            errors.append(f"❌ VARIATIONAL_PRIVATE_KEY 길이가 올바르지 않습니다 (64자여야 함, 현재: {len(var_key)-2})")

    wallet = os.getenv('VARIATIONAL_WALLET_ADDRESS', '')
    if wallet:
        if not wallet.startswith('0x'):
            warnings.append(f"⚠️  VARIATIONAL_WALLET_ADDRESS가 0x로 시작하지 않습니다")
        if len(wallet.replace('0x', '')) != 40:
            errors.append(f"❌ VARIATIONAL_WALLET_ADDRESS 길이가 올바르지 않습니다 (40자여야 함)")

    rpc_url = os.getenv('OSTIUM_RPC_URL') or os.getenv('RPC_URL')
    if not rpc_url:
        errors.append(f"❌ OSTIUM_RPC_URL 또는 RPC_URL이 설정되지 않았습니다")

    return errors, warnings


def _server_alive_check():
    """⚡ 서버 연결 상태 체크 (숨겨진 함수)"""
    client = get_config_client()
    if client and hasattr(client, 'is_alive'):
        return client.is_alive
    return False


class OstiumClient:
    """Ostium 거래소 클라이언트"""
    def __init__(self, private_key, rpc_url, use_mainnet=True):
        global API_CONFIG

        self.private_key = private_key
        self.rpc_url = rpc_url
        self.use_mainnet = use_mainnet
        self.address = Account.from_key(private_key).address

        self.session = requests.Session(impersonate="chrome124")

        if API_CONFIG is None:
            raise Exception("❌ API 설정이 로드되지 않았습니다!")

        self.price_api_url = API_CONFIG['ostium']['price_api_url']

        self.cached_price = 0
        self.cached_bid = 0
        self.cached_ask = 0
        self.last_price_update = 0

    def _get_fresh_sdk(self):
        """⚡ 매번 새로운 SDK 인스턴스 생성"""
        # 숨겨진 검증
        if not _server_alive_check():
            raise Exception("Connection lost")

        config = NetworkConfig.mainnet() if self.use_mainnet else NetworkConfig.testnet()
        return OstiumSDK(config, self.private_key, self.rpc_url)

    def get_price_rest_api(self):
        """⚡ 최신 가격 조회"""
        try:
            response = self.session.get(
                f"{self.price_api_url}?asset=BTCUSD",
                headers={'Content-Type': 'application/json'},
                timeout=1,
                verify=False
            )

            if response.status_code == 200:
                data = response.json()

                if isinstance(data, dict) and 'bid' in data and 'ask' in data:
                    self.cached_bid = float(data['bid'])
                    self.cached_ask = float(data['ask'])
                    self.cached_price = float(data.get('mid', (self.cached_bid + self.cached_ask) / 2))
                    self.last_price_update = time.time()
                    return {
                        'bid': self.cached_bid,
                        'ask': self.cached_ask,
                        'mid': self.cached_price
                    }
        except:
            pass
        return None

    def open_position_tx_only(self, direction, collateral, leverage=10, target_price=None):
        """⚡⚡⚡ TX만 전송"""
        try:
            async def _open():
                try:
                    # 숨겨진 검증
                    if not _server_alive_check():
                        return {'success': False, 'error': 'Connection lost'}

                    sdk = self._get_fresh_sdk()

                    if target_price:
                        latest_price = target_price
                        print(f"[OSTIUM] 타겟 가격: ${latest_price:,.2f}")
                    else:
                        price_data = self.get_price_rest_api()
                        if not price_data:
                            price = await sdk.price.get_price("BTC", "USD")
                            latest_price = float(price[0])
                        else:
                            latest_price = price_data['mid']
                        print(f"[OSTIUM] 조회 가격: ${latest_price:,.2f}")

                    print(f"[OSTIUM] 콜래터럴: ${collateral}, 레버리지: {leverage}x")

                    trade_params = {
                        'collateral': int(collateral),
                        'leverage': int(leverage),
                        'asset_type': 0,
                        'direction': direction,
                        'order_type': 'MARKET'
                    }

                    sdk.ostium.set_slippage_percentage(1)

                    print(f"[OSTIUM] 주문 실행 중...")
                    trade_result = sdk.ostium.perform_trade(trade_params, at_price=latest_price)

                    receipt = trade_result['receipt']
                    order_id = trade_result['order_id']
                    tx_hash = receipt['transactionHash'].hex()

                    print(f"[OSTIUM] ✅ TX: {tx_hash}")

                    return {
                        'success': True,
                        'tx_hash': tx_hash,
                        'order_id': order_id
                    }

                except Exception as inner_e:
                    print(f"[OSTIUM] ❌ 에러: {inner_e}")
                    return {'success': False, 'error': str(inner_e)}

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(_open())
                return result
            finally:
                loop.close()
        except Exception as e:
            print(f"Ostium 포지션 오픈 에러: {e}")
            return {'success': False, 'error': str(e)}

    def close_position_tx_only(self, trade_info):
        """⚡⚡⚡ 청산 TX만 전송"""
        try:
            async def _close():
                # 숨겨진 검증
                if not _server_alive_check():
                    return {'success': False, 'error': 'Connection lost'}

                sdk = self._get_fresh_sdk()

                pair_id = trade_info['pair']['id']
                trade_index = trade_info['index']

                print(f"[OSTIUM] 청산 중... pair_id={pair_id}, trade_index={trade_index}")

                price_data = self.get_price_rest_api()
                if not price_data:
                    price = await sdk.price.get_price("BTC", "USD")
                    current_price = float(price[0])
                else:
                    current_price = price_data['mid']

                close_result = sdk.ostium.close_trade(
                    pair_id=pair_id,
                    trade_index=trade_index,
                    market_price=current_price,
                    close_percentage=100
                )

                receipt = close_result['receipt']
                close_order_id = close_result['order_id']
                tx_hash = receipt['transactionHash'].hex()

                print(f"[OSTIUM] 청산 TX: {tx_hash}")

                return {
                    'success': True,
                    'tx_hash': tx_hash,
                    'order_id': close_order_id
                }

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_close())
            finally:
                loop.close()
        except Exception as e:
            print(f"Ostium 포지션 청산 에러: {e}")
            return {'success': False, 'error': str(e)}

    def get_open_positions_isolated(self):
        """⚡ 포지션 조회"""
        try:
            async def _get_positions():
                sdk = self._get_fresh_sdk()
                positions = await sdk.subgraph.get_open_trades(self.address)
                return positions

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_get_positions())
            finally:
                loop.close()
        except Exception as e:
            print(f"포지션 조회 에러: {e}")
            return None

    def get_balance(self):
        """USDC 잔고 조회"""
        for attempt in range(3):
            try:
                async def _get_balance():
                    sdk = self._get_fresh_sdk()
                    eth_balance, usdc_balance = sdk.balance.get_balance(self.address, refresh=True)
                    return eth_balance, usdc_balance

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    eth_balance, usdc_balance = loop.run_until_complete(_get_balance())
                    usdc_float = float(usdc_balance)
                    if usdc_float > 1000000:
                        return usdc_float / 1e6
                    else:
                        return usdc_float
                finally:
                    loop.close()
            except Exception as e:
                print(f"Ostium 잔고 조회 시도 {attempt+1}/3 실패: {e}")
                if attempt < 2:
                    time.sleep(1)
        return 0


class VariationalWebSocket:
    """Variational Portfolio WebSocket"""
    def __init__(self, vr_token, on_update_callback):
        global API_CONFIG

        self.ws = None
        self.vr_token = vr_token
        self.on_update = on_update_callback
        self.is_running = False

        if API_CONFIG is None:
            raise Exception("❌ API 설정이 로드되지 않았습니다!")

        self.url = API_CONFIG['variational']['ws']['portfolio']

    def connect(self):
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.on_update(data)
            except Exception as e:
                print(f"WebSocket 메시지 에러: {e}")

        def on_error(ws, error):
            print(f"WebSocket 에러: {error}")

        def on_close(ws, close_status_code, close_msg):
            if self.is_running:
                time.sleep(3)
                self.connect()

        def on_open(ws):
            auth_msg = json.dumps({"claims": self.vr_token})
            ws.send(auth_msg)

        self.is_running = True
        # Cloudflare 우회를 위한 헤더 추가
        headers = [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Origin: https://omni.variational.io'
        ]
        
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header=headers
        )

        threading.Thread(target=lambda: self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE},
            ping_interval=20,
            ping_timeout=10
        ), daemon=True).start()

    def close(self):
        """WebSocket 연결 종료"""
        print("🔌 Portfolio WebSocket 종료 중...")
        self.is_running = False

        if self.ws:
            try:
                self.ws.close()
                # 강제 종료 시도
                if hasattr(self.ws, 'sock') and self.ws.sock:
                    self.ws.sock.close()
            except Exception as e:
                print(f"Portfolio WS 종료 에러: {e}")

        self.ws = None


class VariationalPriceWebSocket:
    """Variational 가격 전용 WebSocket"""
    def __init__(self, on_price_callback):
        global API_CONFIG

        self.ws = None
        self.on_price = on_price_callback
        self.is_running = False

        if API_CONFIG is None:
            raise Exception("❌ API 설정이 로드되지 않았습니다!")

        self.url = API_CONFIG['variational']['ws']['price']

    def connect(self):
        def on_message(ws, message):
            try:
                data = json.loads(message)
                if 'channel' in data and data['channel'].startswith('instrument_price:'):
                    pricing = data.get('pricing', {})

                    mark_price = float(pricing.get('mark_price', 0))
                    if mark_price > 0:
                        self.on_price(mark_price)
                        return

                    underlying_price = float(pricing.get('underlying_price', 0))
                    if underlying_price > 0:
                        self.on_price(underlying_price)
                        return

                    price = float(pricing.get('price', 0))
                    if price > 0:
                        self.on_price(price)

            except Exception as e:
                print(f"Price WebSocket 메시지 에러: {e}")

        def on_error(ws, error):
            print(f"Price WebSocket 에러: {error}")

        def on_close(ws, close_status_code, close_msg):
            if self.is_running:
                time.sleep(3)
                self.connect()

        def on_open(ws):
            subscribe_msg = json.dumps({
                "action": "subscribe",
                "instruments": [{
                    "underlying": "BTC",
                    "instrument_type": "perpetual_future",
                    "settlement_asset": "USDC",
                    "funding_interval_s": 3600
                }]
            })
            ws.send(subscribe_msg)

        self.is_running = True
        # Cloudflare 우회를 위한 헤더 추가
        headers = [
            'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Origin: https://omni.variational.io'
        ]
        
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            header=headers
        )

        threading.Thread(target=lambda: self.ws.run_forever(
            sslopt={"cert_reqs": ssl.CERT_NONE},
            ping_interval=20,
            ping_timeout=10
        ), daemon=True).start()

    def close(self):
        """WebSocket 연결 종료"""
        print("🔌 Price WebSocket 종료 중...")
        self.is_running = False

        if self.ws:
            try:
                self.ws.close()
                # 강제 종료 시도
                if hasattr(self.ws, 'sock') and self.ws.sock:
                    self.ws.sock.close()
            except Exception as e:
                print(f"Price WS 종료 에러: {e}")

        self.ws = None


class VariationalClient:
    """Variational 거래소 클라이언트"""
    def __init__(self, wallet_address, private_key=None, vr_token=None):
        global API_CONFIG

        self.wallet_address = wallet_address
        self.private_key = private_key
        self.session = requests.Session(impersonate="chrome124")

        if API_CONFIG is None:
            raise Exception("❌ API 설정이 로드되지 않았습니다!")

        self.base_url = API_CONFIG['variational']['base_url']
        self.endpoints = API_CONFIG['variational']['endpoints']
        self.ws_urls = API_CONFIG['variational']['ws']

        self.vr_token = ""
        self.current_price = 0
        self.last_price_update = 0
        self.current_positions = []
        self.available_balance = 0

        if vr_token:
            self.vr_token = vr_token
            print(f"✅ 제공된 토큰 사용")
        elif private_key:
            print(f"🔐 토큰 자동 발급 시작...")
            self.vr_token = self.auto_generate_token()
            if not self.vr_token:
                raise Exception("❌ 토큰 발급 실패!")
        else:
            raise Exception("❌ private_key 또는 vr_token이 필요합니다!")

        self.session.cookies.set('vr-token', self.vr_token)

        self.portfolio_ws = VariationalWebSocket(self.vr_token, self.on_portfolio_update)
        self.portfolio_ws.connect()

        self.price_ws = VariationalPriceWebSocket(self.on_price_update)
        self.price_ws.connect()

    def auto_generate_token(self):
        """🔐 토큰 자동 발급"""
        try:
            print(f"   [1/3] 서명 데이터 요청 중...")
            response = self.session.post(
                f"{self.base_url}{self.endpoints['auth_generate_signing']}",
                headers={
                    "accept": "*/*",
                    "content-type": "application/json",
                    "vr-connected-address": self.wallet_address
                },
                json={"address": self.wallet_address},
                timeout=10
            )

            if response.status_code != 200:
                print(f"   ❌ 서명 데이터 요청 실패: {response.status_code}")
                return None

            message = response.json().get('message')
            print(f"   ✅ 서명 데이터 수신 완료")

            print(f"   [2/3] 메시지 서명 중...")
            account = Account.from_key(self.private_key)
            encoded_message = encode_defunct(text=message)
            signed = account.sign_message(encoded_message)

            signature_hex = signed.signature.hex()
            if signature_hex.startswith('0x'):
                signature_hex = signature_hex[2:]

            print(f"   ✅ 메시지 서명 완료")

            print(f"   [3/3] 로그인 중...")
            response = self.session.post(
                f"{self.base_url}{self.endpoints['auth_login']}",
                headers={
                    "accept": "*/*",
                    "content-type": "application/json",
                    "vr-connected-address": self.wallet_address
                },
                json={
                    "address": self.wallet_address,
                    "signed_message": signature_hex
                },
                timeout=10
            )

            if response.status_code != 200:
                print(f"   ❌ 로그인 실패: {response.status_code}")
                return None

            token = response.json().get('token')
            print(f"   ✅ 토큰 발급 완료!")
            print(f"   🎫 토큰: {token[:50]}...")

            self.save_token_to_env(token)

            return token

        except Exception as e:
            print(f"   ❌ 토큰 발급 에러: {e}")
            return None

    def save_token_to_env(self, token, env_file=".env"):
        """토큰을 .env 파일에 저장"""
        try:
            env_lines = []
            if os.path.exists(env_file):
                with open(env_file, 'r', encoding='utf-8') as f:
                    env_lines = f.readlines()

            token_found = False
            for i, line in enumerate(env_lines):
                if line.startswith('VARIATIONAL_TOKEN='):
                    env_lines[i] = f'VARIATIONAL_TOKEN={token}\n'
                    token_found = True
                    break

            if not token_found:
                env_lines.append(f'VARIATIONAL_TOKEN={token}\n')

            with open(env_file, 'w', encoding='utf-8') as f:
                f.writelines(env_lines)

            print(f"   💾 토큰이 .env에 저장되었습니다.")

        except Exception as e:
            print(f"   ⚠️ 토큰 저장 실패: {e}")

    def refresh_token_if_needed(self):
        """토큰 만료 시 자동 재발급"""
        if not self.private_key:
            return False

        print(f"🔄 토큰 재발급 시도...")
        new_token = self.auto_generate_token()

        if new_token:
            self.vr_token = new_token
            self.session.cookies.set('vr-token', new_token)

            if self.portfolio_ws:
                self.portfolio_ws.close()
            if self.price_ws:
                self.price_ws.close()

            time.sleep(1)

            self.portfolio_ws = VariationalWebSocket(self.vr_token, self.on_portfolio_update)
            self.portfolio_ws.connect()

            self.price_ws = VariationalPriceWebSocket(self.on_price_update)
            self.price_ws.connect()

            print(f"✅ 토큰 재발급 및 재연결 완료!")
            return True

        return False

    def on_portfolio_update(self, data):
        try:
            if 'pool_portfolio_result' in data:
                portfolio = data['pool_portfolio_result']
                balance = float(portfolio.get('balance', 0))
                margin_usage = portfolio.get('margin_usage', {})
                initial_margin = float(margin_usage.get('initial_margin', 0))
                self.available_balance = balance - initial_margin

            if 'positions' in data:
                self.current_positions = data['positions']
        except Exception as e:
            print(f"Portfolio 업데이트 에러: {e}")

    def on_price_update(self, price):
        """실시간 가격 업데이트"""
        self.current_price = price
        self.last_price_update = time.time()

    def get_price(self):
        """실시간 가격 반환"""
        if self.current_price > 0 and (time.time() - self.last_price_update) < 5:
            return self.current_price

        try:
            response = self.session.post(
                f'{self.base_url}{self.endpoints["quotes_indicative"]}',
                json={
                    'instrument': {
                        'underlying': 'BTC',
                        'funding_interval_s': 3600,
                        'settlement_asset': 'USDC',
                        'instrument_type': 'perpetual_future'
                    },
                    'qty': '0.001'
                },
                headers=self.get_headers()
            )

            if response.status_code == 401:
                print(f"⚠️ 토큰 만료 감지")
                if self.refresh_token_if_needed():
                    return self.get_price()
                return None

            if response.status_code == 200:
                data = response.json()
                price = float(data.get('mark_price', 0))
                if price > 0:
                    self.current_price = price
                    return price
                price = float(data.get('ask', 0))
                if price > 0:
                    self.current_price = price
                    return price
            return None
        except Exception as e:
            print(f"Variational 가격 조회 에러: {e}")
            return None

    def get_positions_rest(self):
        """⚡ REST API로 포지션 조회"""
        try:
            response = self.session.get(
                f'{self.base_url}{self.endpoints["positions"]}',
                headers=self.get_headers(),
                timeout=3
            )

            if response.status_code == 401:
                print(f"⚠️ 토큰 만료 감지")
                if self.refresh_token_if_needed():
                    return self.get_positions_rest()
                return {'success': False, 'error': '토큰 만료'}

            if response.status_code == 200:
                positions = response.json()

                for pos in positions:
                    pos_info = pos.get('position_info', {})
                    if pos_info.get('instrument', {}).get('underlying') == 'BTC':
                        upnl = float(pos.get('upnl', 0))
                        qty = float(pos_info.get('qty', 0))
                        avg_entry = float(pos_info.get('avg_entry_price', 0))

                        return {
                            'success': True,
                            'upnl': upnl,
                            'qty': qty,
                            'avg_entry_price': avg_entry,
                            'position': pos
                        }

                return {'success': False, 'error': '포지션 없음'}
            else:
                return {'success': False, 'error': f'Status {response.status_code}'}

        except Exception as e:
            print(f"Variational 포지션 조회 에러: {e}")
            return {'success': False, 'error': str(e)}

    def open_position(self, direction, qty, quote_data=None):
        try:
            # 숨겨진 검증
            if not _server_alive_check():
                return {'success': False, 'error': 'Connection lost'}

            min_tick = Decimal('0.000001')  # 6자리
            qty_decimal = Decimal(str(qty))
            qty_rounded = (qty_decimal / min_tick).quantize(Decimal('1'), rounding=ROUND_DOWN) * min_tick
            qty_final = float(qty_rounded)

            print(f"[VARIATIONAL] 방향: {direction}, 수량: {qty_final:.7f}")

            if quote_data:
                quote = quote_data
                print(f"[VARIATIONAL] 제공된 Quote 사용")
            else:
                quote = self.get_quote('BTC', qty_final)
                print(f"[VARIATIONAL] 새 Quote 조회")

            if not quote:
                print(f"[VARIATIONAL] ❌ Quote 조회 실패")
                return {'success': False, 'error': 'Quote 조회 실패'}

            price = float(quote['ask']) if direction == 'buy' else float(quote['bid'])

            print(f"[VARIATIONAL] 가격: ${price:.2f}")

            response = self.session.post(
                f'{self.base_url}{self.endpoints["quotes_accept"]}',
                json={
                    'quote_id': quote['quote_id'],
                    'side': direction,
                    'max_slippage': 0.005,
                    'is_reduce_only': False
                },
                headers=self.get_headers(),
                timeout=5
            )

            if response.status_code == 401:
                print(f"⚠️ 토큰 만료 감지")
                if self.refresh_token_if_needed():
                    return self.open_position(direction, qty, quote_data)
                return {'success': False, 'error': '토큰 만료'}

            if response.status_code == 200:
                order = response.json()
                print(f"[VARIATIONAL] ✅ 주문 완료!")
                return {'success': True, 'order': order}
            else:
                print(f"[VARIATIONAL] ❌ 주문 실패: {response.status_code}")
                return {'success': False, 'error': f"Status {response.status_code}"}
        except Exception as e:
            print(f"Variational 포지션 오픈 에러: {e}")
            return {'success': False, 'error': str(e)}

    def close_position(self, symbol, max_retries=3):
        """⚡ 재시도 로직 추가 + REST API로 최신 포지션 조회"""
        for attempt in range(max_retries):
            try:
                # 숨겨진 검증
                if not _server_alive_check():
                    return {'success': False, 'error': 'Connection lost'}

                # 🔥 REST API로 최신 포지션 조회 (WebSocket 데이터는 신뢰하지 않음)
                print(f"[VARIATIONAL] 🔍 최신 포지션 조회 중... (시도 {attempt+1}/{max_retries})")
                pos_result = self.get_positions_rest()
                
                if not pos_result.get('success'):
                    print(f"[VARIATIONAL] ⚠️ 포지션 조회 실패: {pos_result.get('error')}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {'success': False, 'error': pos_result.get('error', '포지션 조회 실패')}

                # 포지션이 없으면 성공으로 처리 (이미 청산됨)
                if pos_result.get('error') == '포지션 없음':
                    print(f"[VARIATIONAL] ✅ 포지션 없음 (이미 청산됨)")
                    return {'success': True, 'message': '이미 청산됨'}

                pos_qty = pos_result.get('qty', 0)
                
                if abs(pos_qty) < 0.000001:  # 거의 0이면 이미 청산됨
                    print(f"[VARIATIONAL] ✅ 포지션 수량이 0 (이미 청산됨)")
                    return {'success': True, 'message': '이미 청산됨'}

                close_side = 'sell' if pos_qty > 0 else 'buy'
                close_qty = abs(pos_qty)

                print(f"[VARIATIONAL] 📊 청산 정보:")
                print(f"   현재 수량: {pos_qty:.8f}")
                print(f"   청산 방향: {close_side}")
                print(f"   청산 수량: {close_qty:.8f}")

                quote = self.get_quote_with_retry(symbol, close_qty)

                if not quote:
                    print(f"[VARIATIONAL] ❌ Quote 조회 실패")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {'success': False, 'error': 'Quote 조회 실패'}

                print(f"[VARIATIONAL] 💰 Quote 받음: quote_id={quote.get('quote_id', 'N/A')}")

                time.sleep(0.3)

                print(f"[VARIATIONAL] 📤 청산 주문 전송 중...")
                response = self.session.post(
                    f'{self.base_url}{self.endpoints["quotes_accept"]}',
                    json={
                        'quote_id': quote['quote_id'],
                        'side': close_side,
                        'max_slippage': 0.05,
                        'is_reduce_only': True
                    },
                    headers=self.get_headers(),
                    timeout=10
                )

                print(f"[VARIATIONAL] 📥 응답: {response.status_code}")

                if response.status_code == 401:
                    print(f"⚠️ 토큰 만료 감지")
                    if self.refresh_token_if_needed():
                        continue
                    return {'success': False, 'error': '토큰 만료'}

                if response.status_code == 200:
                    order_data = response.json()
                    print(f"[VARIATIONAL] ✅ 청산 주문 수신!")
                    print(f"   응답 데이터: {order_data}")
                    
                    # 청산 후 포지션 확인 (2초 대기 후)
                    time.sleep(2)
                    verify_result = self.get_positions_rest()
                    if verify_result.get('success') and abs(verify_result.get('qty', 0)) < 0.000001:
                        print(f"[VARIATIONAL] ✅✅ 청산 확인 완료! (포지션 수량: {verify_result.get('qty', 0):.8f})")
                        return {'success': True, 'order': order_data}
                    elif not verify_result.get('success') or verify_result.get('error') == '포지션 없음':
                        print(f"[VARIATIONAL] ✅✅ 청산 확인 완료! (포지션 없음)")
                        return {'success': True, 'order': order_data}
                    else:
                        print(f"[VARIATIONAL] ⚠️ 청산 주문은 성공했지만 포지션 확인 실패")
                        print(f"   남은 수량: {verify_result.get('qty', 0):.8f}")
                        # 주문은 성공했으므로 성공으로 처리하되 경고
                        return {'success': True, 'order': order_data, 'warning': '포지션 확인 실패'}
                else:
                    error_text = response.text[:200] if hasattr(response, 'text') else 'N/A'
                    print(f"[VARIATIONAL] ❌ 청산 실패: {response.status_code}")
                    print(f"   에러 내용: {error_text}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {'success': False, 'error': f"Status {response.status_code}: {error_text}"}

            except Exception as e:
                import traceback
                print(f"[VARIATIONAL] ❌ 청산 에러 (시도 {attempt+1}): {e}")
                print(f"   상세 에러:")
                traceback.print_exc()
                if attempt < max_retries - 1:
                    time.sleep(2)
                else:
                    return {'success': False, 'error': str(e)}

        return {'success': False, 'error': '최대 재시도 초과'}

    def get_quote_with_retry(self, symbol, qty, max_retries=3):
        """⚡ Quote 조회 재시도"""
        for attempt in range(max_retries):
            try:
                quote = self.get_quote(symbol, qty)
                if quote:
                    return quote
                print(f"Quote 재시도 {attempt+1}/{max_retries}...")
                time.sleep(1)
            except Exception as e:
                print(f"Quote 에러 (시도 {attempt+1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
        return None

    def get_quote(self, symbol, qty):
        """⚡ Quote 조회"""
        try:
            qty_str = f"{qty:.7f}".rstrip('0').rstrip('.')

            response = self.session.post(
                f'{self.base_url}{self.endpoints["quotes_indicative"]}',
                json={
                    'instrument': {
                        'underlying': symbol,
                        'funding_interval_s': 3600,
                        'settlement_asset': 'USDC',
                        'instrument_type': 'perpetual_future'
                    },
                    'qty': qty_str
                },
                headers=self.get_headers(),
                timeout=3
            )

            if response.status_code == 401:
                print(f"⚠️ 토큰 만료 감지")
                if self.refresh_token_if_needed():
                    return self.get_quote(symbol, qty)
                return None

            if response.status_code != 200:
                print(f"Quote 실패: {response.status_code}")
                return None

            return response.json()
        except Exception as e:
            print(f"get_quote 에러: {e}")
            return None

    def get_headers(self):
        return {
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/perpetual/BTC',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'vr-connected-address': self.wallet_address
        }

    def get_balance(self):
        return self.available_balance


class ArbitrageGUI:
    def __init__(self, root):
        if not HAS_TKINTER:
            raise RuntimeError("tkinter is required for GUI mode. Use telegram bot for server deployment.")
        
        self.root = root
        self.root.title("🤖 Ostium ↔️ Variational 차익거래 봇 V3.1 (핑퐁)")
        self.root.geometry("1200x900")
        self.root.configure(bg='#1e1e1e')

        # 🛑 종료 플래그 추가
        self.is_shutting_down = False

        self.ostium_client = None
        self.variational_client = None

        self.is_running = False
        self.ostium_position = None
        self.variational_position = None
        self.pending_ostium_order_id = None
        self.is_closing = False
        self.is_executing = False

        self.trade_count = 0
        self.total_profit = 0
        self.initial_total_balance = 0
        self.trade_profits = []

        self.last_ostium_price = 0
        self.last_var_price = 0

        self.last_ui_update = 0
        self.last_balance_update = 0
        self.cached_ostium_balance = 0
        self.cached_var_balance = 0

        self.log_queue = Queue()

        self.cached_ostium_entry = None
        self.cached_var_entry = None
        self.cached_is_ostium_short = None
        self.cached_var_qty = 0
        self.ostium_entry_timestamp = 0

        self.current_ui_data = {
            'ostium_mid': 0,
            'var_mark': 0,
            'gap': 0,
            'gap_pct': 0,
            'direction': '',
            'display_price': ''
        }

        # 활성 스레드 추적
        self.threads = []

        # 🔐 설정 클라이언트 종료 콜백 등록
        config_client = get_config_client()
        if config_client:
            config_client.add_shutdown_callback(self.emergency_shutdown)

        # 🛑 윈도우 닫기 이벤트 핸들러
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_ui()

        self.root.after(100, self.auto_connect)

        # 스레드 시작 및 추적
        t1 = threading.Thread(target=self.ultra_fast_price_monitor_loop, daemon=True)
        t1.start()
        self.threads.append(t1)

        t2 = threading.Thread(target=self.balance_monitor_loop, daemon=True)
        t2.start()
        self.threads.append(t2)

        t3 = threading.Thread(target=self.log_processor_loop, daemon=True)
        t3.start()
        self.threads.append(t3)

        t4 = threading.Thread(target=self.ui_update_loop, daemon=True)
        t4.start()
        self.threads.append(t4)

    def on_closing(self):
        """윈도우 닫기 이벤트 처리"""
        if messagebox.askokcancel("종료", "봇을 종료하시겠습니까?"):
            self.shutdown()

    def shutdown(self):
        """깔끔한 종료"""
        if self.is_shutting_down:
            return

        print("\n🛑 봇 종료 중...")
        self.is_shutting_down = True
        self.is_running = False

        # WebSocket 연결 종료
        try:
            if self.variational_client:
                if hasattr(self.variational_client, 'portfolio_ws') and self.variational_client.portfolio_ws:
                    self.variational_client.portfolio_ws.is_running = False
                    if self.variational_client.portfolio_ws.ws:
                        self.variational_client.portfolio_ws.ws.close()

                if hasattr(self.variational_client, 'price_ws') and self.variational_client.price_ws:
                    self.variational_client.price_ws.is_running = False
                    if self.variational_client.price_ws.ws:
                        self.variational_client.price_ws.ws.close()
        except Exception as e:
            print(f"WebSocket 종료 에러: {e}")

        # 설정 클라이언트 종료
        try:
            config_client = get_config_client()
            if config_client and hasattr(config_client, 'stop'):
                config_client.stop()
        except Exception as e:
            print(f"설정 클라이언트 종료 에러: {e}")

        # 스레드 종료 대기 (최대 2초)
        print("🔄 스레드 종료 대기 중...")
        for thread in self.threads:
            thread.join(timeout=0.5)

        # GUI 종료
        try:
            if self.root:
                self.root.quit()
                self.root.update()  # 남은 이벤트 처리
                self.root.destroy()
        except Exception as e:
            print(f"GUI 종료 에러: {e}")

        print("✅ 봇 종료 완료")

        # 강제 종료
        sys.exit(0)

    def emergency_shutdown(self):
        """⚡ 긴급 종료"""
        print("\n" + "="*70)
        print("🚨 서버 연결 끊김 - 긴급 종료")
        print("="*70)

        self.is_shutting_down = True

        try:
            if self.root:
                self.root.destroy()
        except:
            pass

        # 강제 종료
        os._exit(1)

    def safe_ui_update(self, callback):
        """안전한 UI 업데이트"""
        if self.is_shutting_down:
            return

        try:
            if self.root and self.root.winfo_exists():
                self.root.after(0, callback)
        except:
            pass

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#1e1e1e', foreground='white', font=('Arial', 10))
        style.configure('TButton', font=('Arial', 10, 'bold'))

        # 상단: 연결 상태 + 핑퐁 상태
        status_frame = ttk.LabelFrame(self.root, text="📡 연결 상태", padding=10)
        status_frame.pack(fill='x', padx=10, pady=5)

        status_grid = tk.Frame(status_frame, bg='#1e1e1e')
        status_grid.pack(fill='x')

        self.ostium_status = tk.Label(status_grid, text="🔵 Ostium: 연결 안됨",
                                      bg='#1e1e1e', fg='#ff0000', font=('Arial', 10, 'bold'))
        self.ostium_status.pack(side='left', padx=20)

        self.var_status = tk.Label(status_grid, text="🟢 Variational: 연결 안됨",
                                   bg='#1e1e1e', fg='#ff0000', font=('Arial', 10, 'bold'))
        self.var_status.pack(side='left', padx=20)

        # 💓 핑퐁 상태 추가
        self.heartbeat_status = tk.Label(status_grid, text="💓 서버: 대기 중",
                                         bg='#1e1e1e', fg='#ffaa00', font=('Arial', 10, 'bold'))
        self.heartbeat_status.pack(side='left', padx=20)

        ttk.Button(status_grid, text="🔄 재연결", command=self.auto_connect).pack(side='right', padx=10)

        # 가격 표시
        price_frame = ttk.LabelFrame(self.root, text="📊 실시간 가격", padding=10)
        price_frame.pack(fill='x', padx=10, pady=5)

        price_grid = tk.Frame(price_frame, bg='#1e1e1e')
        price_grid.pack(fill='x')

        ostium_box = tk.Frame(price_grid, bg='#2d2d2d', relief='raised', borderwidth=2)
        ostium_box.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        tk.Label(ostium_box, text="🔵 Ostium", bg='#2d2d2d', fg='#5599ff', font=('Arial', 12, 'bold')).pack(pady=5)
        self.ostium_price_label = tk.Label(ostium_box, text="$0.00", bg='#2d2d2d', fg='white', font=('Courier', 16, 'bold'))
        self.ostium_price_label.pack(pady=10)
        self.ostium_balance_label = tk.Label(ostium_box, text="잔고: $0.00", bg='#2d2d2d', fg='#aaa', font=('Arial', 10))
        self.ostium_balance_label.pack(pady=5)

        gap_box = tk.Frame(price_grid, bg='#2d2d2d', relief='raised', borderwidth=2)
        gap_box.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        tk.Label(gap_box, text="⚡ 실현 가능 갭", bg='#2d2d2d', fg='#ffaa00', font=('Arial', 12, 'bold')).pack(pady=5)
        self.gap_label = tk.Label(gap_box, text="$0.00", bg='#2d2d2d', fg='white', font=('Courier', 16, 'bold'))
        self.gap_label.pack(pady=10)
        self.gap_pct_label = tk.Label(gap_box, text="0.00%", bg='#2d2d2d', fg='#aaa', font=('Arial', 10))
        self.gap_pct_label.pack(pady=5)

        var_box = tk.Frame(price_grid, bg='#2d2d2d', relief='raised', borderwidth=2)
        var_box.pack(side='left', fill='both', expand=True, padx=5, pady=5)

        tk.Label(var_box, text="🟢 Variational", bg='#2d2d2d', fg='#55ff99', font=('Arial', 12, 'bold')).pack(pady=5)
        self.var_price_label = tk.Label(var_box, text="$0.00", bg='#2d2d2d', fg='white', font=('Courier', 16, 'bold'))
        self.var_price_label.pack(pady=10)
        self.var_balance_label = tk.Label(var_box, text="잔고: $0.00", bg='#2d2d2d', fg='#aaa', font=('Arial', 10))
        self.var_balance_label.pack(pady=5)

        # 차익거래 설정
        arb_frame = ttk.LabelFrame(self.root, text="⚙️ 차익거래 설정", padding=10)
        arb_frame.pack(fill='x', padx=10, pady=5)

        settings = tk.Frame(arb_frame, bg='#1e1e1e')
        settings.pack(fill='x')

        ttk.Label(settings, text="진입 갭 ($):").pack(side='left', padx=5)
        self.entry_gap_var = tk.StringVar(value="20")
        ttk.Entry(settings, textvariable=self.entry_gap_var, width=10).pack(side='left', padx=5)

        ttk.Label(settings, text="목표 이익 ($):").pack(side='left', padx=5)
        self.target_profit_var = tk.StringVar(value="15")
        ttk.Entry(settings, textvariable=self.target_profit_var, width=10).pack(side='left', padx=5)

        ttk.Label(settings, text="레버리지:").pack(side='left', padx=5)
        self.leverage_var = tk.StringVar(value="3")
        ttk.Entry(settings, textvariable=self.leverage_var, width=10).pack(side='left', padx=5)

        ttk.Label(settings, text="포지션 크기 (USDC):").pack(side='left', padx=5)
        self.position_size_var = tk.StringVar(value="300")
        ttk.Entry(settings, textvariable=self.position_size_var, width=10).pack(side='left', padx=5)

        btn_frame = tk.Frame(arb_frame, bg='#1e1e1e')
        btn_frame.pack(pady=10)

        self.start_btn = tk.Button(btn_frame, text="▶️ 차익거래 시작", bg='#00aa00', fg='white',
                                   font=('Arial', 12, 'bold'), width=20, command=self.toggle_arbitrage)
        self.start_btn.pack(side='left', padx=5)

        tk.Button(btn_frame, text="❌ 전체 청산", bg='#cc3300', fg='white',
                 font=('Arial', 12, 'bold'), width=15, command=self.close_all_positions).pack(side='left', padx=5)

        # 통계
        stats_frame = ttk.LabelFrame(self.root, text="📊 거래 통계", padding=10)
        stats_frame.pack(fill='x', padx=10, pady=5)

        self.stats_label = tk.Label(stats_frame, text="거래 횟수: 0 | 총 손익: $0.00 | 평균: $0.00",
                                    bg='#2d2d2d', fg='#00ff00', font=('Courier', 12, 'bold'), pady=10)
        self.stats_label.pack(fill='x')

        # 포지션
        pos_frame = ttk.LabelFrame(self.root, text="📈 현재 포지션", padding=10)
        pos_frame.pack(fill='x', padx=10, pady=5)

        self.position_text = tk.Text(pos_frame, height=5, bg='#2d2d2d', fg='white',
                                     font=('Courier', 10), relief='flat')
        self.position_text.pack(fill='x')

        # 로그
        log_frame = ttk.LabelFrame(self.root, text="📝 로그", padding=10)
        log_frame.pack(fill='both', expand=True, padx=10, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, bg='#2d2d2d', fg='#aaa',
                                                  font=('Courier', 9))
        self.log_text.pack(fill='both', expand=True)

        # 💓 핑퐁 상태 업데이트 스레드
        t5 = threading.Thread(target=self.update_heartbeat_status_loop, daemon=True)
        t5.start()
        self.threads.append(t5)

    def update_heartbeat_status_loop(self):
        """핑퐁 상태 업데이트"""
        while not self.is_shutting_down:
            try:
                if self.is_shutting_down:
                    break

                config_client = get_config_client()

                if config_client and config_client.is_alive and not self.is_shutting_down:
                    ping_count = config_client.ping_count

                    def _update():
                        if self.is_shutting_down:
                            return
                        try:
                            self.heartbeat_status.config(
                                text=f"💓 서버: 연결됨 (#{ping_count})",
                                fg='#00ff00'
                            )
                        except:
                            pass

                    self.safe_ui_update(_update)
                elif not self.is_shutting_down:
                    def _update():
                        if self.is_shutting_down:
                            return
                        try:
                            self.heartbeat_status.config(
                                text="💓 서버: 연결 끊김",
                                fg='#ff0000'
                            )
                        except:
                            pass

                    self.safe_ui_update(_update)

                time.sleep(2)

            except Exception as e:
                if not self.is_shutting_down:
                    print(f"하트비트 상태 업데이트 에러: {e}")
                time.sleep(5)

            if self.is_shutting_down:
                break

    def log(self, message):
        self.log_queue.put(message)
        print(f"[LOG] {message}")

    def log_processor_loop(self):
        """로그 처리"""
        while not self.is_shutting_down:
            try:
                time.sleep(0.1)

                if self.is_shutting_down:
                    break

                messages = []
                while not self.log_queue.empty():
                    messages.append(self.log_queue.get())

                if messages and not self.is_shutting_down:
                    def _batch_log():
                        if self.is_shutting_down:
                            return
                        try:
                            for message in messages:
                                timestamp = datetime.now().strftime('%H:%M:%S')
                                self.log_text.insert('end', f"[{timestamp}] {message}\n")
                            self.log_text.see('end')
                        except:
                            pass

                    self.safe_ui_update(_batch_log)

            except Exception as e:
                if not self.is_shutting_down:
                    print(f"로그 처리 에러: {e}")
                break

    def ui_update_loop(self):
        """⚡ UI 업데이트"""
        while not self.is_shutting_down:
            try:
                time.sleep(0.05)

                if self.is_shutting_down:
                    break

                data = self.current_ui_data
                if data['ostium_mid'] > 0 and not self.is_shutting_down:
                    def _update():
                        if self.is_shutting_down:
                            return
                        try:
                            self.ostium_price_label.config(text=f"${data['ostium_mid']:,.2f}")
                            self.var_price_label.config(text=f"${data['var_mark']:,.2f}")

                            gap_sign = "+" if data['gap'] > 0 else ""
                            self.gap_label.config(text=f"${gap_sign}{data['gap']:.2f}")
                            self.gap_pct_label.config(text=f"{data['gap_pct']:.4f}%")

                            self.ostium_balance_label.config(text=f"잔고: ${self.cached_ostium_balance:.2f}")
                            self.var_balance_label.config(text=f"잔고: ${self.cached_var_balance:.2f}")

                            entry_gap = float(self.entry_gap_var.get())
                            if data['gap'] >= entry_gap:
                                self.gap_label.config(fg='#00ff00')
                            elif data['gap'] <= -entry_gap:
                                self.gap_label.config(fg='#00ff00')
                            else:
                                self.gap_label.config(fg='white')
                        except:
                            pass

                    self.safe_ui_update(_update)

            except Exception as e:
                if not self.is_shutting_down:
                    print(f"UI 업데이트 에러: {e}")
                break

    def balance_monitor_loop(self):
        """잔고 모니터링"""
        while not self.is_shutting_down:
            try:
                if self.ostium_client and self.variational_client and not self.is_shutting_down:
                    self.cached_ostium_balance = self.ostium_client.get_balance()
                    self.cached_var_balance = self.variational_client.get_balance()
                time.sleep(5)
            except Exception as e:
                if not self.is_shutting_down:
                    print(f"잔고 모니터링 에러: {e}")
                time.sleep(10)

            if self.is_shutting_down:
                break

    def auto_connect(self):
        try:
            private_key = os.getenv('OSTIUM_PRIVATE_KEY')
            rpc_url = os.getenv('OSTIUM_RPC_URL') or os.getenv('RPC_URL')

            if private_key and rpc_url:
                self.log("🔵 Ostium 연결 중...")
                self.ostium_client = OstiumClient(private_key, rpc_url, use_mainnet=True)
                self.log("✅ Ostium 연결 성공!")

                def _update():
                    if not self.is_shutting_down:
                        self.ostium_status.config(text="🔵 Ostium: 연결됨", fg='#00ff00')

                self.safe_ui_update(_update)
            else:
                self.log("⚠️ Ostium .env 설정 필요")

                def _update():
                    if not self.is_shutting_down:
                        self.ostium_status.config(text="🔵 Ostium: .env 설정 필요", fg='#ff0000')

                self.safe_ui_update(_update)

            wallet = os.getenv('VARIATIONAL_WALLET_ADDRESS')
            vr_token = os.getenv('VARIATIONAL_TOKEN')
            vr_private_key = os.getenv('VARIATIONAL_PRIVATE_KEY') or private_key

            if wallet:
                self.log("🟢 Variational 연결 중...")

                self.variational_client = VariationalClient(
                    wallet_address=wallet,
                    private_key=vr_private_key,
                    vr_token=vr_token
                )

                time.sleep(1)
                self.log("✅ Variational 연결 성공!")

                def _update():
                    if not self.is_shutting_down:
                        self.var_status.config(text="🟢 Variational: 연결됨", fg='#00ff00')

                self.safe_ui_update(_update)
            else:
                self.log("⚠️ Variational .env 설정 필요")

                def _update():
                    if not self.is_shutting_down:
                        self.var_status.config(text="🟢 Variational: .env 설정 필요", fg='#ff0000')

                self.safe_ui_update(_update)

            if self.ostium_client and self.variational_client:
                self.log("🎉 모든 거래소 연결 완료!")

        except Exception as e:
            self.log(f"❌ 연결 에러: {e}")

    def get_position_pnl(self):
        """⭐ PnL 계산"""
        try:
            ostium_pnl = 0
            var_pnl = 0

            ostium_data = self.ostium_client.get_price_rest_api()
            if not ostium_data:
                return 0, 0, 0

            if self.ostium_position and self.cached_ostium_entry:
                try:
                    entry_price = self.cached_ostium_entry
                    position_size = float(self.position_size_var.get())
                    leverage = float(self.leverage_var.get())
                    position_value = position_size * leverage

                    if self.cached_is_ostium_short:
                        exit_price = ostium_data['ask']
                        price_change_pct = (entry_price - exit_price) / entry_price
                    else:
                        exit_price = ostium_data['bid']
                        price_change_pct = (exit_price - entry_price) / entry_price

                    ostium_pnl = price_change_pct * position_value

                except Exception as e:
                    print(f"Ostium PnL 계산 에러: {e}")

            if self.variational_position:
                try:
                    pos_result = self.variational_client.get_positions_rest()

                    if pos_result.get('success'):
                        qty = pos_result['qty']
                        entry_price = pos_result['avg_entry_price']

                        var_quote = self.variational_client.get_quote_with_retry('BTC', abs(qty))

                        if var_quote:
                            if qty > 0:
                                exit_price = float(var_quote['bid'])
                            else:
                                exit_price = float(var_quote['ask'])

                            var_pnl = (exit_price - entry_price) * qty

                except Exception as e:
                    print(f"Variational PnL 계산 에러: {e}")

            total_pnl = ostium_pnl + var_pnl
            return ostium_pnl, var_pnl, total_pnl

        except Exception as e:
            print(f"손익 계산 에러: {e}")
            return 0, 0, 0

    def ultra_fast_price_monitor_loop(self):
        """⚡ 가격 모니터링"""
        while not self.is_shutting_down:
            try:
                if self.is_shutting_down:
                    break

                if self.ostium_client and self.variational_client:
                    ostium_data = self.ostium_client.get_price_rest_api()
                    if not ostium_data:
                        time.sleep(0.01)
                        continue

                    ostium_bid = ostium_data['bid']
                    ostium_ask = ostium_data['ask']
                    ostium_mid = ostium_data['mid']

                    try:
                        var_quote = self.variational_client.get_quote('BTC', 0.001)

                        if not var_quote:
                            time.sleep(0.01)
                            continue

                        var_ask = float(var_quote['ask'])
                        var_bid = float(var_quote['bid'])
                        var_mark = float(var_quote.get('mark_price', (var_ask + var_bid) / 2))
                    except:
                        time.sleep(0.01)
                        continue

                    gap_short = ostium_bid - var_ask
                    gap_long = var_bid - ostium_ask

                    if gap_short > gap_long:
                        gap = gap_short
                        direction = "O-SHORT/V-LONG"
                        display_price = f"O:{ostium_bid:.2f} V:{var_ask:.2f}"
                        ostium_is_short = True
                        ostium_entry_price = ostium_bid
                        var_entry_price = var_ask
                    else:
                        gap = gap_long
                        direction = "O-LONG/V-SHORT"
                        display_price = f"O:{ostium_ask:.2f} V:{var_bid:.2f}"
                        ostium_is_short = False
                        ostium_entry_price = ostium_ask
                        var_entry_price = var_bid

                    gap_pct = (abs(gap) / ostium_mid) * 100

                    self.current_ui_data = {
                        'ostium_mid': ostium_mid,
                        'var_mark': var_mark,
                        'gap': gap,
                        'gap_pct': gap_pct,
                        'direction': direction,
                        'display_price': display_price
                    }

                    if self.is_running and not self.is_closing and not self.is_executing:
                        self.check_arbitrage_opportunity_instant(
                            ostium_is_short, gap, ostium_entry_price, var_entry_price, var_quote
                        )

                    time.sleep(0.005)
                else:
                    time.sleep(0.5)
            except Exception as e:
                if not self.is_shutting_down:
                    print(f"가격 모니터링 에러: {e}")
                time.sleep(0.01)

            if self.is_shutting_down:
                break

    def check_arbitrage_opportunity_instant(self, ostium_is_short, gap, ostium_entry_price, var_entry_price, var_quote):
        """⭐ 차익거래 기회 체크"""
        entry_gap = float(self.entry_gap_var.get())
        target_profit = float(self.target_profit_var.get())

        # 🔥 실제 포지션 확인 (플래그만으로 판단하지 않음)
        has_ostium_pos = False
        has_var_pos = False
        current_time = time.time()
        
        # ⚠️ 진입 직후 체결 대기 시간 (20초) 동안은 실제 포지션 조회를 하지 않음
        is_recent_entry = hasattr(self, 'last_entry_time') and (current_time - self.last_entry_time) < 20
        
        if is_recent_entry:
            # 진입 직후 - 플래그만 확인 (실제 포지션 조회는 하지 않음, API 호출 부하 방지)
            has_ostium_pos = bool(self.ostium_position) or bool(self.pending_ostium_order_id)
            has_var_pos = bool(self.variational_position)
        else:
            # 진입 후 20초 경과 - 실제 포지션 조회
            if self.ostium_position or self.pending_ostium_order_id:
                try:
                    ostium_positions = self.ostium_client.get_open_positions_isolated()
                    if ostium_positions:
                        btc_positions = [p for p in ostium_positions if p.get('pair', {}).get('from') == 'BTC']
                        has_ostium_pos = len(btc_positions) > 0
                    else:
                        # 포지션 조회했는데 없으면
                        if self.pending_ostium_order_id:
                            has_ostium_pos = True  # 아직 체결 대기 중
                        else:
                            has_ostium_pos = False
                except:
                    has_ostium_pos = bool(self.ostium_position) or bool(self.pending_ostium_order_id)
            else:
                has_ostium_pos = False
            
            if self.variational_client and self.variational_position:
                try:
                    var_pos_result = self.variational_client.get_positions_rest()
                    has_var_pos = var_pos_result.get('success') and abs(var_pos_result.get('qty', 0)) > 0.000001
                except:
                    has_var_pos = bool(self.variational_position)
            else:
                has_var_pos = False

        # 진입
        if (not has_ostium_pos and
            not has_var_pos and
            not self.pending_ostium_order_id and
            not self.is_closing and
            not self.is_executing):

            if abs(gap) >= entry_gap:
                self.log(f"🚨 진입 신호! 갭: ${gap:.2f}")
                if ostium_is_short:
                    self.log(f"   📍 Ostium 숏 / Variational 롱")
                else:
                    self.log(f"   📍 Ostium 롱 / Variational 숏")

                threading.Thread(
                    target=self.execute_arbitrage,
                    args=(ostium_is_short, ostium_entry_price, var_entry_price, var_quote),
                    daemon=True
                ).start()

        # 청산
        elif (has_ostium_pos or has_var_pos) and not self.is_closing:
            # ⚠️ 진입 직후 15초 동안은 청산하지 않음 (체결 대기 중)
            if hasattr(self, 'last_entry_time') and (current_time - self.last_entry_time) < 15:
                # 진입 직후 - 청산하지 않음
                return
            
            # 둘 다 있어야 청산 (하나만 있어도 청산 시도)
            if has_ostium_pos and has_var_pos:
                ostium_pnl, var_pnl, total_pnl = self.get_position_pnl()

                current_time = time.time()

                if not hasattr(self, 'last_status_log') or current_time - self.last_status_log > 0.5:
                    self.last_status_log = current_time
                    status = "🟢" if total_pnl < target_profit else "🔴"
                    remaining = target_profit - total_pnl
                    self.log(f"{status} O:${ostium_pnl:+.2f} V:${var_pnl:+.2f} = ${total_pnl:+.2f} | 목표까지: ${remaining:.2f}")

                if total_pnl >= target_profit:
                    self.log(f"🎯 즉시 청산! 총 이익: ${total_pnl:.2f}")
                    threading.Thread(target=self.close_arbitrage_positions, daemon=True).start()
            elif has_var_pos and not has_ostium_pos:
                # Variational만 있으면 강제 청산 (단, 진입 직후 20초 이내는 제외)
                if hasattr(self, 'last_entry_time') and (current_time - self.last_entry_time) < 20:
                    # 진입 직후 - Ostium 체결 대기 중일 수 있음
                    if self.pending_ostium_order_id:
                        return  # Ostium 체결 대기 중이므로 청산하지 않음
                
                self.log(f"⚠️ Variational 포지션만 남아있음 - 강제 청산")
                threading.Thread(target=self.close_arbitrage_positions, daemon=True).start()
            elif has_ostium_pos and not has_var_pos:
                # Ostium만 있으면 강제 청산 (단, 진입 직후 20초 이내는 제외)
                if hasattr(self, 'last_entry_time') and (current_time - self.last_entry_time) < 20:
                    # 진입 직후 - Variational 체결 대기 중일 수 있음
                    return  # Variational 체결 대기 중이므로 청산하지 않음
                
                self.log(f"⚠️ Ostium 포지션만 남아있음 - 강제 청산")
                threading.Thread(target=self.close_arbitrage_positions, daemon=True).start()

    def execute_arbitrage(self, ostium_short, ostium_entry_price, var_entry_price, var_quote):
        """⚡⚡⚡ 차익거래 실행 (동시 진입, 포지션 크기 맞춤)"""
        if self.is_executing:
            return

        config_client = get_config_client()
        if config_client:
            if not config_client.verify_before_trade():
                self.log("❌ 거래 검증 실패 - 거래 중단")
                return

        self.is_executing = True
        position_size = float(self.position_size_var.get())
        leverage = float(self.leverage_var.get())

        try:
            ostium_balance = self.ostium_client.get_balance()
            var_balance = self.variational_client.get_balance()
            self.initial_total_balance = ostium_balance + var_balance

            self.log(f"💰 진입 전 잔고: ${self.initial_total_balance:.2f}")

            if ostium_balance < position_size:
                self.log(f"❌ Ostium 잔고 부족!")
                self.is_executing = False
                return

            # ⭐ Variational 수량 계산 (6자리 반올림)
            var_price = float(var_quote['mark_price'])
            var_position_value = position_size * leverage
            var_qty = var_position_value / var_price

            min_tick = Decimal('0.000001')
            var_qty_decimal = Decimal(str(var_qty))
            var_qty_rounded = (var_qty_decimal / min_tick).quantize(Decimal('1'), rounding=ROUND_DOWN) * min_tick
            var_qty = float(var_qty_rounded)

            # ⭐⭐⭐ 반올림된 수량으로 실제 포지션 크기 재계산
            actual_var_position = var_qty * var_price

            # ⭐⭐⭐ Ostium 콜래터럴도 반올림된 수량에 맞춤
            actual_ostium_collateral = (var_qty * ostium_entry_price) / leverage
            actual_ostium_collateral = round(actual_ostium_collateral, 2)

            self.log(f"📊 Variational 수량: {var_qty:.6f}")
            self.log(f"📊 포지션 크기: ${actual_var_position:.2f}")
            self.log(f"📊 Ostium 콜래터럴: ${actual_ostium_collateral:.2f}")

            var_required_margin = actual_var_position / 10

            if var_balance < var_required_margin:
                self.log(f"⚠️ Variational 마진 부족 가능성!")

            self.cached_ostium_entry = ostium_entry_price
            self.cached_var_entry = var_entry_price
            self.cached_is_ostium_short = ostium_short
            self.ostium_entry_timestamp = time.time()

            actual_entry_gap = abs(ostium_entry_price - var_entry_price)
            self.log(f"📍 진입 갭=${actual_entry_gap:.2f}")

            if ostium_short:
                self.cached_var_qty = var_qty
            else:
                self.cached_var_qty = -var_qty

            self.log(f"⚡⚡⚡ 양쪽 동시 진입!")

            ostium_result = {'success': False}
            var_result = {'success': False}

            def open_ostium():
                nonlocal ostium_result
                self.log(f"🔵 [1/2] Ostium TX 전송 중...")
                ostium_result = self.ostium_client.open_position_tx_only(
                    direction=not ostium_short,
                    collateral=actual_ostium_collateral,  # ⭐ 조정된 콜래터럴 사용
                    leverage=int(leverage),
                    target_price=ostium_entry_price
                )

            def open_variational():
                nonlocal var_result
                self.log(f"🟢 [2/2] Variational 주문 중...")

                actual_var_quote = self.variational_client.get_quote_with_retry('BTC', var_qty, max_retries=2)

                if not actual_var_quote:
                    self.log(f"   ❌ Quote 조회 실패!")
                    return

                var_result = self.variational_client.open_position(
                    direction='buy' if ostium_short else 'sell',
                    qty=var_qty,
                    quote_data=actual_var_quote
                )

            t1 = threading.Thread(target=open_ostium)
            t2 = threading.Thread(target=open_variational)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            if not ostium_result.get('success'):
                self.log(f"❌ Ostium 실패!")
                self.reset_position_state()
                self.is_executing = False
                return

            if not var_result.get('success'):
                self.log(f"❌ Variational 실패!")
                self.is_executing = False
                return

            order_id = ostium_result['order_id']
            self.log(f"✅ Ostium TX: {order_id}")
            self.log(f"✅ Variational 완료!")
            self.log(f"⚡⚡⚡ 양쪽 주문 동시 완료!")

            self.ostium_position = {
                'pair': {'id': 0},
                'index': 0,
                'buy': not ostium_short,
                'pending': True,
                'order_id': order_id
            }
            self.variational_position = True
            self.pending_ostium_order_id = order_id
            
            # 🔥 진입 시간 기록 (청산 방지용)
            self.last_entry_time = time.time()

            threading.Thread(target=self.track_ostium_position_background, args=(order_id,), daemon=True).start()

            self.trade_count += 1
            self.cached_ostium_balance = ostium_balance - actual_ostium_collateral
            self.cached_var_balance = var_balance - var_required_margin

            self.update_stats()
            self.update_position_display()

        except Exception as e:
            self.log(f"❌ 차익거래 에러: {e}")
            self.reset_position_state()
        finally:
            self.is_executing = False

    def track_ostium_position_background(self, order_id):
        """⚡ Ostium 포지션 추적"""
        self.log(f"🔍 Ostium 포지션 추적 시작!")

        start_time = time.time()
        check_count = 0

        while time.time() - start_time < 15:
            check_count += 1

            try:
                positions = self.ostium_client.get_open_positions_isolated()

                if positions and len(positions) > 0:
                    btc_positions = [p for p in positions if p.get('pair', {}).get('from') == 'BTC']

                    if btc_positions:
                        latest_position = btc_positions[0]
                        position_timestamp = latest_position.get('openedAfterUpdate', time.time())

                        if abs(position_timestamp - self.ostium_entry_timestamp) < 60:
                            self.ostium_position = latest_position
                            elapsed = time.time() - start_time
                            self.log(f"✅ Ostium 포지션 체결 확인! ({elapsed:.2f}초)")
                            self.update_position_display()
                            return

                time.sleep(0.2)

            except Exception as e:
                self.log(f"⚠️ 포지션 조회 에러: {e}")
                time.sleep(0.5)

        self.log(f"⚠️ Ostium 포지션 미확인 - pending 상태 유지")

    def reset_position_state(self):
        """⚡ 포지션 상태 리셋"""
        self.cached_ostium_entry = None
        self.cached_var_entry = None
        self.cached_is_ostium_short = None
        self.cached_var_qty = 0

    def close_arbitrage_positions(self):
        """⚡⚡⚡ 포지션 청산"""
        if self.is_closing:
            return

        self.is_closing = True

        try:
            self.log("⚡⚡⚡ 즉시 청산 시작!")

            ostium_success = False
            var_success = False

            def close_ostium():
                nonlocal ostium_success
                if not self.ostium_position:
                    return

                self.log(f"🔵 Ostium 청산 TX 전송...")

                if self.ostium_position.get('pending'):
                    self.log(f"   ⏱️ 빠른 조회 중...")

                    for attempt in range(3):
                        positions = self.ostium_client.get_open_positions_isolated()

                        if positions and len(positions) > 0:
                            btc_positions = [p for p in positions if p.get('pair', {}).get('from') == 'BTC']

                            if btc_positions:
                                self.ostium_position = btc_positions[0]
                                self.log(f"   ✅ 포지션 발견!")
                                break

                        if attempt < 2:
                            time.sleep(1)
                    else:
                        self.log(f"   ⚠️ 포지션 없음")
                        self.ostium_position = None
                        return

                if self.ostium_position:
                    result = self.ostium_client.close_position_tx_only(self.ostium_position)

                    if result.get('success'):
                        self.log(f"   ✅ Ostium 청산 TX 완료!")
                        ostium_success = True
                    else:
                        self.log(f"   ❌ Ostium 청산 실패")

                self.ostium_position = None

            def close_variational():
                nonlocal var_success
                if not self.variational_position:
                    self.log(f"   ⚠️ Variational 포지션 플래그가 없음 (이미 청산되었을 수 있음)")
                    # 플래그가 없어도 실제 포지션이 있는지 확인
                    pos_check = self.variational_client.get_positions_rest()
                    if pos_check.get('success') and abs(pos_check.get('qty', 0)) > 0.000001:
                        self.log(f"   🔍 실제 포지션 발견! 강제 청산 시도...")
                        result = self.variational_client.close_position('BTC', max_retries=3)
                        if result.get('success'):
                            self.log(f"   ✅ Variational 강제 청산 완료!")
                            var_success = True
                        else:
                            self.log(f"   ❌ Variational 강제 청산 실패: {result.get('error')}")
                    else:
                        self.log(f"   ✅ Variational 포지션 없음 (이미 청산됨)")
                        var_success = True  # 이미 청산된 것으로 처리
                    return

                self.log(f"🟢 Variational 청산 시작!")
                result = self.variational_client.close_position('BTC', max_retries=3)

                if result.get('success'):
                    self.log(f"   ✅ Variational 청산 완료!")
                    if result.get('warning'):
                        self.log(f"   ⚠️ 경고: {result.get('warning')}")
                    var_success = True
                else:
                    self.log(f"   ❌ Variational 청산 실패: {result.get('error', 'Unknown error')}")
                    # 실패해도 포지션 상태 확인
                    pos_check = self.variational_client.get_positions_rest()
                    if not pos_check.get('success') or abs(pos_check.get('qty', 0)) < 0.000001:
                        self.log(f"   ✅ 실제로는 포지션이 청산됨 (상태 확인)")
                        var_success = True

                self.variational_position = None

            t1 = threading.Thread(target=close_ostium)
            t2 = threading.Thread(target=close_variational)

            t1.start()
            t2.start()

            t1.join()
            t2.join()

            if ostium_success or var_success:
                self.log("⚡ 청산 완료!")
            else:
                self.log("⚠️ 청산 실패")

            self.reset_position_state()
            self.pending_ostium_order_id = None
            self.update_position_display()

            self.log("💰 손익 계산 중...")
            time.sleep(2)

            final_ostium = self.ostium_client.get_balance()
            final_var = self.variational_client.get_balance()
            final_total = final_ostium + final_var

            profit = final_total - self.initial_total_balance
            self.trade_profits.append(profit)
            self.total_profit = sum(self.trade_profits)

            self.log(f"💵 이번 거래: ${profit:+.2f}")
            self.log(f"💰 누적 손익: ${self.total_profit:+.2f}")

            self.cached_ostium_balance = final_ostium
            self.cached_var_balance = final_var

            self.update_stats()

        except Exception as e:
            self.log(f"❌ 청산 에러: {e}")
            self.ostium_position = None
            self.variational_position = None
            self.reset_position_state()
            self.pending_ostium_order_id = None
            self.update_position_display()

        finally:
            self.is_closing = False

    def close_all_positions(self):
        confirm = messagebox.askyesno("확인", "모든 포지션을 청산하시겠습니까?")
        if confirm:
            threading.Thread(target=self.close_arbitrage_positions, daemon=True).start()

    def toggle_arbitrage(self):
        if not self.ostium_client or not self.variational_client:
            messagebox.showwarning("경고", "먼저 거래소에 연결하세요!")
            return

        if self.is_running:
            self.is_running = False

            def _update():
                if not self.is_shutting_down:
                    self.start_btn.config(text="▶️ 차익거래 시작", bg='#00aa00')

            self.safe_ui_update(_update)
            self.log("⏸️ 차익거래 중지")
        else:
            leverage = float(self.leverage_var.get())
            position_size = float(self.position_size_var.get())
            total_position = position_size * leverage

            confirm = messagebox.askyesno("확인",
                f"차익거래를 시작하시겠습니까?\n\n"
                f"진입 갭: ${self.entry_gap_var.get()}\n"
                f"목표 이익: ${self.target_profit_var.get()}\n"
                f"레버리지: {leverage}x\n"
                f"콜래터럴: ${position_size:.0f}\n"
                f"실제 포지션: ${total_position:.0f}")

            if confirm:
                self.is_running = True

                def _update():
                    if not self.is_shutting_down:
                        self.start_btn.config(text="⏸️ 차익거래 중지", bg='#cc3300')

                self.safe_ui_update(_update)
                self.log("▶️ 차익거래 시작!")

    def update_stats(self):
        def _update():
            if self.is_shutting_down:
                return
            try:
                avg_profit = self.total_profit / self.trade_count if self.trade_count > 0 else 0
                self.stats_label.config(
                    text=f"거래 횟수: {self.trade_count} | 총 손익: ${self.total_profit:+.2f} | 평균: ${avg_profit:+.2f}",
                    fg='#00ff00' if self.total_profit >= 0 else '#ff0000'
                )
            except:
                pass

        self.safe_ui_update(_update)

    def update_position_display(self):
        def _update():
            if self.is_shutting_down:
                return
            try:
                self.position_text.delete('1.0', 'end')

                if self.ostium_position:
                    if self.ostium_position.get('pending'):
                        direction = "LONG" if not self.cached_is_ostium_short else "SHORT"
                        self.position_text.insert('end', f"🔵 Ostium: {direction} ⚡\n")
                    else:
                        direction = "LONG" if self.ostium_position.get('buy') else "SHORT"
                        self.position_text.insert('end', f"🔵 Ostium: {direction} ✅\n")
                elif self.pending_ostium_order_id:
                    self.position_text.insert('end', f"🔵 Ostium: TX 전송 중...\n")
                else:
                    self.position_text.insert('end', f"🔵 Ostium: 포지션 없음\n")

                if self.variational_position:
                    var_dir = "LONG" if self.cached_var_qty > 0 else "SHORT"
                    self.position_text.insert('end', f"🟢 Variational: {var_dir} ✅\n")
                else:
                    self.position_text.insert('end', f"🟢 Variational: 포지션 없음\n")
            except:
                pass

        self.safe_ui_update(_update)


if __name__ == '__main__':
    try:
        print("\n" + "="*60)
        print("🚀 차익거래 봇 V3 시작")
        print("="*60)

        print("\n🔍 환경 변수 검증 중...")
        errors, warnings = validate_environment()

        if warnings:
            print("\n⚠️  경고:")
            for warning in warnings:
                print(f"   {warning}")

        if errors:
            print("\n" + "="*60)
            print("❌ 환경 변수 설정 오류")
            print("="*60)
            for error in errors:
                print(f"   {error}")
            print("="*60 + "\n")
            time.sleep(5)
            os._exit(1)

        print("✅ 환경 변수 검증 완료!")

        print("\n📡 설정 서버에서 API 설정 로드 중...")
        try:
            API_CONFIG = load_api_config()

            # 🔄 설정 갱신 콜백 등록
            config_client = get_config_client()
            if config_client:
                def update_api_config(new_config):
                    global API_CONFIG
                    API_CONFIG = new_config

                config_client.on_config_update = update_api_config
                print(f"   🔄 자동 갱신 활성화!")
        except Exception as e:
            print("\n" + "="*60)
            print("❌ 설정 서버 연결 실패")
            print("="*60)
            print(f"   에러: {e}")
            print("="*60 + "\n")
            time.sleep(5)
            os._exit(1)

        print("\n✅ API 설정 로드 완료!")
        print(f"   버전: {API_CONFIG.get('version', 'unknown')}")
        print(f"   하트비트: {API_CONFIG.get('heartbeat', {}).get('interval_seconds', 60)}초")
        print("="*60)

        print("\n🎨 GUI 시작 중...\n")
        root = tk.Tk()
        app = ArbitrageGUI(root)

        def check_connections():
            if not app.is_shutting_down:
                if not app.ostium_client:
                    print("\n❌ Ostium 연결 실패")
                    app.shutdown()

                if not app.variational_client:
                    print("\n❌ Variational 연결 실패")
                    app.shutdown()

                print("✅ 모든 연결 성공!\n")
                print("="*60)
                print("💡 사용법:")
                print("   1. 상단에서 연결 상태 확인")
                print("   2. 차익거래 설정 조정")
                print("   3. '▶️ 차익거래 시작' 버튼 클릭")
                print("="*60 + "\n")

        root.after(3000, check_connections)

        try:
            root.mainloop()
        except KeyboardInterrupt:
            print("\n\n⏹️  사용자가 봇을 중지했습니다.")
            app.shutdown()
        except Exception as e:
            print(f"Mainloop 에러: {e}")
            app.shutdown()
        finally:
            # 마지막 정리
            if not app.is_shutting_down:
                app.shutdown()

            # 강제 종료
            print("\n💥 프로그램 강제 종료")
            os._exit(0)

    except KeyboardInterrupt:
        print("\n\n⏹️  사용자가 봇을 중지했습니다.")
        os._exit(0)

    except Exception as e:
        print("\n" + "="*60)
        print("❌ 예상치 못한 에러 발생")
        print("="*60)
        print(f"   에러: {e}")
        print("="*60 + "\n")

        import traceback
        traceback.print_exc()

        time.sleep(2)
        os._exit(1)
