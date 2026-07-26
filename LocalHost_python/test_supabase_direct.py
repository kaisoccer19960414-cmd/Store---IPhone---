# test_supabase_direct.py
from dotenv import load_dotenv
import os
import requests

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY')

print("SUPABASE_URL:", SUPABASE_URL)
print("KEYの長さ:", len(SUPABASE_SERVICE_KEY or ""))
print("KEYの先頭10文字:", (SUPABASE_SERVICE_KEY or "")[:10])
print("KEYの末尾10文字:", (SUPABASE_SERVICE_KEY or "")[-10:])

for i, ch in enumerate(SUPABASE_SERVICE_KEY):
    if ord(ch) > 127:
        print(f"怪しい文字を発見: 位置{i}, 文字='{ch}', コード={ord(ch)}")
print("チェック完了(何も表示されなければ、怪しい文字は無し)")

headers = {
    'apikey': SUPABASE_SERVICE_KEY,
    'Content-Type': 'application/json',
}

res = requests.post(
    f'{SUPABASE_URL}/rest/v1/quiz_data',
    headers={**headers, 'Prefer': 'return=representation'},
    json={'question': 'CallTracer直接テスト'}
)

print("ステータスコード:", res.status_code)
print("レスポンス:", res.text)