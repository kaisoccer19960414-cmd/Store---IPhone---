import os
from supabase import create_client, Client
from google import genai
from google.genai import types

# 1. 接続のための設定値（あなたのアプリの合言葉）
SUPABASE_URL = "https://tekrwutayfleorpfbuhc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80"

# 2. SupabaseとGeminiの準備（インスタンス化）
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ⚠️ 注意: GeminiのAPIキーは本来ここに書きます。今回はテスト用に空にしています。
client = genai.Client(api_key="YOUR_GEMINI_API_KEY") 

def main():
    print("🔄 Supabaseから最新の授業メモを読み込んでいます...")
    
    # 3. 倉庫から最新の授業メモを1件取ってくる (JavaでいうSELECT処理)
    response = supabase.table("lesson_notes").select("*").order("id", desc=True).limit(1).execute()
    
    if not response.data:
        print("❌ 授業メモが1件も見つかりませんでした。")
        return
    
    latest_note = response.data[0]
    note_content = latest_note["content"]
    note_date = latest_note["lesson_date"]
    
    print(f"📝 対象のメモ（{note_date}）: \n---")
    print(note_content)
    print("---\n")
    
    # 4. ジェミタソ（AI）へのプロンプト（命令書）を作る
    prompt = f"""
以下のPythonの授業メモを元にして、「3択問題」を1問作成してください。
Pythonのコードの動きと、Javaの文法の違いを比較できるような問題がベストです。

【元にする授業メモ】
{note_content} 

【出力フォーマット】 
以下の形式（JSON形式）だけで出力してください。余計な挨拶や解説の文字は一切不要です。
{{
  "question": "問題文をここに書く",
  "choice_a": "選択肢A",
  "choice_b": "選択肢B",
  "choice_c": "選択肢C",
  "answer": "AまたはBまたはC",
  "explanation": "解説をここに書く"
}}
"""

    print("🤖 ジェミタソが問題を生成中...")
    
    # 5. Gemini APIを叩いて問題を生成させる（2026年最新の高速モデル flash を使用）
    ai_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json" # 👈 JSONで返せと強制する
        )
    )
    
    # (省略) ... 上の処理の続き
    
    # AIが作ったテキストを表示
    quiz_json_text = ai_response.text
    print("✨ 問題が生成されました:")
    print(quiz_json_text)
    
    # 🌟【ここから追加】Supabaseへ自動保存（POST処理）
    print("💾 クイズデータをSupabaseへ保存中...")
    import json
    try:
        # AIが作ったJSONテキストをPythonで扱えるデータ（辞書型）に変換
        quiz_data = json.loads(quiz_json_text)
        
        # 1ページ目のテーブルの列名（question, answer, explanation）に合わせてデータを梱包
        insert_data = {
            "question": f"【問題】\n{quiz_data['question']}\n\nA: {quiz_data['choice_a']}\nB: {quiz_data['choice_b']}\nC: {quiz_data['choice_c']}",
            "answer": quiz_data["answer"],
            "explanation": quiz_data["explanation"]
        }
        
        # Supabaseの `quiz_data` テーブルにガシャコン！と挿入
        insert_response = supabase.table("quiz_data").insert(insert_data).execute()
        print("🎉 1ページ目の問題集（クラウドDB）へ自動保存が完了しました！")
        
    except Exception as e:
        print(f"❌ 保存処理でエラーが発生しました: {e}")

if __name__ == "__main__":
    main()