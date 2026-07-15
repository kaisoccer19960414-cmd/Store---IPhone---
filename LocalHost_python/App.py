#ローカルホスト専用コード　普段使ってない
#テスト用

from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
app.json.ensure_ascii = False 
CORS(app)  # フロント(JSファイル)からの通信を許可する

DB_PATH = os.path.join(os.path.dirname(__file__), 'quiz.db')


def get_db_connection():
    """DBへの接続を1つ用意して返す"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 結果を辞書っぽく扱えるようにする
    return conn


def init_db():
    """アプリ起動時にテーブルがなければ作成する"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS quiz_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()


# ---------- 1. GET一覧（Supabaseの fetchAllQuizzes に相当） ----------
@app.route('/quiz_data', methods=['GET'])
def get_all_quizzes():
    limit = request.args.get('limit', default=20, type=int)

    conn = get_db_connection()
    rows = conn.execute(
        'SELECT id, question FROM quiz_data ORDER BY id DESC LIMIT ?',
        (limit,)
    ).fetchall()
    conn.close()

    # sqlite3.Row のリストを、普通の辞書のリストに変換してJSONで返す
    result = [dict(row) for row in rows]
    return jsonify(result), 200


# ---------- 2. POST保存（Supabaseの createQuiz に相当） ----------
@app.route('/quiz_data', methods=['POST'])
def create_quiz():
    body = request.get_json(silent=True)

    if not body or not body.get('question') or not body['question'].strip():
        return jsonify({'error': 'question is required'}), 400

    question = body['question'].strip()

    conn = get_db_connection()
    cursor = conn.execute(
        'INSERT INTO quiz_data (question) VALUES (?)',
        (question,)
    )
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    return jsonify({'id': new_id, 'question': question}), 201


# ---------- 3. DELETE削除 ----------
@app.route('/quiz_data/<int:quiz_id>', methods=['DELETE'])
def delete_quiz(quiz_id):
    conn = get_db_connection()
 
    # 削除対象が存在するか先に確認
    existing = conn.execute(
        'SELECT id FROM quiz_data WHERE id = ?', (quiz_id,)
    ).fetchone()
 
    if existing is None:
        conn.close()
        return jsonify({'error': f'id {quiz_id} は存在しません'}), 404
 
    conn.execute('DELETE FROM quiz_data WHERE id = ?', (quiz_id,))
    conn.commit()
    conn.close()
 
    return jsonify({'deleted': quiz_id}), 200
 
 
# ---------- 4. PATCH更新 ----------
@app.route('/quiz_data/<int:quiz_id>', methods=['PATCH'])
def update_quiz(quiz_id):
    body = request.get_json(silent=True)
 
    if not body or not body.get('question') or not body['question'].strip():
        return jsonify({'error': 'question is required'}), 400
 
    question = body['question'].strip()
 
    conn = get_db_connection()
 
    existing = conn.execute(
        'SELECT id FROM quiz_data WHERE id = ?', (quiz_id,)
    ).fetchone()
 
    if existing is None:
        conn.close()
        return jsonify({'error': f'id {quiz_id} は存在しません'}), 404
 
    conn.execute(
        'UPDATE quiz_data SET question = ? WHERE id = ?',
        (question, quiz_id)
    )
    conn.commit()
    conn.close()
 
    return jsonify({'id': quiz_id, 'question': question}), 200
 




if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)