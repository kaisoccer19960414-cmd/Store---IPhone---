import os
import json
from supabase import create_client, Client
from google import genai
from google.genai import types

# 1. 接続設定
SUPABASE_URL = "https://tekrwutayfleorpfbuhc.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
# ⚠️ 実際のAPIキーを入れてください
client = genai.Client(api_key="YOUR_GEMINI_API_KEY") 

def main():
    print("🔄 Supabaseから要約未作成の最新の授業メモを読み込んでいます...")
    
    # 2. まだ要約（summary）が空の最新のメモを1件取得する
    response = supabase.table("lesson_notes").select("*").is_("summary", "null").order("id", desc=True).limit(1).execute()
    
    if not response.data:
        print("✨ すべての授業メモの要約が完了しているか、データがありません。")
        return
    
    latest_note = response.data[0]
    note_id = latest_note["id"]
    note_content = latest_note["content"]
    note_date = latest_note["lesson_date"]
    
    print(f"📝 対象のメモ（日付: {note_date}, ID: {note_id}）: \n---")
    print(note_content)
    print("---\n")
    
    # 3. ジェミタソへの要約プロンプト
    prompt = f"""
以下のIT授業のメモを論理的に整理し、復習しやすいように要約してください。
重要なキーワードやコードの解説等。

【授業メモ】
{note_content}
"""

    print("🤖 ジェミタソが要約を生成中...")
    
    # 4. Gemini APIを叩く（今回はプレーンなテキストで出力）
    ai_response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt
    )
    
    summary_text = ai_response.text
    print("✨ 要約が生成されました:")
    print(summary_text)
    
    # 5. Supabaseの同じデータに対して、要約（summary）を上書き保存（UPDATE）
    print("💾 要約データをSupabaseへ保存（UPDATE）中...")
    try:
        update_response = supabase.table("lesson_notes").update({"summary": summary_text}).eq("id", note_id).execute()
        print("🎉 2ページ目の要約エリア（クラウドDB）への自動保存が完了しました！")
        
    except Exception as e:
        print(f"❌ 保存処理でエラーが発生しました: {e}")

if __name__ == "__main__":
    main()