from flask import Flask, request, jsonify, session, render_template_string, redirect
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
from urllib.parse import urlparse
import os
import requests

load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False

# セッションを暗号署名するための秘密鍵(これも環境変数で管理する)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'dev-only-fallback-key')

# クロスサイト(vercel.app → onrender.com)でもCookieを送れるようにする設定
app.config.update(
    SESSION_COOKIE_SAMESITE='None',  # 別ドメインからのリクエストでもCookieを許可
    SESSION_COOKIE_SECURE=True,      # HTTPS通信でのみCookieを送る(本番では必須)
)

# フロントのVercelドメインを名指しで許可し、Cookie付きリクエストを許可する
FRONTEND_ORIGIN = os.environ.get('FRONTEND_ORIGIN', 'https://store-iphone-unko.vercel.app')
CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])

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
  {% if success %}<p style="color: green;">ログインしました。このタブは閉じて、元のサイトに戻ってください。</p>{% endif %}
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


@app.route('/login', methods=['GET', 'POST'])
def login():
    # ?next=... で「ログイン後にどこへ戻るか」を受け取る
    next_url = request.values.get('next', '')

    if request.method == 'POST':
        passcode = request.form.get('passcode')
        if passcode == APP_PASSCODE:
            session['authenticated'] = True
            session.permanent = True

            if is_safe_redirect(next_url):
                return redirect(next_url)  # ← 元のページへ自動で戻す
            return render_template_string(LOGIN_PAGE, success=True, next_url=next_url)

        return render_template_string(LOGIN_PAGE, error='パスコードが違います', next_url=next_url)

    return render_template_string(LOGIN_PAGE, next_url=next_url)


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('authenticated', None)
    return jsonify({'logged_out': True})


def require_login(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({'error': 'ログインが必要です'}), 401
        return f(*args, **kwargs)
    return wrapper


@app.route('/quiz_data', methods=['GET'])
def get_all_quizzes():
    # 閲覧(GET)は誰でも自由にできるようにする(ログイン不要)
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