# arbitrage_bot_telegram.py
# 텔레그램 봇 버전 - Railway 배포용
import asyncio
import json
import threading
import time
from datetime import datetime
import websocket
import ssl
from decimal import Decimal, ROUND_DOWN
from queue import Queue
import os
import sys
from dotenv import load_dotenv

# 텔레그램 봇 라이브러리
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# 기존 모듈 import
from curl_cffi import requests
from ostium_python_sdk import OstiumSDK, NetworkConfig
from web3 import Account
from eth_account.messages import encode_defunct
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
        'VARIATIONAL_PRIVATE_KEY': 'Variational Private Key',
        'TELEGRAM_BOT_TOKEN': '텔레그램 봇 토큰'
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


# trader_with_server.py에서 클래스들을 import
# __main__ 블록이 실행되지 않도록 주의
import importlib.util
trader_path = os.path.join(os.path.dirname(__file__), "trader_with_server.py")
spec = importlib.util.spec_from_file_location("trader_module", trader_path)
trader_module = importlib.util.module_from_spec(spec)

# API_CONFIG를 먼저 설정한 후 모듈 로드
def load_trader_classes():
    """trader_with_server.py에서 클래스 로드 (API_CONFIG 설정 후)"""
    global OstiumClient, VariationalClient, VariationalWebSocket, VariationalPriceWebSocket
    # API_CONFIG를 trader_module에 설정
    trader_module.API_CONFIG = API_CONFIG
    spec.loader.exec_module(trader_module)
    OstiumClient = trader_module.OstiumClient
    VariationalClient = trader_module.VariationalClient
    VariationalWebSocket = trader_module.VariationalWebSocket
    VariationalPriceWebSocket = trader_module.VariationalPriceWebSocket


class ArbitrageTelegramBot:
    """텔레그램 봇 버전 차익거래 봇"""
    
    def __init__(self):
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
        
        self.cached_ostium_balance = 0
        self.cached_var_balance = 0
        
        self.cached_ostium_entry = None
        self.cached_var_entry = None
        self.cached_is_ostium_short = None
        self.cached_var_qty = 0
        self.ostium_entry_timestamp = 0
        
        # 설정값 (텔레그램으로 변경 가능)
        self.entry_gap = 20.0
        self.target_profit = 15.0
        self.leverage = 3.0
        self.position_size = 300.0
        
        self.current_ui_data = {
            'ostium_mid': 0,
            'var_mark': 0,
            'gap': 0,
            'gap_pct': 0,
            'direction': '',
            'display_price': ''
        }
        
        self.is_shutting_down = False
        self.threads = []
        self.log_queue = Queue()
        
        # 텔레그램 봇 애플리케이션
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        if not self.bot_token:
            raise Exception("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다!")
        
        self.app = Application.builder().token(self.bot_token).build()
        self.setup_handlers()
        
        # 설정 클라이언트 종료 콜백 등록
        config_client = get_config_client()
        if config_client:
            config_client.add_shutdown_callback(self.emergency_shutdown)
    
    def setup_handlers(self):
        """텔레그램 명령어 핸들러 설정"""
        self.app.add_handler(CommandHandler("start", self.start_command))
        self.app.add_handler(CommandHandler("status", self.status_command))
        self.app.add_handler(CommandHandler("start_trading", self.start_trading_command))
        self.app.add_handler(CommandHandler("stop_trading", self.stop_trading_command))
        self.app.add_handler(CommandHandler("settings", self.settings_command))
        self.app.add_handler(CommandHandler("balance", self.balance_command))
        self.app.add_handler(CommandHandler("positions", self.positions_command))
        self.app.add_handler(CommandHandler("close_all", self.close_all_command))
        self.app.add_handler(CommandHandler("stats", self.stats_command))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """봇 시작 명령어"""
        welcome_text = """
🤖 **Ostium ↔️ Variational 차익거래 봇**

사용 가능한 명령어:
/start - 시작 메시지
/status - 현재 상태 확인
/start_trading - 차익거래 시작
/stop_trading - 차익거래 중지
/settings - 설정 변경
/balance - 잔고 확인
/positions - 포지션 확인
/close_all - 모든 포지션 청산
/stats - 거래 통계

봇이 자동으로 가격을 모니터링하고 차익거래 기회를 찾습니다.
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """상태 확인"""
        status_text = f"""
📊 **현재 상태**

🔵 Ostium: {'✅ 연결됨' if self.ostium_client else '❌ 연결 안됨'}
🟢 Variational: {'✅ 연결됨' if self.variational_client else '❌ 연결 안됨'}
💓 서버: {'✅ 연결됨' if _server_alive_check() else '❌ 연결 끊김'}

⚡ 차익거래: {'🟢 실행 중' if self.is_running else '🔴 중지됨'}

📈 현재 가격:
• Ostium: ${self.current_ui_data['ostium_mid']:,.2f}
• Variational: ${self.current_ui_data['var_mark']:,.2f}
• 갭: ${self.current_ui_data['gap']:.2f} ({self.current_ui_data['gap_pct']:.4f}%)

💰 잔고:
• Ostium: ${self.cached_ostium_balance:.2f}
• Variational: ${self.cached_var_balance:.2f}
        """
        await update.message.reply_text(status_text, parse_mode='Markdown')
    
    async def start_trading_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """차익거래 시작"""
        if not self.ostium_client or not self.variational_client:
            await update.message.reply_text("❌ 먼저 거래소에 연결하세요!")
            return
        
        if self.is_running:
            await update.message.reply_text("⚠️ 이미 실행 중입니다!")
            return
        
        self.is_running = True
        await update.message.reply_text(
            f"✅ 차익거래 시작!\n\n"
            f"설정:\n"
            f"• 진입 갭: ${self.entry_gap}\n"
            f"• 목표 이익: ${self.target_profit}\n"
            f"• 레버리지: {self.leverage}x\n"
            f"• 포지션 크기: ${self.position_size}"
        )
        self.log("▶️ 차익거래 시작!")
    
    async def stop_trading_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """차익거래 중지"""
        if not self.is_running:
            await update.message.reply_text("⚠️ 실행 중이 아닙니다!")
            return
        
        self.is_running = False
        await update.message.reply_text("⏸️ 차익거래 중지됨")
        self.log("⏸️ 차익거래 중지")
    
    async def settings_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """설정 변경"""
        keyboard = [
            [InlineKeyboardButton("진입 갭 변경", callback_data="set_entry_gap")],
            [InlineKeyboardButton("목표 이익 변경", callback_data="set_target_profit")],
            [InlineKeyboardButton("레버리지 변경", callback_data="set_leverage")],
            [InlineKeyboardButton("포지션 크기 변경", callback_data="set_position_size")],
            [InlineKeyboardButton("현재 설정 보기", callback_data="view_settings")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⚙️ 설정 변경\n\n현재 설정을 보려면 '현재 설정 보기'를 선택하세요.",
            reply_markup=reply_markup
        )
    
    async def balance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """잔고 확인"""
        if self.ostium_client:
            ostium_balance = self.ostium_client.get_balance()
            self.cached_ostium_balance = ostium_balance
        if self.variational_client:
            var_balance = self.variational_client.get_balance()
            self.cached_var_balance = var_balance
        
        total = self.cached_ostium_balance + self.cached_var_balance
        
        await update.message.reply_text(
            f"💰 **잔고 정보**\n\n"
            f"🔵 Ostium: ${self.cached_ostium_balance:.2f}\n"
            f"🟢 Variational: ${self.cached_var_balance:.2f}\n"
            f"📊 총합: ${total:.2f}",
            parse_mode='Markdown'
        )
    
    async def positions_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """포지션 확인"""
        pos_text = "📈 **현재 포지션**\n\n"
        
        if self.ostium_position:
            if self.ostium_position.get('pending'):
                direction = "LONG" if not self.cached_is_ostium_short else "SHORT"
                pos_text += f"🔵 Ostium: {direction} ⚡ (대기 중)\n"
            else:
                direction = "LONG" if self.ostium_position.get('buy') else "SHORT"
                pos_text += f"🔵 Ostium: {direction} ✅\n"
        else:
            pos_text += "🔵 Ostium: 포지션 없음\n"
        
        if self.variational_position:
            var_dir = "LONG" if self.cached_var_qty > 0 else "SHORT"
            pos_text += f"🟢 Variational: {var_dir} ✅\n"
        else:
            pos_text += "🟢 Variational: 포지션 없음\n"
        
        await update.message.reply_text(pos_text, parse_mode='Markdown')
    
    async def close_all_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """모든 포지션 청산"""
        if not self.ostium_position and not self.variational_position:
            await update.message.reply_text("⚠️ 청산할 포지션이 없습니다!")
            return
        
        await update.message.reply_text("⚡ 청산 시작...")
        threading.Thread(target=self.close_arbitrage_positions, daemon=True).start()
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """거래 통계"""
        avg_profit = self.total_profit / self.trade_count if self.trade_count > 0 else 0
        
        await update.message.reply_text(
            f"📊 **거래 통계**\n\n"
            f"거래 횟수: {self.trade_count}\n"
            f"총 손익: ${self.total_profit:+.2f}\n"
            f"평균 손익: ${avg_profit:+.2f}",
            parse_mode='Markdown'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """버튼 콜백 처리"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "view_settings":
            await query.edit_message_text(
                f"⚙️ **현재 설정**\n\n"
                f"진입 갭: ${self.entry_gap}\n"
                f"목표 이익: ${self.target_profit}\n"
                f"레버리지: {self.leverage}x\n"
                f"포지션 크기: ${self.position_size}",
                parse_mode='Markdown'
            )
        elif query.data.startswith("set_"):
            await query.edit_message_text(
                f"💬 새 값을 입력하세요.\n\n"
                f"예: /set_{query.data.replace('set_', '')} 25"
            )
    
    def log(self, message):
        """로그 출력"""
        self.log_queue.put(message)
        print(f"[LOG] {message}")
    
    def auto_connect(self):
        """자동 연결"""
        try:
            private_key = os.getenv('OSTIUM_PRIVATE_KEY')
            rpc_url = os.getenv('OSTIUM_RPC_URL') or os.getenv('RPC_URL')
            
            if private_key and rpc_url:
                self.log("🔵 Ostium 연결 중...")
                self.ostium_client = OstiumClient(private_key, rpc_url, use_mainnet=True)
                self.log("✅ Ostium 연결 성공!")
            else:
                self.log("⚠️ Ostium .env 설정 필요")
            
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
            else:
                self.log("⚠️ Variational .env 설정 필요")
            
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
                    position_size = self.position_size
                    leverage = self.leverage
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
        # 진입
        if (not self.ostium_position and
            not self.variational_position and
            not self.pending_ostium_order_id and
            not self.is_closing and
            not self.is_executing):
            
            if abs(gap) >= self.entry_gap:
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
        elif (self.ostium_position and self.variational_position) and not self.is_closing:
            ostium_pnl, var_pnl, total_pnl = self.get_position_pnl()
            
            current_time = time.time()
            
            if not hasattr(self, 'last_status_log') or current_time - self.last_status_log > 0.5:
                self.last_status_log = current_time
                status = "🟢" if total_pnl < self.target_profit else "🔴"
                remaining = self.target_profit - total_pnl
                self.log(f"{status} O:${ostium_pnl:+.2f} V:${var_pnl:+.2f} = ${total_pnl:+.2f} | 목표까지: ${remaining:.2f}")
            
            if total_pnl >= self.target_profit:
                self.log(f"🎯 즉시 청산! 총 이익: ${total_pnl:.2f}")
                threading.Thread(target=self.close_arbitrage_positions, daemon=True).start()
    
    def execute_arbitrage(self, ostium_short, ostium_entry_price, var_entry_price, var_quote):
        """⚡⚡⚡ 차익거래 실행"""
        if self.is_executing:
            return
        
        config_client = get_config_client()
        if config_client:
            if not config_client.verify_before_trade():
                self.log("❌ 거래 검증 실패 - 거래 중단")
                return
        
        self.is_executing = True
        position_size = self.position_size
        leverage = self.leverage
        
        try:
            ostium_balance = self.ostium_client.get_balance()
            var_balance = self.variational_client.get_balance()
            self.initial_total_balance = ostium_balance + var_balance
            
            self.log(f"💰 진입 전 잔고: ${self.initial_total_balance:.2f}")
            
            if ostium_balance < position_size:
                self.log(f"❌ Ostium 잔고 부족!")
                self.is_executing = False
                return
            
            # Variational 수량 계산
            var_price = float(var_quote['mark_price'])
            var_position_value = position_size * leverage
            var_qty = var_position_value / var_price
            
            min_tick = Decimal('0.000001')
            var_qty_decimal = Decimal(str(var_qty))
            var_qty_rounded = (var_qty_decimal / min_tick).quantize(Decimal('1'), rounding=ROUND_DOWN) * min_tick
            var_qty = float(var_qty_rounded)
            
            actual_var_position = var_qty * var_price
            actual_ostium_collateral = (var_qty * ostium_entry_price) / leverage
            actual_ostium_collateral = round(actual_ostium_collateral, 2)
            
            self.log(f"📊 Variational 수량: {var_qty:.6f}")
            self.log(f"📊 포지션 크기: ${actual_var_position:.2f}")
            self.log(f"📊 Ostium 콜래터럴: ${actual_ostium_collateral:.2f}")
            
            self.cached_ostium_entry = ostium_entry_price
            self.cached_var_entry = var_entry_price
            self.cached_is_ostium_short = ostium_short
            self.ostium_entry_timestamp = time.time()
            
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
                    collateral=actual_ostium_collateral,
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
            
            threading.Thread(target=self.track_ostium_position_background, args=(order_id,), daemon=True).start()
            
            self.trade_count += 1
            self.cached_ostium_balance = ostium_balance - actual_ostium_collateral
            
        except Exception as e:
            self.log(f"❌ 차익거래 에러: {e}")
            self.reset_position_state()
        finally:
            self.is_executing = False
    
    def track_ostium_position_background(self, order_id):
        """⚡ Ostium 포지션 추적"""
        self.log(f"🔍 Ostium 포지션 추적 시작!")
        
        start_time = time.time()
        while time.time() - start_time < 15:
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
                    return
                
                self.log(f"🟢 Variational 청산 시작!")
                result = self.variational_client.close_position('BTC', max_retries=2)
                if result.get('success'):
                    self.log(f"   ✅ Variational 청산 완료!")
                    var_success = True
                else:
                    self.log(f"   ❌ Variational 청산 실패")
                
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
        
        except Exception as e:
            self.log(f"❌ 청산 에러: {e}")
            self.ostium_position = None
            self.variational_position = None
            self.reset_position_state()
            self.pending_ostium_order_id = None
        
        finally:
            self.is_closing = False
    
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
    
    def emergency_shutdown(self):
        """⚡ 긴급 종료"""
        print("\n" + "="*70)
        print("🚨 서버 연결 끊김 - 긴급 종료")
        print("="*70)
        
        self.is_shutting_down = True
        os._exit(1)
    
    def run(self):
        """봇 실행"""
        # 연결 시작
        threading.Thread(target=self.auto_connect, daemon=True).start()
        time.sleep(2)
        
        # 모니터링 스레드 시작
        t1 = threading.Thread(target=self.ultra_fast_price_monitor_loop, daemon=True)
        t1.start()
        self.threads.append(t1)
        
        t2 = threading.Thread(target=self.balance_monitor_loop, daemon=True)
        t2.start()
        self.threads.append(t2)
        
        # 텔레그램 봇 시작
        print("🤖 텔레그램 봇 시작 중...")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    try:
        print("\n" + "="*60)
        print("🚀 차익거래 봇 텔레그램 버전 시작")
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
        print("="*60)
        
        # API_CONFIG 설정 후 클래스 로드
        print("\n📦 거래소 클래스 로드 중...")
        load_trader_classes()
        print("✅ 클래스 로드 완료!")
        
        print("\n🤖 텔레그램 봇 초기화 중...\n")
        bot = ArbitrageTelegramBot()
        bot.run()
    
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

