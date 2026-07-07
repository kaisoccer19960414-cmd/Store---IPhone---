from flask import Flask, request, jsonify, render_template_string, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from functools import wraps
from urllib.parse import urlparse
import os
import re
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

# Vercelのプレビューデプロイは "store-iphone-portfolio-git-〇〇-ユーザー名.vercel.app" のような
# 規則的な名前になるため、正規表現で「store-iphone-portfolioから始まり、.vercel.appで終わる」
# URLはまとめて許可する(プレビューURLをpushのたびに手動追加しなくて済むようにする)
PREVIEW_ORIGIN_PATTERN = re.compile(r'^https://store-iphone-portfolio.*\.vercel\.app$')

# ローカルでのLive Server等でのテストも許可する(本番URL + ローカルの定番ポートいくつか)
LOCAL_TEST_ORIGINS = [
    'http://127.0.0.1:5500',
    'http://localhost:5500',
    'http://127.0.0.1:5501',
    'http://localhost:5501',
]
CORS(app, origins=[PREVIEW_ORIGIN_PATTERN, *LOCAL_TEST_ORIGINS])

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
    is_json_request = request.is_json  # fetch経由(PWA内で完結させたい場合)かどうか

    if request.method == 'POST':
        if is_locked_out(client_ip):
            error_msg = '試行回数が多すぎます。5分ほど待ってから再度お試しください。'
            if is_json_request:
                return jsonify({'error': error_msg}), 429
            return render_template_string(LOGIN_PAGE, error=error_msg, next_url=next_url), 429

        if is_json_request:
            passcode = (request.get_json(silent=True) or {}).get('passcode', '')
        else:
            passcode = request.form.get('passcode') or ''

        if APP_PASSCODE and secrets_module.compare_digest(passcode, APP_PASSCODE):
            reset_attempts(client_ip)
            token = serializer.dumps({'authenticated': True})

            if is_json_request:
                return jsonify({'token': token})  # ページ遷移せず、トークンだけ返す

            if is_safe_redirect(next_url):
                return redirect(add_token_to_url(next_url, token))
            return jsonify({'token': token})

        register_failed_attempt(client_ip)
        if is_json_request:
            return jsonify({'error': 'パスコードが違います'}), 401
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
    offset = request.args.get('offset', default=0, type=int)
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers=SUPABASE_HEADERS,
        params={
            # select= の中で「authors(name)」と書くと、外部キーを辿ってJOINしてくれる
            'select': 'id,question,author_id,authors(name)',
            'order': 'id.desc',
            'limit': limit,
            'offset': offset
        }
    )
    return jsonify(res.json()), res.status_code


@app.route('/authors', methods=['GET'])
def get_all_authors():
    """投稿者の一覧(選択肢に使う。閲覧は誰でも可)"""
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/authors',
        headers=SUPABASE_HEADERS,
        params={'select': 'id,name', 'order': 'name.asc'}
    )
    return jsonify(res.json()), res.status_code


@app.route('/quiz_data', methods=['POST'])
@require_login
def create_quiz():
    body = request.get_json(silent=True)
    if not body or not body.get('question') or not body['question'].strip():
        return jsonify({'error': 'question is required'}), 400

    payload = {'question': body['question'].strip()}
    if body.get('author_id'):
        payload['author_id'] = body['author_id']

    res = requests.post(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers={**SUPABASE_HEADERS, 'Prefer': 'return=representation'},
        json=payload
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