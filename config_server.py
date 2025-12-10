"""
설정 서버 - 차익거래 봇 API 설정 제공
Flask 기반 REST API 서버
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import uuid
from datetime import datetime
import time
from functools import wraps

app = Flask(__name__)
CORS(app)  # CORS 허용 (필요시)

# 서버 설정
SERVER_TOKEN = os.getenv('SERVER_TOKEN', 'your-secret-token-here')  # .env에서 설정하거나 하드코딩
# Railway는 PORT 환경 변수를 자동으로 설정하므로 그것을 사용
PORT = int(os.getenv('PORT', 5001))  # Railway에서는 자동 설정, 로컬에서는 5001

# 세션 관리 (실제 운영에서는 DB 사용 권장)
active_sessions = {}

# API 설정 (실제 API URL로 변경 필요)
API_CONFIG = {
    "version": "3.1",
    "config_version": 1,
    "last_updated": datetime.now().isoformat(),
    "heartbeat": {
        "required": True,
        "interval_seconds": 60
    },
    "ostium": {
        # Ostium 가격 API URL
        # 형식: GET {price_api_url}?asset=BTCUSD
        # 응답: {"bid": number, "ask": number, "mid": number}
        "price_api_url": "https://metadata-backend.ostium.io/PricePublish/latest-price"
    },
    "variational": {
        "base_url": "https://omni.variational.io",
        "endpoints": {
            "auth_generate_signing": "/api/auth/generate_signing_data",
            "auth_login": "/api/auth/login",
            "quotes_indicative": "/api/quotes/indicative",
            "quotes_accept": "/api/quotes/accept",
            "positions": "/api/positions"
        },
        "ws": {
            "portfolio": "wss://omni.variational.io/ws/portfolio",
            "price": "wss://omni.variational.io/ws/price"
        }
    }
}


def require_auth(f):
    """인증 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'error': 'Authorization header missing'}), 401
        
        try:
            token = auth_header.split(' ')[1]  # "Bearer {token}" 형식
        except IndexError:
            return jsonify({'error': 'Invalid authorization format'}), 401
        
        if token != SERVER_TOKEN:
            return jsonify({'error': 'Invalid token'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'active_sessions': len(active_sessions)
    })


@app.route('/config', methods=['GET'])
@require_auth
def get_config():
    """설정 조회"""
    # 세션 ID 생성 (없으면 새로 생성)
    session_id = str(uuid.uuid4())
    
    # 세션 저장
    active_sessions[session_id] = {
        'created_at': time.time(),
        'last_ping': time.time(),
        'ping_count': 0
    }
    
    # 설정 반환
    return jsonify({
        'config': API_CONFIG,
        'session_id': session_id
    })


@app.route('/ping', methods=['POST'])
@require_auth
def ping():
    """하트비트 핑"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    
    # 세션 확인
    if session_id not in active_sessions:
        return jsonify({'error': 'Invalid session_id'}), 401
    
    # 세션 업데이트
    session = active_sessions[session_id]
    session['last_ping'] = time.time()
    session['ping_count'] = session.get('ping_count', 0) + 1
    
    # 응답
    return jsonify({
        'alive': True,
        'config_version': API_CONFIG['config_version'],
        'timestamp': datetime.now().isoformat()
    })


@app.route('/verify', methods=['POST'])
@require_auth
def verify():
    """거래 전 검증"""
    data = request.get_json()
    session_id = data.get('session_id')
    
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400
    
    # 세션 확인
    if session_id not in active_sessions:
        return jsonify({
            'verified': False,
            'error': 'Invalid session_id',
            'action': 'restart'
        }), 401
    
    # 세션 유효성 확인 (마지막 핑이 5분 이상 지났으면 만료)
    session = active_sessions[session_id]
    time_since_last_ping = time.time() - session['last_ping']
    
    if time_since_last_ping > 300:  # 5분
        return jsonify({
            'verified': False,
            'error': 'Session expired',
            'action': 'restart'
        }), 401
    
    # 검증 성공
    return jsonify({
        'verified': True,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/admin/config', methods=['PUT'])
@require_auth
def update_config():
    """설정 업데이트 (관리자용)"""
    global API_CONFIG
    
    new_config = request.get_json()
    
    if not new_config:
        return jsonify({'error': 'Config data required'}), 400
    
    # 설정 버전 증가
    API_CONFIG['config_version'] = API_CONFIG.get('config_version', 0) + 1
    API_CONFIG['last_updated'] = datetime.now().isoformat()
    
    # 새 설정 병합
    API_CONFIG.update(new_config)
    
    return jsonify({
        'success': True,
        'config_version': API_CONFIG['config_version'],
        'message': 'Config updated successfully'
    })


@app.route('/admin/sessions', methods=['GET'])
@require_auth
def list_sessions():
    """활성 세션 목록 (관리자용)"""
    sessions_info = []
    current_time = time.time()
    
    for session_id, session_data in active_sessions.items():
        sessions_info.append({
            'session_id': session_id[:16] + '...',
            'created_at': datetime.fromtimestamp(session_data['created_at']).isoformat(),
            'last_ping': datetime.fromtimestamp(session_data['last_ping']).isoformat(),
            'ping_count': session_data['ping_count'],
            'age_seconds': int(current_time - session_data['created_at']),
            'time_since_last_ping': int(current_time - session_data['last_ping'])
        })
    
    return jsonify({
        'active_sessions': len(active_sessions),
        'sessions': sessions_info
    })


def cleanup_old_sessions():
    """오래된 세션 정리 (백그라운드 작업)"""
    import threading
    
    def cleanup():
        while True:
            time.sleep(300)  # 5분마다
            current_time = time.time()
            expired_sessions = []
            
            for session_id, session_data in active_sessions.items():
                if current_time - session_data['last_ping'] > 600:  # 10분 이상 핑 없으면
                    expired_sessions.append(session_id)
            
            for session_id in expired_sessions:
                del active_sessions[session_id]
                print(f"🧹 세션 정리: {session_id[:16]}...")
    
    thread = threading.Thread(target=cleanup, daemon=True)
    thread.start()


if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 설정 서버 시작")
    print("="*60)
    print(f"📡 포트: {PORT}")
    print(f"🔐 토큰: {SERVER_TOKEN[:20]}...")
    print(f"📋 설정 버전: v{API_CONFIG['config_version']}")
    print("="*60 + "\n")
    
    # 세션 정리 시작
    cleanup_old_sessions()
    
    # 서버 실행
    # Railway에서는 PORT 환경 변수를 자동으로 설정
    app.run(
        host='0.0.0.0',
        port=PORT,
        debug=False
    )

