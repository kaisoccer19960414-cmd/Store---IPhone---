from flask import Flask, request, jsonify, render_template_string, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
from urllib.parse import urlparse
import os
import time
import secrets as secrets_module
import requests

load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False

SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-only-fallback-key')
serializer = URLSafeTimedSerializer(SECRET_KEY)
TOKEN_MAX_AGE = 60 * 60 * 24 * 7  # トークンの有効期限: 7日間

# --- ログイン試行回数の制限(総当たり攻撃対策) ---
# IPアドレスごとに「失敗回数」と「ロックが解除される時刻」を記録する
# (ポートフォリオ規模の簡易実装。本格運用ならRedis等の永続ストレージを使う)
LOGIN_ATTEMPTS = {}
MAX_ATTEMPTS = 5          # この回数間違えたら
LOCKOUT_SECONDS = 300     # 5分間ロックする


def is_locked_out(ip):
    record = LOGIN_ATTEMPTS.get(ip)
    if not record:
        return False
    if record['count'] >= MAX_ATTEMPTS and time.time() < record['locked_until']:
        return True
    return False


def register_failed_attempt(ip):
    record = LOGIN_ATTEMPTS.setdefault(ip, {'count': 0, 'locked_until': 0})
    record['count'] += 1
    if record['count'] >= MAX_ATTEMPTS:
        record['locked_until'] = time.time() + LOCKOUT_SECONDS


def reset_attempts(ip):
    LOGIN_ATTEMPTS.pop(ip, None)


# Safari等のクロスサイトCookie制限を回避するため、Cookieには頼らずトークン方式にする
FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN', 'https://store-iphone-portfolio.vercel.app')
CORS(app, origins=[FRONTEND_ORIGIN])

APP_PASSCODE = os.environ.get('APP_PASSCODE')
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

SUPABASE_HEADERS = {
    'apikey': SUPABASE_SERVICE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
    'Content-Type': 'application/json',
}

LOGIN_PAGE = """
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"><title>管理者ログイン</title></head>
<body style="font-family: sans-serif; max-width: 400px; margin: 80px auto;">
  <h2>管理者ログイン</h2>
  <form method="POST">
    <input type="hidden" name="next" value="{{ next_url }}">
    <input type="password" name="passcode" placeholder="パスコード" autofocus
           style="font-size: 1.2em; padding: 8px; width: 100%; box-sizing: border-box;">
    <button type="submit" style="margin-top: 10px; padding: 8px 20px;">ログイン</button>
  </form>
  {% if error %}<p style="color: red;">{{ error }}</p>{% endif %}
</body>
</html>
"""


def is_safe_redirect(url):
    """許可したフロントのドメインへのリダイレクトだけを許可する(オープンリダイレクト対策)"""
    if not url:
        return False
    parsed = urlparse(url)
    allowed = urlparse(FRONTEND_ORIGIN)
    return parsed.scheme == allowed.scheme and parsed.netloc == allowed.netloc


def add_token_to_url(url, token):
    """URLの末尾に ?token=... (または &token=...) を付け足す"""
    separator = '&' if '?' in url else '?'
    return f'{url}{separator}token={token}'


@app.route('/login', methods=['GET', 'POST'])
def login():
    next_url = request.values.get('next', '')
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if request.method == 'POST':
        if is_locked_out(client_ip):
            return render_template_string(
                LOGIN_PAGE,
                error='試行回数が多すぎます。5分ほど待ってから再度お試しください。',
                next_url=next_url
            ), 429
        passcode = request.form.get('passcode') or ''
        # secrets.compare_digest: 文字列比較にかかる時間を一定にし、タイミング攻撃を防ぐ
        if APP_PASSCODE and secrets_module.compare_digest(passcode, APP_PASSCODE):
            reset_attempts(client_ip)  # ログイン成功したので失敗カウントをリセット
            token = serializer.dumps({'authenticated': True})

            if is_safe_redirect(next_url):
                return redirect(add_token_to_url(next_url, token))
            return jsonify({'token': token})

        register_failed_attempt(client_ip)  # 失敗を記録
        return render_template_string(LOGIN_PAGE, error='パスコードが違います', next_url=next_url)

    return render_template_string(LOGIN_PAGE, next_url=next_url)


def verify_token(token):
    try:
        data = serializer.loads(token, max_age=TOKEN_MAX_AGE)
        return data.get('authenticated') is True
    except (BadSignature, SignatureExpired):
        return False


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else None

        if not token or not verify_token(token):
            return jsonify({'error': 'ログインが必要です'}), 401
        return f(*args, **kwargs)
    return wrapper


@app.route('/quiz_data', methods=['GET'])
def get_all_quizzes():
    limit = request.args.get('limit', default=20, type=int)
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers=SUPABASE_HEADERS,
        params={'order': 'id.desc', 'limit': limit}
    )
    return jsonify(res.json()), res.status_code


@app.route('/quiz_data', methods=['POST'])
@require_login
def create_quiz():
    body = request.get_json(silent=True)
    if not body or not body.get('question') or not body['question'].strip():
        return jsonify({'error': 'question is required'}), 400

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation'},
        json={'question': body['question'].strip()}
    )
    return jsonify(res.json()), res.status_code


@app.route('/quiz_data/<int:quiz_id>', methods=['PATCH'])
@require_login
def update_quiz(quiz_id):
    body = request.get_json(silent=True)
    if not body or not body.get('question') or not body['question'].strip():
        return jsonify({'error': 'question is required'}), 400

    res = requests.patch(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation'},
        params={'id': f'eq.{quiz_id}'},
        json={'question': body['question'].strip()}
    )
    return jsonify(res.json()), res.status_code


@app.route('/quiz_data/<int:quiz_id>', methods=['DELETE'])
@require_login
def delete_quiz(quiz_id):
    res = requests.delete(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers=SUPABASE_HEADERS,
        params={'id': f'eq.{quiz_id}'}
    )
    return jsonify({'deleted': quiz_id}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)