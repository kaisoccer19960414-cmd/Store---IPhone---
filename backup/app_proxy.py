from flask import Flask, request, jsonify, session, render_template_string
from flask_cors import CORS
from dotenv import load_dotenv
from functools import wraps
import os
import requests

load_dotenv()

app = Flask(__name__)
app.json.ensure_ascii = False
CORS(app)

# --- 環境変数から読み込む(コードに直接書かない!) ---
# Renderにデプロイする時、これらは「環境変数」としてダッシュボードで設定する
APP_PASSCODE = os.environ.get('APP_PASSCODE')          
SUPABASE_URL = os.environ.get('SUPABASE_URL')          
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')  

SUPABASE_HEADERS = {
    'apikey': SUPABASE_SERVICE_KEY,
    'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
    'Content-Type': 'application/json',
}


def check_passcode():
    """リクエストヘッダーのパスコードが正しいか確認する"""
    given = request.headers.get('X-App-Passcode')
    return given == APP_PASSCODE


@app.route('/quiz_data', methods=['GET'])
def get_all_quizzes():
    if not check_passcode():
        return jsonify({'error': 'パスコードが違います'}), 401

    limit = request.args.get('limit', default=20, type=int)
    res = requests.get(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers=SUPABASE_HEADERS,
        params={'order': 'id.desc', 'limit': limit}
    )
    return jsonify(res.json()), res.status_code


@app.route('/quiz_data', methods=['POST'])
def create_quiz():
    if not check_passcode():
        return jsonify({'error': 'パスコードが違います'}), 401

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
def update_quiz(quiz_id):
    if not check_passcode():
        return jsonify({'error': 'パスコードが違います'}), 401

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
def delete_quiz(quiz_id):
    if not check_passcode():
        return jsonify({'error': 'パスコードが違います'}), 401

    res = requests.delete(
        f'{SUPABASE_URL}/rest/v1/quiz_data',
        headers=SUPABASE_HEADERS,
        params={'id': f'eq.{quiz_id}'}
    )
    return jsonify({'deleted': quiz_id}), 200


if __name__ == '__main__':
    app.run(debug=True, port=5000)